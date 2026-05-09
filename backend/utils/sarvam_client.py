# ============================================================
# backend/utils/sarvam_client.py  —  Sarvam AI Integration
# ============================================================
# Sarvam AI provides Indian-language AI models:
#   - Bulbul v2  : Text-to-Speech (11 Indian languages, 12 voices)
#   - Saarika v2 : Speech-to-Text transcription
#   - Saaras v2  : Speech analytics / diarization
#
# Docs: https://docs.sarvam.ai/api-reference-docs/
# ============================================================

import os
import base64
import requests
from backend.config import SARVAM_API_KEY, SARVAM_BASE_URL


def _get_key(runtime_key: str = "") -> str:
    """Return the Sarvam API key (runtime arg takes precedence)."""
    return runtime_key or SARVAM_API_KEY


def _try_import_sdk():
    """
    Import SarvamAI SDK lazily.
    Returns SarvamAI class or None.
    """
    try:
        from sarvamai import SarvamAI  # type: ignore
        return SarvamAI
    except Exception:
        return None


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return None


def _http_error_message(resp: requests.Response) -> str:
    data = _safe_json(resp)
    if isinstance(data, dict):
        for key in ("message", "error", "detail"):
            if data.get(key):
                return str(data.get(key))
    text = (resp.text or "").strip()
    if text:
        return text[:500]
    return f"HTTP {getattr(resp, 'status_code', 'error')}"


def is_sarvam_available(runtime_key: str = "") -> bool:
    """Check if a Sarvam API key is available."""
    return bool(_get_key(runtime_key))


# ═══════════════════════════════════════════════════════════════
# TEXT TO SPEECH  — Bulbul v2
# ═══════════════════════════════════════════════════════════════

