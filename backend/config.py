# ============================================================
# backend/config.py  —  NeuroAgent Configuration & Model Registry
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _first_existing_path(*candidates: str) -> str:
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return candidates[0] if candidates else ""

# ── Flask ──────────────────────────────────────────────────────
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", 5000))
DEBUG    = os.getenv("DEBUG", "True") == "True"

# ── API Keys ───────────────────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY",       "")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY",     "")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY",     "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SARVAM_API_KEY     = os.getenv("SARVAM_API_KEY",     "")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY",     "")

# ── Memory ────────────────────────────────────────────────────
PINECONE_API_KEY    = os.getenv("PINECONE_API_KEY",    "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "neuroagent-memory")
PINECONE_DIMENSION  = 768

# ── Gmail ─────────────────────────────────────────────────────
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "") or _first_existing_path(
    os.path.join(_REPO_ROOT, "gmail_credentials.json"),
    os.path.join(os.path.dirname(__file__), "gmail_credentials.json"),
)
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "") or _first_existing_path(
    os.path.join(_REPO_ROOT, "gmail_token.json"),
    os.path.join(os.path.dirname(__file__), "gmail_token.json"),
)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ── Agent Settings ─────────────────────────────────────────────
MAX_ITERATIONS    = 10
AGENT_TEMPERATURE = 0.7
DEFAULT_MODEL_ID  = "llama-3.3-70b-versatile"

# ── OpenRouter base URL ────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── Sarvam AI API base URL ─────────────────────────────────────
SARVAM_BASE_URL = "https://api.sarvam.ai"

