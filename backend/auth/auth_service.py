# backend/auth/auth_service.py
import os
import bcrypt
import jwt
from datetime import datetime, timedelta

_default_secret = "nexusbot-jwt-secret-key-minimum-32-chars-long-2024"
SECRET    = os.getenv("JWT_SECRET", _default_secret)
ALGORITHM = "HS256"
EXPIRY_H  = 72  # 3 days

if len(SECRET) < 32:
    SECRET = SECRET + "0" * (32 - len(SECRET))

# ── Password hashing (bcrypt) ──────────────────────────────────
def hash_password(password: str) -> str:
    """Hash password using bcrypt (slow + salted = secure)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain password against bcrypt hash.
    Also handles old SHA-256 hashes for backwards compatibility."""
    try:
        # bcrypt hashes always start with $2b$ or $2a$
        if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        else:
            # Legacy SHA-256 — still verify, but user should re-register
            import hashlib
            return hashlib.sha256(plain.encode("utf-8")).hexdigest() == hashed
    except Exception as e:
        print(f"[Auth] Password verify error: {e}")
        return False

# ── JWT ────────────────────────────────────────────────────────
def create_token(user_id: int, username: str) -> str:
    """Create JWT token for user."""
    payload = {
        "user_id":  user_id,
        "username": username,
        "exp":      datetime.utcnow() + timedelta(hours=EXPIRY_H),
        "iat":      datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """Decode and verify JWT token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        print("[Auth] Token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[Auth] Invalid token: {e}")
        return None
    except Exception as e:
        print(f"[Auth] Token error: {e}")
        return None
