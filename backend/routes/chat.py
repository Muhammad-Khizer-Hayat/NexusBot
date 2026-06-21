# backend/routes/chat.py
import os, uuid, json
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from auth.auth_service import decode_token
from auth.database import (
    create_session, get_user_sessions, update_session_title,
    delete_session, save_message, get_session_messages, get_user_by_id
)
from agents.graph import get_graph
from agents.state import AgentState
from services.memory import clear_memory, load_history
from services.rag_service import add_document, get_document_list, remove_document, has_documents

router   = APIRouter()
security = HTTPBearer(auto_error=False)

# ── Pydantic models ────────────────────────────────────────────
class MessageItem(BaseModel):
    role: str
    content: str

class ChatBody(BaseModel):
    messages:   List[MessageItem] = []
    session_id: Optional[str] = None
    title:      Optional[str] = "New Chat"
    stream:     Optional[bool] = False   # ← NEW: opt-in streaming

# ── Auth helper ────────────────────────────────────────────────
def _get_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            return payload["user_id"], payload["username"]
    return 0, "guest"

def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore")
    if ext == "pdf":
        try:
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            return f"PDF error: {e}"
    return ""

def _build_state(messages, last_user, session_id, chat_history) -> AgentState:
    return {
        "messages":       messages,
        "input":          last_user,
        "original_input": last_user,
        "output":         "",
        "session_id":     session_id,
        "chat_history":   chat_history,
        "intent":         "",
        "tool_name":      "",
        "tool_input":     "",
        "tool_result":    "",
        "rag_chunks":     [],
        "has_docs":       has_documents(),
        "error":          None,
        "retry_count":    0,
        "needs_retry":    False,
        "is_safe":        True,
        "from_memory":    False,
        "memory_answer":  "",
    }

# ── Streaming generator ────────────────────────────────────────
async def _stream_response(result: dict):
    """
    Stream the bot response word-by-word using Server-Sent Events (SSE).
    The frontend receives tokens in real-time — like ChatGPT typing effect.
    """
    response  = result.get("output", "Sorry, I could not generate a response.")
    tool_used = result.get("tool_name", "")
    intent    = result.get("intent", "chat")
    is_weather = "[WEATHER_CARD]" in response and "[/WEATHER_CARD]" in response
    is_image   = "[IMAGE]" in response and "[/IMAGE]" in response

    # Send metadata first so frontend knows what kind of response is coming
    meta = {"type": "meta", "tool_used": tool_used, "intent": intent,
            "is_weather": is_weather, "is_image": is_image,
            "rag_active": has_documents()}
    yield f"data: {json.dumps(meta)}\n\n"

    # For images/weather — send as single event (now URL not base64)
    if is_weather or is_image or "[IMAGE]" in response:
        yield f"data: {json.dumps({'type': 'token', 'text': response})}\n\n"
    else:
        # Stream word by word with a small delay for the typing effect
        import asyncio
        words = response.split(" ")
        buffer = ""
        for i, word in enumerate(words):
            buffer += ("" if i == 0 else " ") + word
            # Send every 3 words as one chunk (smooth but not too many events)
            if (i + 1) % 3 == 0 or i == len(words) - 1:
                chunk = {"type": "token", "text": buffer}
                yield f"data: {json.dumps(chunk)}\n\n"
                buffer = ""
                await asyncio.sleep(0.02)  # 20ms per chunk → natural typing speed

    # Signal end of stream
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

