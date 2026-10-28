# backend/routes/tts.py
# Natural neural voices (Microsoft Edge "Read Aloud" voices) through the edge-tts package.
# POST /api/tts  {text, lang, gender}  ->  audio/mpeg
import re, time, asyncio
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()

# language -> (female voices, male voices). The first voice is tried first, the next one is a fallback.
VOICES = {
    "en-US": (["en-US-AvaMultilingualNeural",    "en-US-JennyNeural"],
              ["en-US-AndrewMultilingualNeural", "en-US-GuyNeural"]),
    "ur-PK": (["ur-PK-UzmaNeural"],      ["ur-PK-AsadNeural"]),
    "ar-SA": (["ar-SA-ZariyahNeural"],   ["ar-SA-HamedNeural"]),
    "hi-IN": (["hi-IN-SwaraNeural"],     ["hi-IN-MadhurNeural"]),
    "bn-BD": (["bn-BD-NabanitaNeural"],  ["bn-BD-PradeepNeural"]),
    "fa-IR": (["fa-IR-DilaraNeural"],    ["fa-IR-FaridNeural"]),
    "tr-TR": (["tr-TR-EmelNeural"],      ["tr-TR-AhmetNeural"]),
    "es-ES": (["es-ES-ElviraNeural"],    ["es-ES-AlvaroNeural"]),
    "fr-FR": (["fr-FR-DeniseNeural"],    ["fr-FR-HenriNeural"]),
    "de-DE": (["de-DE-KatjaNeural"],     ["de-DE-ConradNeural"]),
    "it-IT": (["it-IT-ElsaNeural"],      ["it-IT-DiegoNeural"]),
    "pt-BR": (["pt-BR-FranciscaNeural"], ["pt-BR-AntonioNeural"]),
    "ru-RU": (["ru-RU-SvetlanaNeural"],  ["ru-RU-DmitryNeural"]),
    "zh-CN": (["zh-CN-XiaoxiaoNeural"],  ["zh-CN-YunxiNeural"]),
    "ja-JP": (["ja-JP-NanamiNeural"],    ["ja-JP-KeitaNeural"]),
    "ko-KR": (["ko-KR-SunHiNeural"],     ["ko-KR-InJoonNeural"]),
    "id-ID": (["id-ID-GadisNeural"],     ["id-ID-ArdiNeural"]),
}

MAX_CHARS       = 700      # longest text accepted per request
RATE_LIMIT      = 90       # requests allowed per IP ...
RATE_WINDOW_SEC = 60       # ... in this many seconds

_hits: dict = defaultdict(list)

class TTSBody(BaseModel):
    text:   str
    lang:   str = "en-US"
    gender: str = "female"
    rate:   str = "+0%"

def _ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")

def _limited(ip: str) -> bool:
    now = time.time()
    _hits[ip] = [t for t in _hits[ip] if t > now - RATE_WINDOW_SEC]
    if len(_hits[ip]) >= RATE_LIMIT:
        return True
    _hits[ip].append(now)
    return False

def _clean(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]

async def _synth(edge_tts, text: str, voice: str, rate: str) -> bytes:
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)

@router.post("/tts")
async def tts(body: TTSBody, request: Request):
    if _limited(_ip(request)):
        raise HTTPException(status_code=429, detail="Too many voice requests. Please slow down.")

    text = _clean(body.text)
    if not text:
        raise HTTPException(status_code=400, detail="No text to speak")

    lang = body.lang if body.lang in VOICES else "en-US"
    female, male = VOICES[lang]
    candidates = male if body.gender == "male" else female
    rate = body.rate if re.fullmatch(r"[+-]\d{1,2}%", body.rate or "") else "+0%"

    try:
        import edge_tts
    except ImportError:
        raise HTTPException(status_code=503, detail="edge-tts is not installed. Run: pip install edge-tts")

    last_err = None
    for voice in candidates:
        try:
            audio = await asyncio.wait_for(_synth(edge_tts, text, voice, rate), timeout=20)
            if audio:
                return Response(content=audio, media_type="audio/mpeg",
                                headers={"Cache-Control": "no-store", "X-TTS-Voice": voice})
        except Exception as e:
            last_err = e
            print(f"[TTS] {voice} failed: {e}")

    raise HTTPException(status_code=503, detail=f"Voice service unavailable: {last_err}")