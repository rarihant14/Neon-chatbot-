# ============================================================
# backend/agents/tools.py  —  LangChain Tool Definitions
# ============================================================
# All tools available to the LangGraph agent.
# Grouped by category for easy selective binding.
# ============================================================

import subprocess
from langchain_core.tools import tool
from tavily import TavilyClient

from backend.config import TAVILY_API_KEY
from backend.utils.gmail_client import (
    get_recent_emails, send_email, is_gmail_available,
)

# ── Tavily client ─────────────────────────────────────────────
_tavily = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None


# ═══════════════════════════════════════════════════════════════
# WEB SEARCH
# ═══════════════════════════════════════════════════════════════
@tool
def web_search(query: str) -> str:
    """
    Search the web for current information using Tavily.
    Use for recent events, news, or any factual question needing up-to-date data.
    """
    if _tavily is None:
        return "Web search unavailable: TAVILY_API_KEY not set in .env"
    try:
        results = _tavily.search(query=query, search_depth="advanced", max_results=5)
        parts = [f"### {r['title']}\n{r['url']}\n{r['content']}" for r in results.get("results", [])]
        return "\n---\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search error: {e}"


# ═══════════════════════════════════════════════════════════════
# DEEP RESEARCH
# ═══════════════════════════════════════════════════════════════
@tool
def deep_research(topic: str) -> str:
    """
    Conduct comprehensive research on a topic using multiple search passes.
    Use for research tasks requiring in-depth, synthesised coverage.
    """
    if _tavily is None:
        return "Deep research unavailable: TAVILY_API_KEY not set in .env"
    try:
        context = _tavily.get_search_context(query=topic, max_tokens=4000)
        return f"## Deep Research: {topic}\n\n{context}"
    except Exception as e:
        return f"Deep research error: {e}"


# ═══════════════════════════════════════════════════════════════
# GMAIL — READ
# ═══════════════════════════════════════════════════════════════
@tool
def read_emails(query: str = "", max_results: int = 5) -> str:
    """
    Read emails from Gmail inbox. Optionally filter with Gmail search syntax.
    Example query: 'from:boss@example.com' or 'subject:invoice'.
    """
    if not is_gmail_available():
        return "Gmail not configured. Place gmail_credentials.json in the backend/ folder."
    emails = get_recent_emails(max_results=int(max_results), query=query)
    if not emails:
        return "No emails found."
    lines = []
    for i, e in enumerate(emails):
        if "error" in e:
            return e["error"]
        lines.append(
            f"**{i+1}. {e.get('subject','(No Subject)')}**\n"
            f"   From: {e.get('from','?')}   Date: {e.get('date','?')}\n"
            f"   Preview: {e.get('snippet','')}"
        )
    return "\n\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# GMAIL — SEND
# ═══════════════════════════════════════════════════════════════
@tool
def send_gmail(to: str, subject: str, body: str) -> str:
    """
    Compose and send an email via Gmail.
    Args: to (recipient address), subject (subject line), body (plain text body).
    """
    if not is_gmail_available():
        return "Gmail not configured. Place gmail_credentials.json in the backend/ folder."
    result = send_email(to=to, subject=subject, body=body)
    if result.get("success"):
        return f"Email sent to {to}. Message ID: {result.get('message_id')}"
    return f"Failed to send email: {result.get('error')}"


# ═══════════════════════════════════════════════════════════════
# SHELL COMMAND EXECUTION
# ═══════════════════════════════════════════════════════════════
@tool
def execute_command(command: str) -> str:
    """
    Execute a safe shell command and return its output.
    Blocked patterns: rm -rf, mkfs, dd if=, fork bombs.
    Use for: listing files, running scripts, system info, etc.
    """
    BLOCKED = ["rm -rf", "mkfs", "dd if=", ":(){", "sudo rm", "format c:"]
    for pattern in BLOCKED:
        if pattern in command:
            return f"Command blocked for safety — contains '{pattern}'."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "(Command completed with no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Command error: {e}"


# ═══════════════════════════════════════════════════════════════
# CALCULATOR
# ═══════════════════════════════════════════════════════════════
@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression. Supports standard math functions.
    Examples: '2 ** 10', 'sqrt(144)', 'sin(3.14159 / 2) * 100'.
    """
    import math
    allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    allowed.update({"__builtins__": {}, "abs": abs, "round": round, "min": min, "max": max})
    try:
        result = eval(expression, allowed)
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


# ═══════════════════════════════════════════════════════════════
# SARVAM TTS TOOL (agent-callable)
# ═══════════════════════════════════════════════════════════════
@tool
def sarvam_text_to_speech(
    text: str,
    language: str = "hi-IN",
    speaker: str = "meera",
) -> str:
    """
    Generate speech audio from text using Sarvam AI Bulbul v2.
    Supports 11 Indian languages. Returns confirmation with audio info.
    Args:
        text:     Text to convert (max ~500 chars)
        language: BCP-47 code e.g. 'hi-IN', 'en-IN', 'ta-IN', 'te-IN'
        speaker:  Voice name e.g. 'meera', 'arvind', 'pavithra', 'amol'
    """
    from backend.utils.sarvam_client import text_to_speech_sarvam, is_sarvam_available
    if not is_sarvam_available():
        return "Sarvam AI not configured. Add SARVAM_API_KEY to .env or enter it in settings."
    result = text_to_speech_sarvam(text=text, target_language_code=language, speaker=speaker)
    if result["success"]:
        return f"✅ Audio generated successfully via Sarvam Bulbul v2.\nLanguage: {language} | Speaker: {speaker}\nRequest ID: {result.get('request_id','—')}\nAudio is ready for playback."
    return f"Sarvam TTS failed: {result['error']}"


# ═══════════════════════════════════════════════════════════════
# SARVAM TRANSLATE TOOL
# ═══════════════════════════════════════════════════════════════
@tool
def sarvam_translate(
    text: str,
    source_language: str = "en-IN",
    target_language: str = "hi-IN",
) -> str:
    """
    Translate text between Indian languages using Sarvam AI Mayura.
    Supports: hi-IN, en-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, bn-IN, gu-IN, pa-IN.
    Args:
        text:            Text to translate
        source_language: Source language BCP-47 code
        target_language: Target language BCP-47 code
    """
    from backend.utils.sarvam_client import translate_text_sarvam, is_sarvam_available
    if not is_sarvam_available():
        return "Sarvam AI not configured. Add SARVAM_API_KEY to .env."
    result = translate_text_sarvam(
        text=text,
        source_language_code=source_language,
        target_language_code=target_language,
    )
    if result["success"]:
        return f"Translation ({source_language} → {target_language}):\n\n{result['translated_text']}"
    return f"Sarvam Translate failed: {result['error']}"


# ═══════════════════════════════════════════════════════════════
# SUMMARISE TEXT
# ═══════════════════════════════════════════════════════════════
@tool
def summarise_text(text: str, max_words: int = 150) -> str:
    """
    Summarise a long piece of text in approximately max_words words.
    Useful for condensing articles, emails, or documents.
    """
    word_count = len(text.split())
    return (
        f"Please summarise the following text ({word_count} words) "
        f"in approximately {max_words} words:\n\n{text[:3000]}"
    )


# ── Tool Registry ─────────────────────────────────────────────
ALL_TOOLS = [
    web_search,
    deep_research,
    read_emails,
    send_gmail,
    execute_command,
    calculator,
    sarvam_text_to_speech,
    sarvam_translate,
    summarise_text,
]
