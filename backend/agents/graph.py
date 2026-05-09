# ============================================================
# backend/agents/graph.py  —  LangGraph Multi-Agent Graph
# ============================================================
from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from backend.agents.tools import ALL_TOOLS
from backend.utils.llm_factory import get_llm
from backend.config import DEFAULT_MODEL_ID, MAX_ITERATIONS


class AgentState(TypedDict):
    messages:           Annotated[Sequence[BaseMessage], add_messages]
    username:           str
    model_id:           str
    agent_mode:         str
    iteration:          int
    gemini_api_key:     str
    openai_api_key:     str
    openrouter_api_key: str
    sarvam_api_key:     str


def _system_prompt(username: str, memories: list[dict], agent_mode: str = "default") -> str:
    mem_block = ""
    if memories:
        lines = "\n".join(f"- [{m['timestamp'][:10]}] {m['text']}" for m in memories)
        mem_block = f"\n\n## Memories about {username}:\n{lines}"
    mode = (agent_mode or "default").lower().strip()
    mode_block = ""
    if mode in ("deep", "deepagent", "deep_agent"):
        mode_block = "\n\n## Mode: DeepAgent\n- Prefer deep_research for complex queries.\n- Synthesize into a concise, actionable answer.\n- Ask 1 clarifying question only if blocking."
    elif mode in ("web", "webagent", "web_agent"):
        mode_block = "\n\n## Mode: Web Agent\n- Prefer web_search for time-sensitive info.\n- Clearly separate verified facts vs assumptions."
    elif mode in ("resched", "reschedagent", "resched_agent"):
        mode_block = "\n\n## Mode: Resched Agent\n- Help reschedule tasks and plans.\n- Ask for constraints when missing.\n- Output a concrete schedule."
    return f"""You are NeuroAgent, an advanced AI assistant serving **{username}**.

## Available Tools:
- web_search — real-time web search via Tavily
- deep_research — comprehensive multi-pass research
- read_emails — read Gmail inbox
- send_gmail — send emails via Gmail
- execute_command — safe shell command execution
- calculator — evaluate math expressions
- sarvam_text_to_speech — generate Indian-language audio (Bulbul v2, 11 languages)
- sarvam_translate — translate between Indian languages (Mayura)
- summarise_text — condense long documents

## Instructions:
- Think step-by-step before acting.
- Use tools proactively when needed.
- For Indian language audio, use sarvam_text_to_speech.
- For translations involving Indian languages, use sarvam_translate.
- Keep responses concise and helpful.{mode_block}{mem_block}"""


def agent_node(state: AgentState) -> dict:
    model_id  = state.get("model_id",  DEFAULT_MODEL_ID)
    username  = state.get("username",  "user")
    agent_mode= state.get("agent_mode", "default")
    iteration = state.get("iteration", 0)

    if iteration >= MAX_ITERATIONS:
        return {
            "messages":  [AIMessage(content="Reached maximum reasoning steps. Here is my best answer based on available information.")],
            "iteration": iteration,
        }

    from backend.db.memory_store import retrieve_memories
    last_user_msg = ""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            last_user_msg = m.content
            break
    memories = retrieve_memories(username, last_user_msg, top_k=5) if last_user_msg else []

    try:
        llm = get_llm(
            model_id,
            gemini_api_key     = state.get("gemini_api_key",     ""),
            openai_api_key     = state.get("openai_api_key",     ""),
            openrouter_api_key = state.get("openrouter_api_key", ""),
        )
    except ValueError as e:
        return {
            "messages":  [AIMessage(content=f"⚠️ API key error: {str(e)}")],
            "iteration": iteration + 1,
        }

    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system_msg     = SystemMessage(content=_system_prompt(username, memories, agent_mode=agent_mode))

    try:
        response = llm_with_tools.invoke([system_msg] + list(state["messages"]))
    except Exception as e:
        return {
            "messages":  [AIMessage(content=f"⚠️ Model error: {str(e)}")],
            "iteration": iteration + 1,
        }

    return {"messages": [response], "iteration": iteration + 1}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_agent_graph():
    tool_node = ToolNode(ALL_TOOLS)
    builder   = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile()


_graph = None

def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
        print("[Agent] LangGraph graph compiled successfully.")
    return _graph
