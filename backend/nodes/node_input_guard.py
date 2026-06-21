# backend/nodes/node_input_guard.py
import re
from agents.state import AgentState

BLOCKED = ["ignore previous","forget instructions","jailbreak","act as dan","do anything now"]

def input_guard_node(state: AgentState) -> AgentState:
    user_input = state.get("input", "").strip()
    if not user_input:
        return {**state, "error": "Please type a message.", "is_safe": False}
    lower = user_input.lower()
    for b in BLOCKED:
        if b in lower:
            return {**state, "error": "I cannot process that request.", "is_safe": False}
    clean = re.sub(r'\s+', ' ', user_input).strip()
    print(f"[Node 1] Input: '{clean[:80]}'")
    return {**state, "input": clean, "is_safe": True, "error": None}