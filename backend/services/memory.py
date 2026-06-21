# backend/services/memory.py
# Per-session conversation memory — persisted to SQLite so it survives server restarts

import sqlite3, os
from langchain.memory import ConversationBufferWindowMemory

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nexusbot.db")

# In-memory cache — avoids hitting SQLite on every single message
_store: dict = {}

# ── DB setup ───────────────────────────────────────────────────
def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_table():
    conn = _get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS memory_store (
        session_id TEXT NOT NULL,
        role       TEXT NOT NULL,
        content    TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_store(session_id)")
    conn.commit()
    conn.close()

_ensure_table()

# ── DB read / write ────────────────────────────────────────────
def _save_to_db(session_id: str, human: str, ai: str):
    conn = _get_db()
    conn.execute(
        "INSERT INTO memory_store (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "human", human)
    )
    conn.execute(
        "INSERT INTO memory_store (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "ai", ai)
    )
    conn.commit()
    conn.close()

def _load_from_db(session_id: str) -> ConversationBufferWindowMemory:
    """Restore session history from SQLite into a LangChain memory object."""
    mem = ConversationBufferWindowMemory(
        k=10,
        memory_key="chat_history",
        return_messages=True,
    )
    conn = _get_db()
    rows = conn.execute(
        "SELECT role, content FROM memory_store WHERE session_id=? ORDER BY rowid ASC",
        (session_id,)
    ).fetchall()
    conn.close()

    # Rebuild human→ai pairs and feed into memory
    temp = None
    for row in rows:
        if row["role"] == "human":
            temp = row["content"]
        elif row["role"] == "ai" and temp is not None:
            mem.save_context({"input": temp}, {"output": row["content"]})
            temp = None

    return mem

# ── Public API ─────────────────────────────────────────────────
def get_memory(session_id: str) -> ConversationBufferWindowMemory:
    if session_id not in _store:
        # Restore from DB on first access (survives server restarts)
        _store[session_id] = _load_from_db(session_id)
        print(f"[Memory] Restored session from DB: {session_id[:20]}")
    return _store[session_id]

def save_exchange(session_id: str, human: str, ai: str):
    """Save to both in-memory cache AND SQLite DB."""
    get_memory(session_id).save_context({"input": human}, {"output": ai})
    _save_to_db(session_id, human, ai)
    print(f"[Memory] Persisted exchange for session: {session_id[:20]}")

def load_history(session_id: str) -> list:
    mem  = get_memory(session_id)
    vars = mem.load_memory_variables({})
    return vars.get("chat_history", [])

def clear_memory(session_id: str):
    """Clear from both cache and DB."""
    if session_id in _store:
        del _store[session_id]
    conn = _get_db()
    conn.execute("DELETE FROM memory_store WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    print(f"[Memory] Cleared session: {session_id[:20]}")
