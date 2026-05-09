# ============================================================
# backend/utils/voice.py
# NeuroAgent - Voice Input / Output Utilities
# ============================================================
# Speech-to-text using SpeechRecognition (Google Web API).
# Text-to-speech using gTTS (online) with pyttsx3 as fallback.
# ============================================================

import io
import base64
import tempfile
import os
from typing import Optional

# ── Speech Recognition ────────────────────────────────────────
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    print("[Voice] SpeechRecognition not installed.")

# ── Text-to-Speech ────────────────────────────────────────────
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


def transcribe_audio_bytes(audio_bytes: bytes, language: str = "en-US") -> str:
    """
    Convert raw audio bytes (WAV format) to text.
    Uses Google Web Speech API via SpeechRecognition.
    Returns transcribed string or an error message.
    """
    if not SR_AVAILABLE:
        return "[Voice Error] SpeechRecognition library not available."

    recognizer = sr.Recognizer()

    try:
        # Wrap bytes in a file-like object
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data, language=language)
        return text

    except sr.UnknownValueError:
        return "[Voice] Could not understand audio."
    except sr.RequestError as e:
        return f"[Voice] Speech API error: {e}"
    except Exception as e:
        return f"[Voice] Error: {e}"


def text_to_speech_base64(text: str, language: str = "en") -> Optional[str]:
    """
    Convert `text` to speech and return as a base64-encoded MP3 string.
    The frontend can play this directly via the Web Audio API.
    Returns None if TTS is unavailable.
    """
    if GTTS_AVAILABLE:
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            mp3_buffer = io.BytesIO()
            tts.write_to_fp(mp3_buffer)
            mp3_buffer.seek(0)
            encoded = base64.b64encode(mp3_buffer.read()).decode("utf-8")
            return encoded
        except Exception as e:
            print(f"[Voice] gTTS error: {e}")

    # Fallback: pyttsx3 (offline, WAV output)
    if PYTTSX3_AVAILABLE:
        try:
            engine = pyttsx3.init()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            with open(tmp_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")

            os.unlink(tmp_path)
            return encoded
        except Exception as e:
            print(f"[Voice] pyttsx3 error: {e}")

    print("[Voice] No TTS engine available.")
    return None


def text_to_speech(text: str, language: str = "en") -> dict:
    """
    Convert `text` to speech and return:
      { success, audio_base64, audio_mime, engine, error }
    """
    if not text or not text.strip():
        return {"success": False, "error": "text is required."}

    if GTTS_AVAILABLE:
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            mp3_buffer = io.BytesIO()
            tts.write_to_fp(mp3_buffer)
            mp3_buffer.seek(0)
            encoded = base64.b64encode(mp3_buffer.read()).decode("utf-8")
            return {
                "success": True,
                "audio_base64": encoded,
                "audio_mime": "audio/mpeg",
                "engine": "gtts",
            }
        except Exception as e:
            print(f"[Voice] gTTS error: {e}")

    if PYTTSX3_AVAILABLE:
        try:
            engine = pyttsx3.init()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            with open(tmp_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")

            os.unlink(tmp_path)
            return {
                "success": True,
                "audio_base64": encoded,
                "audio_mime": "audio/wav",
                "engine": "pyttsx3",
            }
        except Exception as e:
            print(f"[Voice] pyttsx3 error: {e}")

    return {"success": False, "error": "No TTS engine available."}


def is_voice_available() -> bool:
    """Return True if at least microphone input is available."""
    return SR_AVAILABLE