# ══════════════════════════════════════════════════════════════
# MODEL REGISTRY
# ──────────────────────────────────────────────────────────────
# provider: "groq" | "gemini" | "openai" | "openrouter"
# requires_key: which runtime key the user must provide (or None)
# chat_model: True = usable for chat, False = generation-only
# ══════════════════════════════════════════════════════════════
MODELS = [

    # ── Groq ──────────────────────────────────────────────────
    {
        "id":           "llama-3.1-8b-instant",
        "label":        "LLaMA 3.1 8B Instant",
        "provider":     "groq",
        "description":  "Ultra-fast 8B model. Best for quick tasks and Q&A.",
        "requires_key": None,
        "context":      "128K",
        "chat_model":   True,
    },
    {
        "id":           "llama-3.3-70b-versatile",
        "label":        "LLaMA 3.3 70B Versatile",
        "provider":     "groq",
        "description":  "Powerful 70B model. Best all-round choice for most tasks.",
        "requires_key": None,
        "context":      "128K",
        "chat_model":   True,
    },
    {
        "id":           "openai/gpt-oss-120b",
        "label":        "GPT-OSS 120B (Groq)",
        "provider":     "groq",
        "description":  "OpenAI's open-source 120B model served via Groq.",
        "requires_key": None,
        "context":      "128K",
        "chat_model":   True,
    },
    {
        "id":           "qwen/qwen3-32b",
        "label":        "Qwen3 32B (Groq)",
        "provider":     "groq",
        "description":  "Alibaba Qwen3 32B via Groq — strong reasoning and code.",
        "requires_key": None,
        "context":      "32K",
        "chat_model":   True,
    },

    # ── OpenRouter (free tier) ────────────────────────────────
    {
        "id":           "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "label":        "Nemotron Nano Omni 30B",
        "provider":     "openrouter",
        "description":  "NVIDIA's free multimodal reasoning model via OpenRouter.",
        "requires_key": "openrouter",
        "context":      "32K",
        "chat_model":   True,
    },
    {
        "id":           "poolside/laguna-xs.2:free",
        "label":        "Laguna XS.2 (Poolside)",
        "provider":     "openrouter",
        "description":  "Poolside's free compact code-focused model via OpenRouter.",
        "requires_key": "openrouter",
        "context":      "16K",
        "chat_model":   True,
    },

    # ── OpenAI ────────────────────────────────────────────────
    {
        "id":           "gpt-4o",
        "label":        "GPT-4o",
        "provider":     "openai",
        "description":  "OpenAI's flagship multimodal model. Best reasoning + vision.",
        "requires_key": "openai",
        "context":      "128K",
        "chat_model":   True,
    },
    {
        "id":           "gpt-4o-mini",
        "label":        "GPT-4o Mini",
        "provider":     "openai",
        "description":  "Fast and affordable GPT-4o variant.",
        "requires_key": "openai",
        "context":      "128K",
        "chat_model":   True,
    },
    {
        "id":           "o3-mini",
        "label":        "o3 Mini",
        "provider":     "openai",
        "description":  "OpenAI o3 reasoning model — complex multi-step tasks.",
        "requires_key": "openai",
        "context":      "128K",
        "chat_model":   True,
    },

    # ── Gemini 2.0 Series ─────────────────────────────────────
    {
        "id":           "gemini-2.0-flash",
        "label":        "Gemini 2.0 Flash",
        "provider":     "gemini",
        "description":  "Google's general-purpose, cost-effective multimodal model.",
        "requires_key": "gemini",
        "context":      "1M",
        "chat_model":   True,
    },
    {
        "id":           "gemini-2.0-flash-lite",
        "label":        "Gemini 2.0 Flash-Lite",
        "provider":     "gemini",
        "description":  "Streamlined for high-frequency, low-latency tasks.",
        "requires_key": "gemini",
        "context":      "1M",
        "chat_model":   True,
    },

    # ── Gemini 2.5 Series ─────────────────────────────────────
    {
        "id":           "gemini-2.5-flash-preview-05-20",
        "label":        "Gemini 2.5 Flash",
        "provider":     "gemini",
        "description":  "Lightning-fast, balancing intelligence and latency.",
        "requires_key": "gemini",
        "context":      "1M",
        "chat_model":   True,
    },
    {
        "id":           "gemini-2.5-flash-lite-preview-06-17",
        "label":        "Gemini 2.5 Flash-Lite",
        "provider":     "gemini",
        "description":  "Optimized for high-throughput, cost-sensitive applications.",
        "requires_key": "gemini",
        "context":      "1M",
        "chat_model":   True,
    },
    {
        "id":           "gemini-2.5-pro-preview-05-06",
        "label":        "Gemini 2.5 Pro",
        "provider":     "gemini",
        "description":  "High-capability model for complex reasoning and coding.",
        "requires_key": "gemini",
        "context":      "1M",
        "chat_model":   True,
    },

    # ── Gemini 3 Series ───────────────────────────────────────
    {
        "id":           "gemini-3.1-flash-lite",
        "label":        "Gemini 3.1 Flash-Lite",
        "provider":     "gemini",
        "description":  "Latest Gen 3 Gemini — ultra-efficient Flash-Lite.",
        "requires_key": "gemini",
        "context":      "1M",
        "chat_model":   True,
    },
]

# ── Sarvam AI Audio Models (separate registry) ─────────────────
# These are not LLM chat models — they are generation-specific APIs
SARVAM_AUDIO_MODELS = [
    {
        "id":          "bulbul:v2",
        "label":       "Bulbul v2 — Text to Speech",
        "type":        "tts",
        "description": "High-quality multilingual TTS. Supports 11 Indian languages.",
        "voices":      ["meera", "pavithra", "maitreyi", "arvind", "amol", "amartya",
                        "diya", "neel", "misha", "vian", "arjun", "maya"],
        "languages":   ["hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN",
                        "mr-IN", "bn-IN", "gu-IN", "pa-IN", "od-IN"],
    },
    {
        "id":          "saarika:v2",
        "label":       "Saarika v2 — Speech to Text",
        "type":        "stt",
        "description": "Accurate STT for Indian English and regional languages.",
        "languages":   ["hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN",
                        "mr-IN", "bn-IN", "gu-IN", "pa-IN"],
    },
    {
        "id":          "saaras:v2",
        "label":       "Saaras v2 — Speech Analytics",
        "type":        "analytics",
        "description": "Diarized transcription with speaker segmentation.",
        "languages":   ["hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN"],
    },
]
