# backend/nodes/node_react_agent.py
from agents.state import AgentState
from services.tools import TOOL_REGISTRY

def react_agent_node(state: AgentState) -> AgentState:
    tool_name  = state.get("tool_name", "")
    tool_input = state.get("tool_input", "")

    if tool_name and tool_input and tool_name in TOOL_REGISTRY:
        print(f"[Node 3a] Running: {tool_name}('{tool_input}')")
        try:
            result = TOOL_REGISTRY[tool_name](tool_input)
            result_str = str(result)
            print(f"[Node 3a] Result ({len(result_str)} chars): {result_str[:200]}")
            return {**state, "tool_result": result_str}
        except Exception as e:
            print(f"[Node 3a] Tool error: {e}")
            return {**state, "tool_result": f"Tool error: {str(e)}"}

    print("[Node 3a] No tool → chat")
    return {**state, "tool_result": ""}