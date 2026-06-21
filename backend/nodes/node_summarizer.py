# backend/nodes/node_summarizer.py
# Auto-summarizes long conversations to prevent token overflow

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agents.state import AgentState
from services.llm import call_llm

MAX_HISTORY = 20   # messages before summarizing

def summarizer_node(state: AgentState) -> AgentState:
    history = state.get("chat_history", [])

    if len(history) <= MAX_HISTORY:
        return state  # Not long enough — skip

    print(f"[Summarizer] History too long ({len(history)} msgs) — summarizing...")

    # Keep last 6 messages as recent context
    old_msgs  = history[:-6]
    recent    = history[-6:]

    # Build summary of old messages
    convo_text = ""
    for msg in old_msgs:
        if isinstance(msg, HumanMessage):
            convo_text += f"User: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            convo_text += f"Assistant: {msg.content}\n"

    summary_prompt = [
        SystemMessage(content="You are a conversation summarizer. Create a concise summary."),
        HumanMessage(content=f"""Summarize this conversation in 3-5 sentences, keeping key facts:

{convo_text[:3000]}

Summary:""")
    ]

    summary = call_llm(summary_prompt)
    print(f"[Summarizer] Summary: {summary[:100]}...")

    # Create a synthetic summary message
    summary_msg = AIMessage(content=f"[Previous conversation summary: {summary}]")

    # Replace old history with summary + recent
    new_history = [summary_msg] + list(recent)

    return {**state, "chat_history": new_history}