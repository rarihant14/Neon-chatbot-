# ============================================================
# backend/app.py  —  Flask API Server
# ============================================================
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session

from backend.config import FLASK_SECRET_KEY, APP_HOST, APP_PORT, DEBUG, SARVAM_AUDIO_MODELS
from backend.db.user_store import (
    init_db, get_or_create_user, get_user_preferences,
    update_user_model, update_voice_setting,
    get_recent_history, clear_history,
)
from backend.db.memory_store import is_available as memory_available
from backend.utils.llm_factory import list_models
from backend.utils.voice import transcribe_audio_bytes, text_to_speech, is_voice_available
from backend.utils.gmail_client import is_gmail_available
from backend.utils.sarvam_client import (
    text_to_speech_sarvam, speech_to_text_sarvam,
    translate_text_sarvam, is_sarvam_available,
)

# Disable Flask's built-in static route because the frontend lives under
# `frontend/static/` and is mounted by the repository root `app.py`.
app = Flask(__name__, template_folder=None, static_folder=None)
app.secret_key = FLASK_SECRET_KEY
app.config["SESSION_TYPE"]     = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(__file__), "..", ".flask_sessions")
app.config["SESSION_PERMANENT"] = False
Session(app)
CORS(app, supports_credentials=True)

# ── Helpers ────────────────────────────────────────────────────
def _ok(**kw):        return jsonify({"status": "ok",    **kw})
def _err(m, c=400):   return jsonify({"status": "error", "message": m}), c
def _me():            return session.get("user_id"), session.get("username")


# ══════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════
@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if not username or len(username) < 2:  return _err("Username must be at least 2 characters.")
    if len(username) > 30:                 return _err("Username must be 30 characters or fewer.")

    user  = get_or_create_user(username)
    prefs = get_user_preferences(user["id"])
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    session["model_id"] = prefs.get("selected_model", "llama-3.3-70b-versatile")

    return _ok(
        user_id      = user["id"],
        username     = user["username"],
        model_id     = prefs.get("selected_model"),
        voice_enabled= prefs.get("voice_enabled", False),
    )


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return _ok(message="Logged out.")


@app.route("/api/session", methods=["GET"])
def get_session():
    uid, uname = _me()
    if not uid: return _err("Not logged in.", 401)
    prefs = get_user_preferences(uid)
    return _ok(
        user_id      = uid,
        username     = uname,
        model_id     = session.get("model_id"),
        voice_enabled= prefs.get("voice_enabled", False),
        agent_mode   = session.get("agent_mode", "default"),
    )


# ══════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════
@app.route("/api/models", methods=["GET"])
def get_models():
    return _ok(models=list_models())


@app.route("/api/model/select", methods=["POST"])
def select_model():
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)

    data     = request.get_json(silent=True) or {}
    model_id = data.get("model_id", "").strip()
    if not model_id: return _err("model_id is required.")

    valid_ids = [m["id"] for m in list_models()]
    if model_id not in valid_ids: return _err(f"Unknown model: {model_id}")

    # Store runtime keys in session (never saved to DB)
    for key_field in ("gemini_api_key", "openai_api_key", "openrouter_api_key", "sarvam_api_key"):
        if data.get(key_field):
            session[key_field] = data[key_field]

    update_user_model(uid, model_id)
    session["model_id"] = model_id
    return _ok(model_id=model_id)


# ══════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════
@app.route("/api/chat", methods=["POST"])
def chat():
    uid, uname = _me()
    if not uid: return _err("Not logged in.", 401)

    data     = request.get_json(silent=True) or {}
    message  = data.get("message", "").strip()
    model_id = data.get("model_id") or session.get("model_id", "llama-3.3-70b-versatile")
    if not message: return _err("message is required.")

    from backend.agents.orchestrator import run_chat
    try:
        result = run_chat(
            user_id            = uid,
            username           = uname,
            user_message       = message,
            model_id           = model_id,
            agent_mode         = session.get("agent_mode", "default"),
            gemini_api_key     = session.get("gemini_api_key",     ""),
            openai_api_key     = session.get("openai_api_key",     ""),
            openrouter_api_key = session.get("openrouter_api_key", ""),
            sarvam_api_key     = session.get("sarvam_api_key",     ""),
        )
        return _ok(**result)
    except Exception as e:
        print(f"[Chat Error] {e}")
        return _err(f"Agent error: {str(e)}", 500)


@app.route("/api/agent/mode", methods=["GET", "POST"])
def agent_mode():
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)

    if request.method == "GET":
        return _ok(agent_mode=session.get("agent_mode", "default"))

    data = request.get_json(silent=True) or {}
    mode = (data.get("agent_mode") or "default").lower().strip()
    allowed = {"default", "deep", "web", "resched"}
    if mode not in allowed:
        return _err(f"Invalid agent_mode. Allowed: {sorted(list(allowed))}")
    session["agent_mode"] = mode
    return _ok(agent_mode=mode)


# ══════════════════════════════════════════════════════════════
# VOICE (SpeechRecognition + gTTS fallback)
# ══════════════════════════════════════════════════════════════
@app.route("/api/voice/input", methods=["POST"])
def voice_input():
    if "audio" not in request.files: return _err("No audio file.")
    audio_bytes = request.files["audio"].read()
    if not audio_bytes: return _err("Empty audio file.")
    return _ok(transcription=transcribe_audio_bytes(audio_bytes))


