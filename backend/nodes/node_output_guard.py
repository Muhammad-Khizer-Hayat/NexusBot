# backend/nodes/node_output_guard.py
import time
from agents.state import AgentState

def output_guard_node(state: AgentState) -> AgentState:
    output      = state.get("output", "")
    retry_count = state.get("retry_count", 0)

    if not state.get("is_safe", True):
        return {**state, "output": state.get("error","I cannot process that."), "needs_retry": False}

    if not output:
        if retry_count < 2:
            print(f"[Node 6] Empty output, retry {retry_count+1}")
            return {**state, "needs_retry": True, "retry_count": retry_count+1,
                    "output":"","tool_result":"","tool_name":"","tool_input":""}
        return {**state, "output":"Sorry, I could not generate a response.", "needs_retry": False}

    if "rate limit" in output.lower() and retry_count < 2:
        print(f"[Node 6] Rate limit, waiting 30s...")
        time.sleep(30)
        return {**state, "needs_retry": True, "retry_count": retry_count+1, "output":"","tool_result":""}

    print(f"[Node 6] Output OK ({len(output)} chars)")
    return {**state, "needs_retry": False}