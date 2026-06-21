# backend/nodes/node_memory.py
from agents.state import AgentState
from services.memory import save_exchange

def _safe_output(output: str) -> str:
    """Strip base64 image data before saving to memory — prevents 413 on next LLM call."""
    if not output:
        return output
    # Replace full [IMAGE]...[/IMAGE] block with a short placeholder
    import re
    cleaned = re.sub(r'\[IMAGE\]data:[^[]{10,}\[/IMAGE\]', '[Image was generated]', output)
    # Also strip any raw base64 data URLs that leaked outside tags
    cleaned = re.sub(r'data:image/[a-z]+;base64,[A-Za-z0-9+/=]{100,}', '[image data]', cleaned)
    return cleaned

def memory_node(state: AgentState) -> AgentState:
    session = state.get("session_id", "default")
    inp     = state.get("input", "")
    out     = state.get("output", "")
    if inp and out:
        safe_out = _safe_output(out)
        save_exchange(session, inp, safe_out)
        print(f"[Node 4] Memory saved for session: {session}")
    return state