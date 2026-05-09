# ============================================================
# backend/agents/orchestrator.py  —  Master Orchestrator
# ============================================================
# Single entry point for all chat turns.
# Passes runtime API keys through the LangGraph state.
# NOTE: stream_chat is intentionally NOT implemented here —
# the app uses standard invoke() for reliability.
# ============================================================

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from backend.agents.graph import get_agent_graph
from backend.db.user_store import save_message, get_recent_history
from backend.db.memory_store import store_memory
from backend.config import DEFAULT_MODEL_ID


def _history_to_lc(history: list[dict]) -> list[BaseMessage]:
    """Convert SQLite history rows to LangChain message objects."""
    msgs = []
    for r in history:
        if r["role"] == "user":
            msgs.append(HumanMessage(content=r["content"]))
        elif r["role"] == "assistant":
            msgs.append(AIMessage(content=r["content"]))
    return msgs


def _classify_intent(msg: str) -> str:
    """Simple keyword-based intent classifier for logging."""
    m = msg.lower()
    if any(k in m for k in ["email", "gmail", "inbox", "send mail"]):
        return "gmail"
    if any(k in m for k in ["run", "execute", "command", "shell", "script"]):
        return "system"
    if any(k in m for k in ["translate", "hindi", "tamil", "marathi", "bangla"]):
        return "sarvam"
    if any(k in m for k in ["speak", "say aloud", "audio", "voice out"]):
        return "tts"
    if any(k in m for k in ["research", "search", "look up", "latest", "news", "find"]):
        return "research"
    return "general"


def run_chat(
    user_id: int,
    username: str,
    user_message: str,
    model_id: str = DEFAULT_MODEL_ID,
    agent_mode: str = "default",
    gemini_api_key: str = "",
    openai_api_key: str = "",
    openrouter_api_key: str = "",
    sarvam_api_key: str = "",
) -> dict:
    """
    Run one full chat turn through the LangGraph agent.

    Returns dict with: reply, intent, model, steps, trace
    """
    # 1. Load recent history and append new message
    history = _history_to_lc(get_recent_history(user_id, limit=10))
    history.append(HumanMessage(content=user_message))
    intent = _classify_intent(user_message)

    # 2. Build initial graph state with all runtime keys
    initial_state = {
        "messages":           history,
        "username":           username,
        "model_id":           model_id,
        "agent_mode":         agent_mode,
        "iteration":          0,
        "gemini_api_key":     gemini_api_key,
        "openai_api_key":     openai_api_key,
        "openrouter_api_key": openrouter_api_key,
        "sarvam_api_key":     sarvam_api_key,
    }

    # 3. Run the LangGraph agent
    graph = get_agent_graph()
    final = graph.invoke(initial_state)
    steps = final.get("iteration", 0)

    # Minimal, safe trace (no hidden chain-of-thought): tool names + short result previews.
    trace: list[dict] = []
    for msg in final.get("messages", []):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in (msg.tool_calls or []):
                name = tc.get("name") if isinstance(tc, dict) else ""
                args = tc.get("args") if isinstance(tc, dict) else {}
                arg_keys = sorted(list(args.keys()))[:12] if isinstance(args, dict) else []
                trace.append({"type": "tool_call", "name": name, "arg_keys": arg_keys})
        elif isinstance(msg, ToolMessage):
            content = (msg.content or "").strip()
            trace.append({"type": "tool_result", "name": getattr(msg, "name", ""), "preview": content[:160]})

    # 4. Extract final AI reply
    reply = "I couldn't generate a response. Please try again."
    for msg in reversed(final["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break

    # 5. Persist to SQLite and Pinecone memory
    save_message(user_id, "user",      user_message, model_used=model_id)
    save_message(user_id, "assistant", reply,         model_used=model_id)
    store_memory(
        username=username,
        text=f"User: {user_message[:200]} | Agent: {reply[:300]}",
        metadata={"model": model_id, "intent": intent},
    )

    return {"reply": reply, "intent": intent, "model": model_id, "steps": steps, "trace": trace, "agent_mode": agent_mode}