@app.route("/api/voice/output", methods=["POST"])
def voice_output():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text: return _err("text is required.")

    # Prefer Sarvam (if configured) and fall back to local gTTS/pyttsx3.
    sarvam_key = data.get("sarvam_api_key") or session.get("sarvam_api_key", "")
    language   = data.get("language", "en-IN")
    speaker    = data.get("speaker", "anushka")

    if is_sarvam_available(sarvam_key):
        result = text_to_speech_sarvam(
            text=text,
            target_language_code=language,
            speaker=speaker,
            api_key=sarvam_key,
        )
        if result.get("success"):
            if data.get("sarvam_api_key"):
                session["sarvam_api_key"] = sarvam_key
            return _ok(
                audio_base64=result["audio_base64"],
                audio_mime="audio/wav",
                engine="sarvam",
                request_id=result.get("request_id", ""),
            )

    fallback = text_to_speech(text, language="en")
    if fallback.get("success"):
        return _ok(
            audio_base64=fallback["audio_base64"],
            audio_mime=fallback["audio_mime"],
            engine=fallback.get("engine", "fallback"),
        )

    return _err(fallback.get("error") or "TTS generation failed.", 500)


@app.route("/api/voice/toggle", methods=["POST"])
def toggle_voice():
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)
    enabled = bool((request.get_json(silent=True) or {}).get("enabled", False))
    update_voice_setting(uid, enabled)
    return _ok(voice_enabled=enabled)


# ══════════════════════════════════════════════════════════════
# SARVAM AI — Audio Generation & Translation
# ══════════════════════════════════════════════════════════════
@app.route("/api/sarvam/tts", methods=["POST"])
def sarvam_tts():
    """
    Generate speech audio using Sarvam AI Bulbul v2.
    Body: { text, language, speaker, api_key (optional) }
    Returns: { audio_base64, request_id }
    """
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)

    data     = request.get_json(silent=True) or {}
    text     = data.get("text", "").strip()
    language = data.get("language", "hi-IN")
    speaker  = data.get("speaker", "meera")
    api_key  = data.get("api_key") or session.get("sarvam_api_key", "")

    if not text: return _err("text is required.")

    result = text_to_speech_sarvam(
        text                 = text,
        target_language_code = language,
        speaker              = speaker,
        api_key              = api_key,
    )

    if result["success"]:
        # Store key in session if provided at runtime
        if data.get("api_key"):
            session["sarvam_api_key"] = data["api_key"]
        return _ok(
            audio_base64 = result["audio_base64"],
            request_id   = result.get("request_id", ""),
            language     = language,
            speaker      = speaker,
        )
    return _err(result["error"], 500)


@app.route("/api/sarvam/stt", methods=["POST"])
def sarvam_stt():
    """
    Transcribe audio using Sarvam AI Saarika v2.
    Multipart: audio file + language field.
    """
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)

    if "audio" not in request.files: return _err("No audio file.")
    audio_bytes = request.files["audio"].read()
    language    = request.form.get("language", "hi-IN")
    api_key     = request.form.get("api_key")  or session.get("sarvam_api_key", "")

    result = speech_to_text_sarvam(
        audio_bytes   = audio_bytes,
        language_code = language,
        api_key       = api_key,
    )

    if result["success"]:
        return _ok(transcript=result["transcript"], language_code=result["language_code"])
    return _err(result["error"], 500)


@app.route("/api/sarvam/translate", methods=["POST"])
def sarvam_translate():
    """
    Translate text between Indian languages using Sarvam AI Mayura.
    Body: { text, source_language, target_language, api_key (optional) }
    """
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)

    data    = request.get_json(silent=True) or {}
    text    = data.get("text", "").strip()
    src     = data.get("source_language", "en-IN")
    tgt     = data.get("target_language", "hi-IN")
    api_key = data.get("api_key") or session.get("sarvam_api_key", "")

    if not text: return _err("text is required.")

    result = translate_text_sarvam(
        text                 = text,
        source_language_code = src,
        target_language_code = tgt,
        api_key              = api_key,
    )

    if result["success"]:
        return _ok(translated_text=result["translated_text"])
    return _err(result["error"], 500)


@app.route("/api/sarvam/models", methods=["GET"])
def sarvam_models():
    """Return available Sarvam AI audio models."""
    return _ok(models=SARVAM_AUDIO_MODELS)


# ══════════════════════════════════════════════════════════════
# HISTORY
# ══════════════════════════════════════════════════════════════
@app.route("/api/history", methods=["GET"])
def get_history():
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)
    history = get_recent_history(uid, limit=int(request.args.get("limit", 50)))
    return _ok(history=history)


@app.route("/api/history/clear", methods=["POST"])
def clear_chat_history():
    uid, _ = _me()
    if not uid: return _err("Not logged in.", 401)
    clear_history(uid)
    return _ok(message="History cleared.")


# ══════════════════════════════════════════════════════════════
# STATUS / HEALTH
# ══════════════════════════════════════════════════════════════
@app.route("/api/health", methods=["GET"])
def health():
    sarvam_key = session.get("sarvam_api_key", "")
    return _ok(
        service = "NeuroAgent",
        memory  = memory_available(),
        gmail   = is_gmail_available(),
        voice   = is_voice_available(),
        sarvam  = is_sarvam_available(sarvam_key),
    )


def create_app():
    init_db()
    return app


if __name__ == "__main__":
    init_db()
    app.run(host=APP_HOST, port=APP_PORT, debug=DEBUG)