# ── Chat ───────────────────────────────────────────────────────
@router.post("/chat")
async def chat(body: ChatBody, user_auth=Depends(_get_user)):
    user_id, username = user_auth
    messages   = [m.dict() for m in body.messages]
    session_id = body.session_id or f"guest_{uuid.uuid4().hex[:8]}"
    title      = body.title or "New Chat"
    do_stream  = body.stream or False

    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    if not last_user:
        raise HTTPException(status_code=400, detail="Empty message")

    if user_id:
        create_session(session_id, user_id, title)
        save_message(session_id, "user", last_user)
        db_messages = get_session_messages(session_id)
        messages    = db_messages

    chat_history  = load_history(session_id)
    initial_state = _build_state(messages, last_user, session_id, chat_history)

    print(f"\n{'='*50}")
    print(f"[Chat] user={username} session={session_id[:20]} stream={do_stream}")
    print(f"[Chat] input='{last_user[:80]}'")

    graph  = get_graph()
    result = graph.invoke(initial_state)

    response   = result.get("output", "Sorry, I could not generate a response.")
    tool_used  = result.get("tool_name", "")
    intent     = result.get("intent", "chat")
    is_weather = "[WEATHER_CARD]" in response and "[/WEATHER_CARD]" in response
    is_image   = "[IMAGE]" in response and "[/IMAGE]" in response
    db_response = "[Image was generated successfully]" if is_image else response

    if user_id:
        save_message(session_id, "assistant", db_response)
        if title == "New Chat" and last_user:
            new_title = last_user[:50] + ("…" if len(last_user) > 50 else "")
            update_session_title(session_id, new_title)

    print(f"[Chat] intent={intent} tool={tool_used} stream={do_stream}")
    print(f"[Chat] response ({len(response)} chars)")
    print(f"{'='*50}\n")

    # ── Stream response via SSE ────────────────────────────────
    if do_stream:
        return StreamingResponse(
            _stream_response(result),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",   # Disable Nginx buffering
            }
        )

    # ── Normal JSON response ───────────────────────────────────
    return {
        "response":   response,
        "rag_active": has_documents(),
        "tool_used":  tool_used,
        "intent":     intent,
        "is_weather": is_weather,
        "is_image":   is_image,
    }

# ── Sessions ───────────────────────────────────────────────────
@router.get("/sessions")
async def sessions(user_auth=Depends(_get_user)):
    user_id, _ = user_auth
    if not user_id:
        return {"sessions": []}
    return {"sessions": get_user_sessions(user_id)}

@router.get("/sessions/{session_id}")
async def session_messages(session_id: str, user_auth=Depends(_get_user)):
    user_id, _ = user_auth
    if not user_id:
        return {"messages": []}
    return {"messages": get_session_messages(session_id)}

@router.delete("/sessions/{session_id}")
async def delete_session_route(session_id: str, user_auth=Depends(_get_user)):
    user_id, _ = user_auth
    clear_memory(session_id)
    if user_id:
        delete_session(session_id)
    return {"success": True}

@router.post("/new-chat")
async def new_chat(request: Request):
    data       = await request.json()
    session_id = data.get("session_id", "")
    if session_id:
        clear_memory(session_id)
    return {"success": True}

# ── Image Upload for OCR ───────────────────────────────────────
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"}

@router.post("/upload-image")
async def upload_image(image: UploadFile = File(...)):
    if not image.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = image.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(status_code=400, detail="Only image files allowed")

    tmp_dir  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(tmp_dir, exist_ok=True)
    filepath = os.path.join(tmp_dir, uuid.uuid4().hex)

    contents = await image.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    from services.tools import ocr_image
    result = ocr_image(filepath)
    try:
        os.remove(filepath)
    except:
        pass

    return {"success": True, "text": result, "filename": image.filename}

# ── Documents ──────────────────────────────────────────────────
@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("txt", "pdf", "md"):
        raise HTTPException(status_code=400, detail="Only .txt .pdf .md allowed")

    contents = await file.read()
    text     = extract_text(file.filename, contents)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text")

    chunks = add_document(file.filename, text)
    return {
        "success":  True,
        "filename": file.filename,
        "chunks":   chunks,
        "message":  f"'{file.filename}' indexed into {chunks} chunks.",
    }

@router.get("/documents")
async def documents():
    return {"documents": get_document_list()}

@router.delete("/documents/{filename:path}")
async def delete_doc(filename: str):
    remove_document(filename)
    return {"success": True}

@router.get("/health")
async def health():
    return {"status": "NexusBot running (FastAPI)", "rag": has_documents()}

# ── Image Proxy ────────────────────────────────────────────────
@router.get("/image-proxy")
async def image_proxy(url: str):
    import httpx, urllib.parse
    from fastapi.responses import Response, RedirectResponse

    # If URL is a Pollinations URL, redirect browser directly to it
    # Browser requests are allowed by Pollinations, server requests are not
    if "pollinations.ai" in url:
        return RedirectResponse(url=url, status_code=302)

    from fastapi.responses import Response
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/*",
            })
        if resp.status_code == 200 and len(resp.content) > 1000:
            ctype = resp.headers.get("content-type", "image/jpeg")
            return Response(content=resp.content, media_type=ctype, headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            })
        return Response(content=b"", status_code=resp.status_code)
    except Exception as e:
        print(f"[Proxy] Error: {e}")
        return Response(content=b"", status_code=500)