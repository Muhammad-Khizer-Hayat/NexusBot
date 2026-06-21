# backend/auth/database.py
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nexusbot.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    UNIQUE NOT NULL,
        email         TEXT    UNIQUE,
        password_hash TEXT,
        google_id     TEXT    UNIQUE,
        avatar        TEXT    DEFAULT '',
        created_at    TEXT    DEFAULT (datetime('now')),
        last_login    TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
        id         TEXT    PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        title      TEXT    DEFAULT 'New Chat',
        created_at TEXT    DEFAULT (datetime('now')),
        updated_at TEXT    DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT    NOT NULL,
        role       TEXT    NOT NULL,
        content    TEXT    NOT NULL,
        created_at TEXT    DEFAULT (datetime('now')),
        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()
    print(f"[DB] Ready: {DB_PATH}")

def _row(r): return dict(r) if r else None

def create_user(username, email=None, password_hash=None, google_id=None, avatar=""):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO users (username,email,password_hash,google_id,avatar) VALUES (?,?,?,?,?)",
                  (username, email, password_hash, google_id, avatar))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError as e:
        raise ValueError(str(e))
    finally:
        conn.close()

def get_user_by_id(uid):
    conn=get_db(); c=conn.cursor(); c.execute("SELECT * FROM users WHERE id=?",(uid,)); r=_row(c.fetchone()); conn.close(); return r
def get_user_by_email(email):
    conn=get_db(); c=conn.cursor(); c.execute("SELECT * FROM users WHERE email=?",(email,)); r=_row(c.fetchone()); conn.close(); return r
def get_user_by_username(username):
    conn=get_db(); c=conn.cursor(); c.execute("SELECT * FROM users WHERE username=?",(username,)); r=_row(c.fetchone()); conn.close(); return r
def get_user_by_google_id(gid):
    conn=get_db(); c=conn.cursor(); c.execute("SELECT * FROM users WHERE google_id=?",(gid,)); r=_row(c.fetchone()); conn.close(); return r
def update_last_login(uid):
    conn=get_db(); conn.execute("UPDATE users SET last_login=datetime('now') WHERE id=?",(uid,)); conn.commit(); conn.close()

def create_session(sid, user_id, title="New Chat"):
    conn=get_db(); conn.execute("INSERT OR IGNORE INTO chat_sessions (id,user_id,title) VALUES (?,?,?)",(sid,user_id,title)); conn.commit(); conn.close()
def get_user_sessions(user_id):
    conn=get_db(); c=conn.cursor(); c.execute("SELECT * FROM chat_sessions WHERE user_id=? ORDER BY updated_at DESC",(user_id,)); rows=[dict(r) for r in c.fetchall()]; conn.close(); return rows
def update_session_title(sid, title):
    conn=get_db(); conn.execute("UPDATE chat_sessions SET title=?,updated_at=datetime('now') WHERE id=?",(title,sid)); conn.commit(); conn.close()
def delete_session(sid):
    conn=get_db(); conn.execute("DELETE FROM chat_sessions WHERE id=?",(sid,)); conn.commit(); conn.close()

def save_message(sid, role, content):
    conn=get_db(); conn.execute("INSERT INTO chat_messages (session_id,role,content) VALUES (?,?,?)",(sid,role,content)); conn.execute("UPDATE chat_sessions SET updated_at=datetime('now') WHERE id=?",(sid,)); conn.commit(); conn.close()
def get_session_messages(sid):
    conn=get_db(); c=conn.cursor(); c.execute("SELECT role,content FROM chat_messages WHERE session_id=? ORDER BY id ASC",(sid,)); rows=[{"role":r["role"],"content":r["content"]} for r in c.fetchall()]; conn.close(); return rows
def delete_session_messages(sid):
    conn=get_db(); conn.execute("DELETE FROM chat_messages WHERE session_id=?",(sid,)); conn.commit(); conn.close()
# ── User Preferences ───────────────────────────────────────────
def save_preference(user_id: int, key: str, value: str):
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER NOT NULL,
        key     TEXT NOT NULL,
        value   TEXT NOT NULL,
        PRIMARY KEY (user_id, key)
    )""")
    conn.execute(
        "INSERT INTO user_preferences (user_id, key, value) VALUES (?,?,?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
        (user_id, key, value)
    )
    conn.commit()
    conn.close()

def get_preferences(user_id: int) -> dict:
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER NOT NULL,
        key     TEXT NOT NULL,
        value   TEXT NOT NULL,
        PRIMARY KEY (user_id, key)
    )""")
    rows = conn.execute(
        "SELECT key, value FROM user_preferences WHERE user_id=?", (user_id,)
    ).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}