# backend/nodes/node_rag.py
from agents.state import AgentState
from services.rag_service import search, has_documents

def rag_node(state: AgentState) -> AgentState:
    if not has_documents():
        print("[Node 3b] No documents")
        return {**state, "rag_chunks": [], "tool_result": "No documents uploaded yet."}
    chunks = search(state["input"], top_k=4)
    if not chunks:
        print("[Node 3b] No relevant chunks")
        return {**state, "rag_chunks": [], "tool_result": "No relevant content in documents."}
    context = "\n\n".join(f"[{c['filename']}]:\n{c['text']}" for c in chunks)
    print(f"[Node 3b] Found {len(chunks)} chunks")
    return {**state, "rag_chunks": chunks, "tool_result": context}