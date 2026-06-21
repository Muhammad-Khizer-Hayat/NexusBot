# backend/services/rag_service.py
# Sentence-transformer embeddings RAG (replaces TF-IDF)

import re
import numpy as np

_chunks: list = []
_embeddings: dict = {}   # chunk_id -> np.array
_model = None

# ── Load model once ────────────────────────────────────────────
def _get_model():
    global _model
    if _model is None:
        print("[RAG] Loading sentence-transformer model...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[RAG] Model ready ✅")
    return _model

# ── Chunking ───────────────────────────────────────────────────
def _chunk_text(text: str, size: int = 400, overlap: int = 80) -> list:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + size, len(words))
        c   = " ".join(words[start:end])
        if c.strip():
            chunks.append(c)
        if end == len(words):
            break
        start += size - overlap
    return chunks

# ── Cosine similarity ──────────────────────────────────────────
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0

# ── Public API ─────────────────────────────────────────────────
def add_document(filename: str, text: str) -> int:
    global _chunks, _embeddings
    model = _get_model()

    # Remove old chunks for this file
    _chunks     = [c for c in _chunks if c["filename"] != filename]
    _embeddings = {k: v for k, v in _embeddings.items() if not k.startswith(filename)}

    # Chunk and embed
    new_chunks = []
    for i, chunk_text in enumerate(_chunk_text(text)):
        cid = f"{filename}__chunk_{i}"
        new_chunks.append({"id": cid, "filename": filename, "text": chunk_text})

    if new_chunks:
        texts = [c["text"] for c in new_chunks]
        vecs  = model.encode(texts, show_progress_bar=False)
        for chunk, vec in zip(new_chunks, vecs):
            _embeddings[chunk["id"]] = vec
        _chunks.extend(new_chunks)

    count = len([c for c in _chunks if c["filename"] == filename])
    print(f"[RAG] Indexed '{filename}' → {count} chunks with embeddings")
    return count

def search(query: str, top_k: int = 4) -> list:
    if not _chunks:
        return []
    model     = _get_model()
    query_vec = model.encode([query], show_progress_bar=False)[0]

    scored = []
    for chunk in _chunks:
        vec   = _embeddings.get(chunk["id"])
        if vec is not None:
            score = _cosine(query_vec, vec)
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]

def get_document_list() -> list:
    seen, names = set(), []
    for c in _chunks:
        if c["filename"] not in seen:
            seen.add(c["filename"])
            names.append(c["filename"])
    return names

def remove_document(filename: str):
    global _chunks, _embeddings
    _chunks     = [c for c in _chunks if c["filename"] != filename]
    _embeddings = {k: v for k, v in _embeddings.items() if not k.startswith(filename)}

def has_documents() -> bool:
    return len(_chunks) > 0
