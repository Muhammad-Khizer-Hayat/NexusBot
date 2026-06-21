# backend/routes/auth.py
import os, re, time
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from auth.database import (
    create_user, get_user_by_email, get_user_by_username,
    get_user_by_google_id, get_user_by_id, update_last_login
)
from auth.auth_service import hash_password, verify_password, create_token, decode_token

router   = APIRouter()
security = HTTPBearer(auto_error=False)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ── Rate limiter (in-memory) ───────────────────────────────────
# Tracks failed login attempts per IP address
_fail_counts: dict = defaultdict(list)   # ip -> [timestamp, ...]
MAX_ATTEMPTS  = 5      # max failed attempts
LOCKOUT_SECS  = 900    # 15 minutes lockout

def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host

def _is_locked(ip: str) -> bool:
    now    = time.time()
    window = now - LOCKOUT_SECS
    # Keep only recent failures within the lockout window
    _fail_counts[ip] = [t for t in _fail_counts[ip] if t > window]
    return len(_fail_counts[ip]) >= MAX_ATTEMPTS

def _record_fail(ip: str):
    _fail_counts[ip].append(time.time())

def _clear_fails(ip: str):
    _fail_counts[ip] = []

# ── Pydantic models ────────────────────────────────────────────
class RegisterBody(BaseModel):
    username: str
    email:    Optional[str] = ""
    password: str

class LoginBody(BaseModel):
    username: str
    password: str

class GoogleBody(BaseModel):
    id_token: str

# ── Helper ─────────────────────────────────────────────────────
def _user_response(user, token):
    return {
        "token": token,
        "user": {
            "id":       user["id"],
            "username": user["username"],
            "email":    user["email"] or "",
            "avatar":   user["avatar"] or "",
        }
    }

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Login required")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")
    return payload

# ── Register ───────────────────────────────────────────────────
@router.post("/register", status_code=201)
async def register(body: RegisterBody):
    username = body.username.strip().lower()
    email    = (body.email or "").strip().lower()
    password = body.password

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Username already taken. Please choose another.")
    if email and get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered. Please login.")

    try:
        pw_hash = hash_password(password)
        user_id = create_user(username=username, email=email or None, password_hash=pw_hash)
        user    = get_user_by_id(user_id)
        token   = create_token(user_id, username)
        update_last_login(user_id)
        print(f"[Auth] ✅ Registered: {username} (id={user_id})")
        return _user_response(user, token)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        print(f"[Auth] Register error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")

# ── Login ──────────────────────────────────────────────────────
@router.post("/login")
async def login(request: Request, body: LoginBody):
    ip       = _get_ip(request)
    login_id = body.username.strip().lower()
    password = body.password

    print(f"[Auth] Login attempt: '{login_id}' from {ip}")

    # ── Rate limit check ───────────────────────────────────────
    if _is_locked(ip):
        remaining = LOCKOUT_SECS // 60
        print(f"[Auth] 🔒 IP locked: {ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {remaining} minutes."
        )

    if not login_id or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = get_user_by_username(login_id)
    if not user:
        user = get_user_by_email(login_id)

    if not user:
        _record_fail(ip)
        remaining_attempts = MAX_ATTEMPTS - len(_fail_counts[ip])
        print(f"[Auth] ❌ User not found: '{login_id}'")
        raise HTTPException(
            status_code=401,
            detail=f"Username or password is incorrect. {remaining_attempts} attempts remaining."
        )

    print(f"[Auth] Found user: {user['username']} (id={user['id']})")

    if not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="This account was created with Google. Please use Google Sign-In.")

    if not verify_password(password, user["password_hash"]):
        _record_fail(ip)
        remaining_attempts = MAX_ATTEMPTS - len(_fail_counts[ip])
        print(f"[Auth] ❌ Wrong password for: {user['username']}")
        raise HTTPException(
            status_code=401,
            detail=f"Username or password is incorrect. {remaining_attempts} attempts remaining."
        )

    # ── Success — clear fail count ─────────────────────────────
    _clear_fails(ip)
    token = create_token(user["id"], user["username"])
    update_last_login(user["id"])
    print(f"[Auth] ✅ Login success: {user['username']}")
    return _user_response(user, token)

# ── Google OAuth ───────────────────────────────────────────────
@router.post("/google")
async def google_login(body: GoogleBody):
    id_token = body.id_token

    if not id_token:
        raise HTTPException(status_code=400, detail="Google ID token required")

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail=(
            "Google OAuth not configured. Add GOOGLE_CLIENT_ID to your .env file."
        ))

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        idinfo    = google_id_token.verify_oauth2_token(id_token, google_requests.Request(), GOOGLE_CLIENT_ID)
        google_id = idinfo["sub"]
        email     = idinfo.get("email", "")
        name      = idinfo.get("name", "")
        picture   = idinfo.get("picture", "")

        username = re.sub(r'[^a-z0-9_]', '', name.lower().replace(" ", "_"))[:20]
        if not username:
            username = f"user_{google_id[:8]}"

        user = get_user_by_google_id(google_id)

        if not user:
            if email and get_user_by_email(email):
                raise HTTPException(status_code=409, detail="This email is already registered with a password account.")
            base, counter = username, 1
            while get_user_by_username(username):
                username = f"{base}{counter}"
                counter += 1
            user_id = create_user(username=username, email=email, google_id=google_id, avatar=picture)
            user    = get_user_by_id(user_id)
            print(f"[Auth] ✅ Google registered: {username}")

        token = create_token(user["id"], user["username"])
        update_last_login(user["id"])
        print(f"[Auth] ✅ Google login: {user['username']}")
        return _user_response(user, token)

    except ImportError:
        raise HTTPException(status_code=500, detail="Missing package. Run: pip install google-auth")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] ❌ Google error: {e}")
        raise HTTPException(status_code=401, detail=f"Google sign-in failed: {str(e)}")

# ── Me ─────────────────────────────────────────────────────────
@router.get("/me")
async def me(user=Depends(get_current_user)):
    db_user = get_user_by_id(user["user_id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id":       db_user["id"],
        "username": db_user["username"],
        "email":    db_user["email"] or "",
        "avatar":   db_user["avatar"] or "",
        "joined":   db_user["created_at"],
    }

# ── /debug route REMOVED ───────────────────────────────────────
# Previously exposed whether any username existed publicly.
# Removed for security.

# ── User Preferences ───────────────────────────────────────────
from pydantic import BaseModel as _BM

class PrefBody(_BM):
    key:   str
    value: str

@router.get("/preferences")
async def get_prefs(user=Depends(get_current_user)):
    from auth.database import get_preferences
    return {"preferences": get_preferences(user["user_id"])}

@router.post("/preferences")
async def save_pref(body: PrefBody, user=Depends(get_current_user)):
    from auth.database import save_preference
    save_preference(user["user_id"], body.key, body.value)
    return {"success": True}