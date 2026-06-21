# backend/agents/graph.py

from langgraph.graph import StateGraph, END
from agents.state import AgentState
from nodes.node_input_guard       import input_guard_node
from nodes.node_query_rewriter    import query_rewriter_node
from nodes.node_memory_check      import memory_check_node
from nodes.node_summarizer        import summarizer_node
from nodes.node_intent_classifier import intent_classifier_node
from nodes.node_react_agent       import react_agent_node
from nodes.node_rag               import rag_node
from nodes.node_chat              import chat_node
from nodes.node_clarify           import clarify_node
from nodes.node_formatter         import formatter_node
from nodes.node_memory            import memory_node
from nodes.node_output_guard      import output_guard_node

# ── Routing ────────────────────────────────────────────────────

def route_after_guard(state: AgentState) -> str:
    if not state.get("is_safe", True):
        return "end_unsafe"
    return "rewrite"                          # → rewriter first

def route_after_memory_check(state: AgentState) -> str:
    """If memory has the answer, skip classify → go straight to formatter."""
    if state.get("from_memory", False):
        print("[Graph] from_memory=True → formatter")
        return "formatter"
    return "classify"

def route_after_classify(state: AgentState) -> str:
    intent = (state.get("intent") or "").lower()
    print(f"[Graph] intent='{intent}' →", end=" ")

    if "tool" in intent or "weather" in intent:
        print("react"); return "react"

    elif intent == "rag":
        print("rag"); return "rag"

    elif intent == "clarify":
        print("clarify"); return "clarify"

    else:
        print("chat"); return "chat"

def route_after_output_guard(state: AgentState) -> str:
    retry = state.get("needs_retry", False)
    count = state.get("retry_count", 0)
    if retry and count < 2:
        return "retry"
    return "done"

# ── Build ──────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("input_guard",    input_guard_node)
    graph.add_node("rewrite",        query_rewriter_node)    # NEW
    graph.add_node("memory_check",   memory_check_node)
    graph.add_node("summarize",      summarizer_node)
    graph.add_node("classify",       intent_classifier_node)
    graph.add_node("react",          react_agent_node)
    graph.add_node("rag",            rag_node)
    graph.add_node("chat",           chat_node)
    graph.add_node("clarify",        clarify_node)
    graph.add_node("formatter",      formatter_node)
    graph.add_node("memory",         memory_node)
    graph.add_node("output_guard",   output_guard_node)

    graph.set_entry_point("input_guard")

    # Guard → rewriter
    graph.add_conditional_edges(
        "input_guard",
        route_after_guard,
        {"end_unsafe": END, "rewrite": "rewrite"}
    )

    # Rewriter → memory check
    graph.add_edge("rewrite",    "summarize")
    graph.add_edge("summarize",  "memory_check")

    # Memory check → formatter (if answered) OR classify (if needs search)
    graph.add_conditional_edges(
        "memory_check",
        route_after_memory_check,
        {"formatter": "formatter", "classify": "classify"}
    )

    # Classify → route to correct handler
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"react": "react", "rag": "rag", "chat": "chat", "clarify": "clarify"}
    )

    graph.add_edge("react",   "formatter")
    graph.add_edge("rag",     "formatter")
    graph.add_edge("chat",    "formatter")
    graph.add_edge("clarify", "formatter")

    graph.add_edge("formatter",    "memory")
    graph.add_edge("memory",       "output_guard")

    graph.add_conditional_edges(
        "output_guard",
        route_after_output_guard,
        {"retry": "classify", "done": END}
    )

    return graph.compile()

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        print("[NexusBot] ✅ LangGraph compiled successfully")
    return _graph