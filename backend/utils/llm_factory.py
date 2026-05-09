# ============================================================
# backend/utils/llm_factory.py  —  LLM Instantiation Factory
# ============================================================
# Supports: Groq | Gemini | OpenAI | OpenRouter
# Runtime keys passed in from session override .env values.
# ============================================================

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from backend.config import (
    GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    AGENT_TEMPERATURE, MODELS, DEFAULT_MODEL_ID,
)


def _model_info(model_id: str) -> dict:
    """Return model metadata dict. Falls back to default if not found."""
    for m in MODELS:
        if m["id"] == model_id:
            return m
    for m in MODELS:
        if m["id"] == DEFAULT_MODEL_ID:
            return m
    return MODELS[0]


def get_llm(
    model_id: str,
    temperature: float = AGENT_TEMPERATURE,
    gemini_api_key: str = "",
    openai_api_key: str = "",
    openrouter_api_key: str = "",
) -> BaseChatModel:
    """
    Instantiate and return the correct LangChain chat model.
    Runtime key arguments override .env values when provided.
    Raises ValueError if the required key is missing.
    """
    info     = _model_info(model_id)
    provider = info["provider"]

    # ── Groq ────────────────────────────────────────────────
    if provider == "groq":
        key = GROQ_API_KEY
        if not key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file.\n"
                "Get a free key at: https://console.groq.com"
            )
        return ChatGroq(
            model=model_id,
            api_key=key,
            temperature=temperature,
        )

    # ── Gemini ───────────────────────────────────────────────
    elif provider == "gemini":
        key = gemini_api_key or GEMINI_API_KEY
        if not key:
            raise ValueError(
                "Gemini API key required. Enter it in the model selection screen.\n"
                "Get a free key at: https://aistudio.google.com/app/apikey"
            )
        return ChatGoogleGenerativeAI(
            model=model_id,
            google_api_key=key,
            temperature=temperature,
            convert_system_message_to_human=True,
        )

    # ── OpenAI ───────────────────────────────────────────────
    elif provider == "openai":
        key = openai_api_key or OPENAI_API_KEY
        if not key:
            raise ValueError(
                "OpenAI API key required. Enter it in the model selection screen.\n"
                "Get a key at: https://platform.openai.com/api-keys"
            )
        return ChatOpenAI(
            model=model_id,
            api_key=key,
            temperature=temperature,
        )

    # ── OpenRouter ───────────────────────────────────────────
    elif provider == "openrouter":
        key = openrouter_api_key or OPENROUTER_API_KEY
        if not key:
            raise ValueError(
                "OpenRouter API key required. Enter it in the model selection screen.\n"
                "Get a free key at: https://openrouter.ai/keys"
            )
        return ChatOpenAI(
            model=model_id,
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            default_headers={
                "HTTP-Referer": "https://neuroagent.local",
                "X-Title":      "NeuroAgent",
            },
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")


def list_models() -> list[dict]:
    """Return the full model registry for the frontend (with derived mode)."""
    def derive_mode(m: dict) -> str:
        mid = (m.get("id") or "").lower()
        provider = (m.get("provider") or "").lower()
        desc = (m.get("description") or "").lower()

        if "reason" in desc or "thinking" in desc:
            return "reasoning"
        if provider == "gemini" and ("pro" in mid or "thinking" in mid):
            return "reasoning"
        if provider == "openai" and (mid.startswith("o3") or mid.startswith("o1") or "reason" in mid):
            return "reasoning"
        return "fast"

    out = []
    for m in MODELS:
        mm = dict(m)
        mm["mode"] = mm.get("mode") or derive_mode(mm)
        out.append(mm)
    return out
