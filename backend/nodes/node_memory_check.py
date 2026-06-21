# backend/nodes/node_memory_check.py
# Checks if the current question can be answered from conversation history
# Prevents unnecessary web searches for follow-up questions

from agents.state import AgentState
from services.llm import call_llm
from langchain_core.messages import SystemMessage, HumanMessage

def memory_check_node(state: AgentState) -> AgentState:
    history    = state.get("chat_history", [])
    user_input = state.get("input", "").strip()

    # No history → must search
    if not history:
        return {**state, "from_memory": False, "memory_answer": ""}

    # ← FIX 1: never answer tool-type requests from memory
    ALWAYS_FRESH = [
        "image","picture","photo","draw","generate","create",
        "weather","temperature","calculate","compute","search","find"
    ]
    msg_lower = user_input.lower()
    if any(w in msg_lower for w in ALWAYS_FRESH):
        print(f"[MemCheck] Tool request → skipping memory")
        return {**state, "from_memory": False, "memory_answer": ""}

    # ← FIX 2: skip LLM for obviously fresh questions — saves 2-3 sec
    MEMORY_TRIGGERS = [
        "tell me more","explain more","elaborate","go on",
        "what about","and what","what else","anything else",
        "you said","you mentioned","you told","previously",
        "earlier","above","repeat","first point","second point",
        "summarize that","summary of that"
    ]
    is_followup = any(t in msg_lower for t in MEMORY_TRIGGERS)
    if not is_followup:
        print(f"[MemCheck] Fresh question → skipping LLM call")
        return {**state, "from_memory": False, "memory_answer": ""}

    # Build conversation pairs
    pairs = []
    temp_human = None
    for msg in history:
        role = getattr(msg, "type", "")
        if role == "human":
            temp_human = msg.content
        elif role == "ai" and temp_human:
            pairs.append(f"User: {temp_human}\nBot: {msg.content}")
            temp_human = None

    if not pairs:
        return {**state, "from_memory": False, "memory_answer": ""}

    history_text = "\n\n".join(pairs[-5:])

    prompt = f"""Conversation history:
{history_text}

New question: "{user_input}"

Can this new question be answered COMPLETELY AND ACCURATELY using ONLY the conversation history above?
- Answer YES only if the history contains enough information to give a complete answer.
- Answer NO if any new information, search, or tool would be needed.

Reply with:
- "YES: <your answer here>" if yes
- "NO" if no"""

    try:
        response = call_llm([
            SystemMessage(content="You decide if a question can be answered from conversation history."),
            HumanMessage(content=prompt)
        ]).strip()

        if response.upper().startswith("YES:"):
            answer = response[4:].strip()
            print(f"[MemCheck] Answered from memory ✅")
            return {**state, "from_memory": True, "memory_answer": answer, "output": answer}
        else:
            print(f"[MemCheck] Needs fresh lookup 🔍")
            return {**state, "from_memory": False, "memory_answer": ""}

    except Exception as e:
        print(f"[MemCheck] Error: {e} — proceeding to classify")
        return {**state, "from_memory": False, "memory_answer": ""}
