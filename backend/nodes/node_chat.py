# backend/nodes/node_chat.py
from agents.state import AgentState
from services.llm import call_llm
from services.memory import load_history
from prompts import get_chat_system, get_diagram_prompt
from langchain_core.messages import SystemMessage, HumanMessage

import re

def _sanitize_history(history: list) -> list:
    """Remove any base64 image data from history messages before sending to LLM."""
    clean = []
    for msg in history:
        content = getattr(msg, "content", "")
        if not content:
            clean.append(msg)
            continue
        # Replace image blocks with a short placeholder
        sanitized = re.sub(r'\[IMAGE\]data:[^[]{10,}\[/IMAGE\]', '[Image was generated]', content)
        sanitized = re.sub(r'data:image/[a-z]+;base64,[A-Za-z0-9+/=]{100,}', '[image data]', sanitized)
        if sanitized != content:
            # Rebuild the message with cleaned content
            msg = msg.__class__(content=sanitized)
        clean.append(msg)
    return clean

def chat_node(state: AgentState) -> AgentState:
    session = state.get("session_id", "default")

    # Prefer pre-loaded history from state, fallback to loading fresh
    raw_history = state.get("chat_history") or load_history(session)
    history = _sanitize_history(raw_history)

    rag_ctx = ""
    if state.get("rag_chunks") and state.get("tool_result"):
        rag_ctx = state["tool_result"]

    # Use diagram-specific prompt if user asked for flowchart/diagram
    user_input = state.get("input", "").lower()
    DIAGRAM_WORDS = ["flowchart","flow chart","diagram","sequence diagram",
                     "uml","er diagram","class diagram","mindmap","workflow diagram"]
    if any(w in user_input for w in DIAGRAM_WORDS):
        system = get_diagram_prompt()
    else:
        system = get_chat_system(rag_context=rag_ctx)

    # Keep last 6 messages only — prevents 413 token limit errors
    messages = [SystemMessage(content=system)] + history[-6:] + [HumanMessage(content=state["input"])]

    print(f"[Node 3c] Chat (history={len(history)})")
    return {**state, "output": call_llm(messages)}