# backend/agents/state.py
# Shared state passed between ALL LangGraph nodes
# IMPORTANT: field names here must match exactly what nodes return

from typing import TypedDict, Annotated, List, Optional
import operator

class AgentState(TypedDict):
    # ── Core conversation ──────────────────────────────────────
    messages:      Annotated[List[dict], operator.add]  # full chat history
    input:         str                                   # latest user message (may be rewritten)
    original_input: str                                  # raw user message before rewrite
    output:        str                                   # final bot response
    session_id:    str                                   # unique per session

    # ── Memory / History ───────────────────────────────────────
    chat_history:  List                                  # loaded LangChain memory messages

    # ── Routing ────────────────────────────────────────────────
    intent:        str   # "tool" | "weather" | "rag" | "chat" | "clarify"
    tool_name:     str   # e.g. "web_search", "weather", "calculate"
    tool_input:    str   # input passed to the tool
    tool_result:   str   # result returned by the tool

    # ── RAG ────────────────────────────────────────────────────
    rag_chunks:    List[dict]   # retrieved document chunks
    has_docs:      bool         # are any documents uploaded?

    # ── Control flow ───────────────────────────────────────────
    error:         Optional[str]   # error message if any
    retry_count:   int             # number of retries so far
    needs_retry:   bool            # should graph retry?
    is_safe:       bool            # passed safety check?
    from_memory:   bool            # was this answered from memory?
    memory_answer: str             # answer from memory if available