def text_to_speech_sarvam(
    text: str,
    target_language_code: str = "hi-IN",
    speaker: str = "meera",
    pitch: float = 0.0,
    pace: float = 1.0,
    loudness: float = 1.5,
    speech_sample_rate: int = 8000,
    enable_preprocessing: bool = True,
    model: str = "bulbul:v2",
    api_key: str = "",
) -> dict:
    """
    Convert text to speech using Sarvam AI Bulbul v2.

    Args:
        text:                 Input text (max ~500 chars recommended per call)
        target_language_code: BCP-47 language code (e.g. "hi-IN", "en-IN", "ta-IN")
        speaker:              Voice name (meera, pavithra, arvind, etc.)
        pitch:                Pitch shift (-0.75 to 0.75)
        pace:                 Speed multiplier (0.5 to 2.0)
        loudness:             Volume multiplier (0.5 to 3.0)
        speech_sample_rate:   8000 or 16000 Hz
        enable_preprocessing: Auto-normalize text (numbers, abbreviations)
        model:                Sarvam TTS model ID
        api_key:              Runtime API key (overrides .env)

    Returns:
        {
          "success": bool,
          "audio_base64": str,   # base64-encoded WAV audio
          "request_id": str,
          "error": str           # only if success=False
        }
    """
    key = _get_key(api_key)
    if not key:
        return {"success": False, "error": "Sarvam API key not configured. Add SARVAM_API_KEY to .env or enter it in settings."}

    # Prefer SarvamAI SDK when available (matches sarvamai usage patterns).
    SarvamAI = _try_import_sdk()
    if SarvamAI is not None:
        try:
            client = SarvamAI(api_subscription_key=key)

            # SDK method signature can vary; try with speaker first, then without.
            try:
                resp = client.text_to_speech.convert(
                    text=text,
                    target_language_code=target_language_code,
                    speaker=speaker,
                )
            except TypeError:
                resp = client.text_to_speech.convert(
                    text=text,
                    target_language_code=target_language_code,
                )
            except Exception as e:
                # Some SDK versions raise on invalid speakers; retry without speaker and
                # with a conservative fallback that appears commonly supported.
                msg = str(e)
                if "Speaker" in msg and "not recognized" in msg:
                    try:
                        resp = client.text_to_speech.convert(
                            text=text,
                            target_language_code=target_language_code,
                        )
                    except Exception:
                        resp = client.text_to_speech.convert(
                            text=text,
                            target_language_code=target_language_code,
                            speaker="anushka",
                        )
                else:
                    raise

            audios = None
            if isinstance(resp, dict):
                audios = resp.get("audios") or resp.get("audio")
                request_id = resp.get("request_id") or resp.get("id") or ""
            else:
                audios = getattr(resp, "audios", None) or getattr(resp, "audio", None)
                request_id = getattr(resp, "request_id", "") or getattr(resp, "id", "")

            audio_b64 = ""
            if isinstance(audios, list) and audios:
                audio_b64 = audios[0] or ""
            elif isinstance(audios, str):
                audio_b64 = audios

            if audio_b64:
                return {"success": True, "audio_base64": audio_b64, "request_id": request_id or ""}
            print("[Sarvam] SDK TTS returned no audio, falling back to HTTP.")
        except Exception as e:
            print(f"[Sarvam] SDK TTS failed, falling back to HTTP: {e}")

    url     = f"{SARVAM_BASE_URL}/text-to-speech"
    headers = {
        "api-subscription-key": key,
        "Content-Type": "application/json",
    }

    try:
        # Sarvam's TTS schema has varied across versions; try `inputs: [text]`
        # first, then fall back to `input: text` for stricter validators.
        payloads = [
            {
                "inputs":               [text],
                "target_language_code": target_language_code,
                "speaker":              speaker,
                "pitch":                pitch,
                "pace":                 pace,
                "loudness":             loudness,
                "speech_sample_rate":   speech_sample_rate,
                "enable_preprocessing": enable_preprocessing,
                "model":                model,
            },
            {
                "input":                text,
                "target_language_code": target_language_code,
                "speaker":              speaker,
                "pitch":                pitch,
                "pace":                 pace,
                "loudness":             loudness,
                "speech_sample_rate":   speech_sample_rate,
                "enable_preprocessing": enable_preprocessing,
                "model":                model,
            },
        ]

        last_error = None
        for payload in payloads:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if not resp.ok:
                last_error = _http_error_message(resp)
                # Only retry on schema-ish errors; otherwise, fail fast.
                if resp.status_code not in (400, 404, 422):
                    break
                continue

            data = _safe_json(resp) or {}

            # Sarvam may return `audios: [b64...]` or `audio: b64...`
            audios = []
            if isinstance(data, dict):
                if isinstance(data.get("audios"), list):
                    audios = data.get("audios") or []
                elif isinstance(data.get("audio"), str) and data.get("audio"):
                    audios = [data.get("audio")]

            if not audios:
                last_error = "No audio returned from Sarvam API."
                continue

            return {
                "success":      True,
                "audio_base64": audios[0],   # already base64 WAV
                "request_id":   (data.get("request_id", "") if isinstance(data, dict) else ""),
            }

        return {"success": False, "error": f"Sarvam TTS error: {last_error or 'Request failed.'}"}

    except Exception as e:
        return {"success": False, "error": f"Sarvam TTS error: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# SPEECH TO TEXT  — Saarika v2
# ═══════════════════════════════════════════════════════════════

def speech_to_text_sarvam(
    audio_bytes: bytes,
    language_code: str = "hi-IN",
    model: str = "saarika:v2",
    with_timestamps: bool = False,
    api_key: str = "",
) -> dict:
    """
    Transcribe audio using Sarvam AI Saarika v2.

    Args:
        audio_bytes:     Raw audio bytes (WAV or any common format)
        language_code:   BCP-47 language code
        model:           Sarvam STT model ID
        with_timestamps: Include word-level timestamps
        api_key:         Runtime API key

    Returns:
        {
          "success": bool,
          "transcript": str,
          "language_code": str,
          "request_id": str,
          "error": str
        }
    """
    key = _get_key(api_key)
    if not key:
        return {"success": False, "error": "Sarvam API key not configured."}

    url     = f"{SARVAM_BASE_URL}/speech-to-text"
    headers = {"api-subscription-key": key}

    try:
        files   = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        payload = {
            "language_code":   language_code,
            "model":           model,
            "with_timestamps": str(with_timestamps).lower(),
        }

        resp = requests.post(url, headers=headers, data=payload, files=files, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        return {
            "success":       True,
            "transcript":    data.get("transcript", ""),
            "language_code": data.get("language_code", language_code),
            "request_id":    data.get("request_id", ""),
        }

    except requests.exceptions.HTTPError as e:
        msg = ""
        try:    msg = e.response.json().get("message", str(e))
        except: msg = str(e)
        return {"success": False, "error": f"Sarvam STT error: {msg}"}
    except Exception as e:
        return {"success": False, "error": f"Sarvam STT error: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# SPEECH ANALYTICS  — Saaras v2
# ═══════════════════════════════════════════════════════════════

def speech_analytics_sarvam(
    audio_bytes: bytes,
    language_code: str = "hi-IN",
    model: str = "saaras:v2",
    api_key: str = "",
) -> dict:
    """
    Diarized transcription with speaker segmentation using Saaras v2.

    Returns:
        {
          "success": bool,
          "diarized_transcript": list,   # list of {speaker, transcript, start, end}
          "request_id": str,
          "error": str
        }
    """
    key = _get_key(api_key)
    if not key:
        return {"success": False, "error": "Sarvam API key not configured."}

    url     = f"{SARVAM_BASE_URL}/speech-to-text-translate"
    headers = {"api-subscription-key": key}

    try:
        files   = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        payload = {"language_code": language_code, "model": model}

        resp = requests.post(url, headers=headers, data=payload, files=files, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        return {
            "success":              True,
            "diarized_transcript":  data.get("diarized_transcript", []),
            "transcript":           data.get("transcript", ""),
            "request_id":           data.get("request_id", ""),
        }

    except requests.exceptions.HTTPError as e:
        msg = ""
        try:    msg = e.response.json().get("message", str(e))
        except: msg = str(e)
        return {"success": False, "error": f"Sarvam Analytics error: {msg}"}
    except Exception as e:
        return {"success": False, "error": f"Sarvam Analytics error: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# TEXT TRANSLATION  — Mayura v2
# ═══════════════════════════════════════════════════════════════

def translate_text_sarvam(
    text: str,
    source_language_code: str = "en-IN",
    target_language_code: str = "hi-IN",
    speaker_gender: str = "Female",
    mode: str = "formal",
    api_key: str = "",
) -> dict:
    """
    Translate text between Indian languages using Sarvam Mayura.

    Returns:
        {
          "success": bool,
          "translated_text": str,
          "request_id": str,
          "error": str
        }
    """
    key = _get_key(api_key)
    if not key:
        return {"success": False, "error": "Sarvam API key not configured."}

    # Prefer the official SDK when available (matches the user's suggested setup).
    SarvamAI = _try_import_sdk()
    if SarvamAI is not None:
        try:
            client = SarvamAI(api_subscription_key=key)
            resp = client.text.translate(
                input=text,
                source_language_code=source_language_code,
                target_language_code=target_language_code,
                speaker_gender=speaker_gender,
            )

            # Normalize common response shapes (dict, pydantic, object attrs)
            translated = ""
            request_id = ""
            if isinstance(resp, dict):
                translated = resp.get("translated_text") or resp.get("output") or resp.get("text") or ""
                request_id = resp.get("request_id") or resp.get("id") or ""
            else:
                translated = getattr(resp, "translated_text", "") or getattr(resp, "output", "") or getattr(resp, "text", "")
                request_id = getattr(resp, "request_id", "") or getattr(resp, "id", "")

            return {"success": True, "translated_text": translated or "", "request_id": request_id or ""}
        except Exception as e:
            # Fall back to HTTP implementation if SDK fails for any reason
            print(f"[Sarvam] SDK translate failed, falling back to HTTP: {e}")

    url     = f"{SARVAM_BASE_URL}/translate"
    headers = {
        "api-subscription-key": key,
        "Content-Type":         "application/json",
    }
    payload = {
        "input":                text,
        "source_language_code": source_language_code,
        "target_language_code": target_language_code,
        "speaker_gender":       speaker_gender,
        "mode":                 mode,
        "model":                "mayura:v1",
        "enable_preprocessing": True,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        return {
            "success":         True,
            "translated_text": data.get("translated_text", ""),
            "request_id":      data.get("request_id", ""),
        }

    except requests.exceptions.HTTPError as e:
        msg = ""
        try:    msg = e.response.json().get("message", str(e))
        except: msg = str(e)
        return {"success": False, "error": f"Sarvam Translate error: {msg}"}
    except Exception as e:
        return {"success": False, "error": f"Sarvam Translate error: {str(e)}"}
