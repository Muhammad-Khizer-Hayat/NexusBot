import re, requests
from bs4 import BeautifulSoup
import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import base64, time, random
from ddgs import DDGS



HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# EASYOCR INIT (LOAD ONCE)
_ocr_reader = None
def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        print("[OCR] Loading EasyOCR model...")
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
        print("[OCR] Model ready")
    return _ocr_reader

def _rewrite_query(query: str) -> list:
    q  = query.strip()
    ql = q.lower()
    queries = [q]
    if re.search(r'top\s+\d*\s*(software|tech|it|companies)', ql):
        country = ""
        for c in ["pakistan","india","usa","uk","china","uae"]:
            if c in ql:
                country = c.title(); break
        if country:
            queries.append(f"best software companies in {country} 2024 list")
            queries.append(f"{country} software houses top ranked")
    elif any(w in ql for w in ["founder","ceo","owner","chairman"]):
        queries.append(q + " LinkedIn"); queries.append(q + " Crunchbase")
    elif any(w in ql for w in ["latest","news","recent","today"]):
        queries.append(q + " 2024 2025")
    return queries[:3]

def _scrape(url: str, max_chars: int = 2000) -> str:
    try:
        res  = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","iframe","noscript","form","button"]):
            tag.decompose()
        lines = []
        for elem in soup.find_all(["p","h1","h2","h3","h4","li","td","article"]):
            t = elem.get_text(" ", strip=True)
            if len(t) > 40:
                lines.append(t)
        return "\n".join(lines)[:max_chars]
    except:
        return ""
#------------------------Web Search-----------------
def web_search(query: str, max_results: int = 6) -> str:
    try:
        queries = _rewrite_query(query)
        all_results = {}
        with DDGS() as ddgs:
            for q in queries:
                for r in ddgs.text(q, max_results=max_results):
                    url  = r.get("href","")
                    skip = ["youtube.com","reddit.com","twitter.com","facebook.com","instagram.com","tiktok.com"]
                    if url and url not in all_results and not any(s in url for s in skip):
                        all_results[url] = {"title": r.get("title",""), "body": r.get("body",""), "query": q}
        if not all_results:
            return "No search results found."
        output = f"=== Search results for: '{query}' ===\n\n"
        for url, r in list(all_results.items())[:8]:
            output += f"• {r['title']}\n  {r['body']}\n  Source: {url}\n\n"
        scraped = []
        priority_domains = ["pasha.org.pk","crunchbase.com","dawn.com","tribune.com.pk","techjuice.com","propakistani.pk","profit.pakistantoday.com.pk"]
        urls_to_scrape = list(all_results.keys())
        priority_urls  = [u for u in urls_to_scrape if any(d in u for d in priority_domains)]
        other_urls     = [u for u in urls_to_scrape if u not in priority_urls]
        for url in (priority_urls + other_urls)[:4]:
            content = _scrape(url, max_chars=1800)
            if content and len(content) > 100:
                scraped.append(f"--- Content from: {url} ---\n{content}")
        if scraped:
            output += "\n=== Detailed content ===\n\n" + "\n\n".join(scraped)
        return output
    except Exception as e:
        return f"Search failed: {str(e)}" 
    
    #---------------------Scrap Url-----------------------

def scrape_url(url: str, max_chars: int = 3000) -> str:
    login_patterns = ["/dashboard","/login","/account","/portal","/admin","/signin","/profile","/app/"]
    if any(p in url.lower() for p in login_patterns):
        return f"Cannot access '{url}' — login required."
    result = _scrape(url, max_chars)
    return result if result else f"Could not read content from: {url}"

#--------------------- Wikipedia----------------------

def wikipedia_search(query: str, sentences: int = 10) -> str:
    try:
        s = requests.get("https://en.wikipedia.org/w/api.php",
            params={"action":"query","format":"json","list":"search","srsearch":query,"srlimit":1},
            headers=HEADERS, timeout=15)
        results = s.json().get("query",{}).get("search",[])
        if not results:
            return f"No Wikipedia article found for '{query}'."
        title = results[0]["title"]
        e = requests.get("https://en.wikipedia.org/w/api.php",
            params={"action":"query","format":"json","titles":title,"prop":"extracts",
                    "exintro":False,"explaintext":True,"exsentences":sentences,"redirects":1},
            headers=HEADERS, timeout=15)
        pages   = e.json().get("query",{}).get("pages",{})
        extract = next(iter(pages.values())).get("extract","").strip()
        return extract[:3000] if extract else "No content found."
    except Exception as e:
        return f"Wikipedia failed: {str(e)}"
    
    #-------------------------------Weather Search Tool----------------

def get_weather(city: str) -> str:
    # Primary: wttr.in
    try:
        url  = f"https://wttr.in/{city}"
        resp = requests.get(url, params={"format": "j1"}, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data      = resp.json()
        current   = data["current_condition"][0]
        area      = data.get("nearest_area", [{}])[0]
        city_name = area.get("areaName", [{}])[0].get("value", city)
        country   = area.get("country",  [{}])[0].get("value", "")
        return (
            f"Weather in {city_name}, {country}:\n"
            f"Condition: {current.get('weatherDesc',[{}])[0].get('value','Clear')}\n"
            f"Temperature: {current.get('temp_C','0')}°C\n"
            f"Feels like: {current.get('FeelsLikeC','0')}°C\n"
            f"Humidity: {current.get('humidity','0')}%\n"
            f"Wind: {current.get('windspeedKmph','0')} km/h"
        )
    except Exception as e:
        print(f"[Weather] wttr.in failed: {e} — trying open-meteo")

    # Fallback: open-meteo
    try:
        geo = requests.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json",
            timeout=10).json()
        if not geo.get("results"):
            return f"City '{city}' not found."
        loc = geo["results"][0]
        w = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={loc['latitude']}&longitude={loc['longitude']}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weathercode,apparent_temperature"
            f"&temperature_unit=celsius", timeout=10).json()["current"]
        code_map = {
            0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
            45:"Foggy",51:"Light drizzle",53:"Drizzle",61:"Light rain",
            63:"Rain",65:"Heavy rain",71:"Light snow",73:"Snow",
            80:"Light showers",81:"Showers",95:"Thunderstorm",
        }
        return (
            f"Weather in {loc['name']}, {loc.get('country','')}:\n"
            f"Condition: {code_map.get(w.get('weathercode',0),'Clear')}\n"
            f"Temperature: {w['temperature_2m']}°C\n"
            f"Feels like: {w['apparent_temperature']}°C\n"
            f"Humidity: {w['relative_humidity_2m']}%\n"
            f"Wind: {w['wind_speed_10m']} km/h"
        )
    except Exception as e:
        return f"Weather failed: {str(e)}"
    
    #----------------------- Calculator tool For Problem  Solving of Mathematics---------------------

def calculate(expression: str) -> str:
    try:
        expr = expression.lower().strip()
        m = re.search(r'(\d+\.?\d*)\s*%\s*of\s*(\d+\.?\d*)', expr)
        if m:
            p, n = float(m.group(1)), float(m.group(2))
            return f"{p}% of {n} = {n * p / 100}"
        safe = re.sub(r'[^0-9+\-*/().,\s]','', expression).replace("^","**").strip()
        return f"{expression} = {eval(safe,{'__builtins__':{}},{})}"
    except Exception as e:
        return f"Calculation error: {str(e)}"
    

# IMAGE GENERATION — Pollinations.ai with base64 conversion---------

def generate_image(prompt: str) -> str:
    """
    Generate image.
    Priority:
      1. Stability AI (free 25/month) — add STABILITY_KEY to .env
      2. Together AI  (free $1 credit) — add TOGETHER_KEY to .env
      3. Pollinations direct URL (browser loads it — free, no key)
    """
    import os, base64, json

    if not prompt:
        return "IMAGE_ERROR: Please describe what to generate."

    enhanced = f"{prompt}, highly detailed, high quality, 4k, sharp focus"
    seed     = random.randint(1, 99999)
    print(f"[ImageGen] Prompt: '{prompt}' seed={seed}")

    STABILITY_KEY = os.getenv("STABILITY_KEY", "")
    TOGETHER_KEY  = os.getenv("TOGETHER_KEY",  "")

    def _b64(content, ctype="image/png"):
        ext = "png" if "png" in ctype else "jpeg"
        b64 = base64.b64encode(content).decode("utf-8")
        return f"IMAGE_URL:data:image/{ext};base64,{b64}"

    # ── Provider 1: Stability AI — save to file, serve as URL ────
    if STABILITY_KEY:
        try:
            resp = requests.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={
                    "Authorization": f"Bearer {STABILITY_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "text_prompts": [{"text": enhanced, "weight": 1}],
                    "cfg_scale": 7, "height": 1024, "width": 1024,
                    "steps": 30, "samples": 1, "seed": seed,
                },
                timeout=60
            )
            print(f"[ImageGen] Stability: status={resp.status_code} size={len(resp.content)}")
            if resp.status_code == 200:
                import base64 as _b64, pathlib
                data   = resp.json()
                b64img = data["artifacts"][0]["base64"]
                # Save to static folder — serve as URL instead of embedding base64
                static_dir = pathlib.Path(__file__).parent.parent / "static" / "images"
                static_dir.mkdir(parents=True, exist_ok=True)
                filename = f"img_{seed}.png"
                filepath = static_dir / filename
                with open(filepath, "wb") as f:
                    f.write(_b64.b64decode(b64img))
                print(f"[ImageGen] ✅ Stability AI — saved to {filename}")
                return f"IMAGE_DIRECT_URL:http://127.0.0.1:8000/static/images/{filename}"
        except Exception as e:
            print(f"[ImageGen] Stability error: {e}")

    # ── Provider 2: Together AI ────────────────────────────────────
    if TOGETHER_KEY:
        try:
            resp = requests.post(
                "https://api.together.xyz/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {TOGETHER_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "stabilityai/stable-diffusion-xl-base-1.0",
                    "prompt": enhanced,
                    "n": 1, "width": 512, "height": 512,
                },
                timeout=60
            )
            print(f"[ImageGen] Together: status={resp.status_code}")
            if resp.status_code == 200:
                data    = resp.json()
                img_url = data["data"][0].get("url", "")
                if img_url:
                    img = requests.get(img_url, timeout=30)
                    if img.status_code == 200:
                        print(f"[ImageGen] ✅ Together AI success")
                        return _b64(img.content, "image/png")
        except Exception as e:
            print(f"[ImageGen] Together error: {e}")

    # ── Provider 3: Pollinations direct browser URL ────────────────
    encoded   = requests.utils.quote(enhanced)
    image_url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true&seed={seed}&width=1024&height=1024"
    print(f"[ImageGen] Using Pollinations direct URL (browser loads it)")
    return f"IMAGE_DIRECT_URL:{image_url}"


# OCR
def ocr_image(image_path: str) -> str:
    try:
        img    = Image.open(image_path).convert("RGB")
        img    = img.convert("L")
        img    = ImageEnhance.Contrast(img).enhance(2.5)
        img    = img.filter(ImageFilter.SHARPEN)
        w, h   = img.size
        img    = img.resize((w * 2, h * 2))
        img_np = np.array(img)
        reader = _get_ocr_reader()
        result = reader.readtext(img_np, detail=1)
        if not result:
            return "No readable text found. Try a clearer image."
        filtered = [text for (_, text, conf) in result if conf > 0.30]
        if not filtered:
            return "Text detected but confidence too low. Try a clearer image."
        return "\n".join(filtered)
    except Exception as e:
        return f"OCR failed: {str(e)}"

TOOL_REGISTRY = {
    "web_search":     web_search,
    "scrape":         scrape_url,
    "wikipedia":      wikipedia_search,
    "weather":        get_weather,
    "calculate":      calculate,
    "ocr":            ocr_image,
    "generate_image": generate_image,
}

# ══════════════════════════════════════════════════════════════
# NEW TOOLS
# ══════════════════════════════════════════════════════════════

# ── 1. Currency Converter ──────────────────────────────────────
def currency_convert(query: str) -> str:
    """Convert currency. Query format: '100 USD to PKR' or '50 EUR to GBP'"""
    try:
        query = query.strip()
        m = re.search(
            r'([\d,]+(?:\.\d+)?)\s*([A-Za-z]{3})\s*(?:to|in|into|=|→)\s*([A-Za-z]{3})',
            query, re.IGNORECASE
        )
        if not m:
            return "Format: '100 USD to PKR' or '50 EUR to GBP'"

        amount   = float(m.group(1).replace(",", ""))
        from_cur = m.group(2).upper()
        to_cur   = m.group(3).upper()

        # Free API — no key needed
        url  = f"https://api.exchangerate-api.com/v4/latest/{from_cur}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if to_cur not in data.get("rates", {}):
            return f"Currency '{to_cur}' not supported."

        rate   = data["rates"][to_cur]
        result = amount * rate
        return (
            f"💱 Currency Conversion\n"
            f"{amount:,.2f} {from_cur} = {result:,.2f} {to_cur}\n"
            f"Rate: 1 {from_cur} = {rate:.4f} {to_cur}\n"
            f"Updated: {data.get('date', 'today')}"
        )
    except requests.RequestException:
        return "Currency service unavailable. Please try again."
    except Exception as e:
        return f"Currency conversion failed: {str(e)}"


# ── 2. YouTube Transcript ─────────────────────────────────────
def youtube_transcript(url_or_id: str) -> str:
    """Get transcript/subtitles from a YouTube video."""
    try:
        # Extract video ID from URL
        vid_id = url_or_id.strip()
        for pat in [r'(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})']:
            m = re.search(pat, url_or_id)
            if m:
                vid_id = m.group(1)
                break

        if len(vid_id) != 11:
            return "Invalid YouTube URL or video ID."

        # Try new API (>=0.2.0) first, fall back to old API
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            # New API style (>=0.2.0)
            ytt_api  = YouTubeTranscriptApi()
            fetched  = ytt_api.fetch(vid_id)
            snippets = fetched.snippets if hasattr(fetched, "snippets") else list(fetched)
            full_text = " ".join(
                s.text if hasattr(s, "text") else s.get("text", "")
                for s in snippets
            )
        except TypeError:
            # Old API style (<0.2.0)
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(vid_id)
            full_text = " ".join(t["text"] for t in transcript_list)

        if not full_text.strip():
            return "This video has no subtitles/transcript available."

        if len(full_text) > 4000:
            full_text = full_text[:4000] + "...[transcript trimmed]"

        return f"📺 YouTube Transcript\nVideo ID: {vid_id}\n\n{full_text}"

    except ImportError:
        return "Missing package. Run: pip install youtube-transcript-api"
    except Exception as e:
        err = str(e).lower()
        if "disabled" in err or "no transcript" in err or "no element" in err:
            return "This video has no subtitles/transcript available."
        return f"Could not get transcript: {str(e)}"


# ── 3. News Feed ───────────────────────────────────────────────
def get_news(topic: str = "latest") -> str:
    """Get latest news headlines for a topic using RSS feeds — no API key needed."""
    try:
        topic = topic.strip().lower()

        # Pick best RSS feed for topic
        feeds = {
            "tech":        "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "technology":  "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "world":       "https://feeds.bbci.co.uk/news/world/rss.xml",
            "business":    "https://feeds.bbci.co.uk/news/business/rss.xml",
            "sports":      "https://feeds.bbci.co.uk/sport/rss.xml",
            "sport":       "https://feeds.bbci.co.uk/sport/rss.xml",
            "science":     "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
            "health":      "https://feeds.bbci.co.uk/news/health/rss.xml",
            "pakistan":    "https://www.dawn.com/feeds/home",
            "ai":          "https://feeds.feedburner.com/oreilly/radar",
        }

        feed_url = feeds.get(topic, "https://feeds.bbci.co.uk/news/rss.xml")
        resp = requests.get(feed_url, headers=HEADERS, timeout=12)
        resp.raise_for_status()

        # Parse RSS with regex (no extra library)
        items = re.findall(
            r'<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?<description><!\[CDATA\[(.*?)\]\]></description>.*?</item>',
            resp.text, re.DOTALL
        )
        if not items:
            # Fallback: plain XML title tags
            titles = re.findall(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', resp.text)
            titles = [t.strip() for t in titles if t.strip() and len(t.strip()) > 20][:8]
            if not titles:
                return f"No news found for '{topic}'."
            output = f"📰 Latest {topic.title()} News\n\n"
            for i, t in enumerate(titles[:8], 1):
                output += f"{i}. {t}\n"
            return output

        output = f"📰 Latest {topic.title()} News\n\n"
        for i, (title, desc) in enumerate(items[:8], 1):
            desc_clean = re.sub(r'<[^>]+>', '', desc).strip()[:120]
            output += f"{i}. {title.strip()}\n   {desc_clean}\n\n"
        return output.strip()

    except Exception as e:
        return f"News fetch failed: {str(e)}"


# ── 4. Code Executor (safe sandbox) ───────────────────────────
def run_code(code: str) -> str:
    """Execute Python code in a restricted sandbox and return output."""
    import io, contextlib, signal, ast

    code = code.strip()

    # Strip markdown code fences if present
    code = re.sub(r'^```(?:python)?\s*', '', code, flags=re.MULTILINE)
    code = re.sub(r'```\s*$', '', code, flags=re.MULTILINE).strip()

    # ── Safety check: block dangerous imports/calls ────────────
    BLOCKED = [
        "import os", "import sys", "import subprocess", "import socket",
        "import shutil", "import pathlib", "import glob", "__import__",
        "open(", "exec(", "eval(", "compile(", "importlib",
        "os.system", "os.popen", "os.remove", "os.rmdir",
        "subprocess.run", "subprocess.call", "subprocess.Popen",
        "requests.get", "requests.post", "urllib", "http.client",
        "builtins", "__builtins__", "globals()", "locals()",
        "getattr(", "setattr(", "delattr(",
    ]
    code_lower = code.lower()
    for blocked in BLOCKED:
        if blocked.lower() in code_lower:
            return f"❌ Blocked: '{blocked}' is not allowed in the sandbox."

    # ── Validate syntax before running ────────────────────────
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"❌ Syntax Error: {e}"

    # ── Safe builtins only ─────────────────────────────────────
    safe_builtins = {
        "print": print, "len": len, "range": range, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter, "sorted": sorted,
        "reversed": reversed, "list": list, "dict": dict, "set": set,
        "tuple": tuple, "str": str, "int": int, "float": float,
        "bool": bool, "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "type": type, "isinstance": isinstance,
        "repr": repr, "format": format, "chr": chr, "ord": ord,
        "hex": hex, "oct": oct, "bin": bin, "divmod": divmod,
        "pow": pow, "hash": hash, "id": id,
        "__name__": "__main__",
    }

    # ── Capture output ─────────────────────────────────────────
    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, {"__builtins__": safe_builtins}, {})
        output = stdout_capture.getvalue()
        if not output.strip():
            return "✅ Code ran successfully (no output)."
        return f"✅ Output:\n{output.strip()}"
    except Exception as e:
        return f"❌ Runtime Error: {type(e).__name__}: {e}"


# ── Update TOOL_REGISTRY ───────────────────────────────────────
TOOL_REGISTRY.update({
    "currency_convert":  currency_convert,
    "youtube_transcript": youtube_transcript,
    "get_news":          get_news,
    "run_code":          run_code,
})

# ══════════════════════════════════════════════════════════════
# NEW TOOLS BATCH 2
# ══════════════════════════════════════════════════════════════

# ── 5. Dictionary / Word Definition ───────────────────────────
def define_word(word: str) -> str:
    """Get definition, pronunciation, and examples for a word."""
    try:
        word    = word.strip().lower().split()[0]
        resp    = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
            timeout=10, headers=HEADERS
        )
        if resp.status_code != 200:
            return f"No definition found for '{word}'."
        data    = resp.json()[0]
        phonetic = data.get("phonetic", "")
        output  = f"📖 **{word}** {phonetic}\n\n"
        for meaning in data.get("meanings", [])[:3]:
            pos  = meaning.get("partOfSpeech", "")
            defs = meaning.get("definitions", [])[:2]
            output += f"**{pos.capitalize()}**\n"
            for i, d in enumerate(defs, 1):
                output += f"{i}. {d['definition']}\n"
                if d.get("example"):
                    output += f"   *\"{d['example']}\"*\n"
            output += "\n"
        synonyms = data.get("meanings", [{}])[0].get("synonyms", [])[:5]
        if synonyms:
            output += f"**Synonyms:** {', '.join(synonyms)}"
        return output.strip()
    except Exception as e:
        return f"Dictionary error: {e}"


# ── 6. QR Code Generator ──────────────────────────────────────
def generate_qr(text: str) -> str:
    """Generate a QR code for any text or URL."""
    try:
        text    = text.strip()
        encoded = requests.utils.quote(text)
        # Use free QR API — returns direct image URL
        qr_url  = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}"
        # Fetch and return as base64 so it displays inline
        resp    = requests.get(qr_url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100:
            b64 = base64.b64encode(resp.content).decode("utf-8")
            return f"IMAGE_URL:data:image/png;base64,{b64}"
        return f"QR_URL:{qr_url}"
    except Exception as e:
        return f"QR generation failed: {e}"


# ── 7. Unit Converter ─────────────────────────────────────────
def unit_convert(query: str) -> str:
    """Convert between common units: km/miles, kg/lbs, C/F, etc."""
    try:
        query = query.strip().lower()
        # Extract number and units
        m = re.search(r'([\d,]+(?:\.\d+)?)\s*([a-zA-Z°/]+)\s*(?:to|in|into|=)\s*([a-zA-Z°/]+)', query, re.I)
        if not m:
            return "Format: '10 km to miles' or '100 kg to lbs' or '37 C to F'"

        val     = float(m.group(1).replace(",", ""))
        from_u  = m.group(2).lower().strip()
        to_u    = m.group(3).lower().strip()

        # Conversion table
        conversions = {
            # Length
            ("km",    "miles"):  val * 0.621371,
            ("miles", "km"):     val * 1.60934,
            ("m",     "ft"):     val * 3.28084,
            ("ft",    "m"):      val * 0.3048,
            ("cm",    "inch"):   val * 0.393701,
            ("inch",  "cm"):     val * 2.54,
            ("m",     "yards"):  val * 1.09361,
            # Weight
            ("kg",    "lbs"):    val * 2.20462,
            ("lbs",   "kg"):     val * 0.453592,
            ("g",     "oz"):     val * 0.035274,
            ("oz",    "g"):      val * 28.3495,
            ("kg",    "g"):      val * 1000,
            ("g",     "kg"):     val / 1000,
            # Temperature
            ("c",     "f"):      (val * 9/5) + 32,
            ("f",     "c"):      (val - 32) * 5/9,
            ("c",     "k"):      val + 273.15,
            ("k",     "c"):      val - 273.15,
            # Volume
            ("l",     "gallon"): val * 0.264172,
            ("gallon","l"):      val * 3.78541,
            ("ml",    "l"):      val / 1000,
            ("l",     "ml"):     val * 1000,
            # Speed
            ("kmh",   "mph"):    val * 0.621371,
            ("mph",   "kmh"):    val * 1.60934,
            ("km/h",  "mph"):    val * 0.621371,
            ("mph",   "km/h"):   val * 1.60934,
        }

        result = conversions.get((from_u, to_u))

        # Normalize aliases
        aliases = {"celsius":"c","fahrenheit":"f","kelvin":"k","kilometer":"km",
                   "kilogram":"kg","pound":"lbs","meter":"m","feet":"ft","foot":"ft",
                   "liter":"l","litre":"l","gallon":"gallon","inch":"inch","inches":"inch"}
        from_n = aliases.get(from_u, from_u)
        to_n   = aliases.get(to_u,   to_u)
        if result is None:
            result = conversions.get((from_n, to_n))

        if result is not None:
            return (f"📐 Unit Conversion\n"
                    f"{val:,} {m.group(2)} = **{result:,.4f} {m.group(3)}**")
        return f"Conversion from '{from_u}' to '{to_u}' not supported yet."
    except Exception as e:
        return f"Unit conversion failed: {e}"


# ── 8. Email Sender (Gmail SMTP) ───────────────────────────────
def send_email(query: str) -> str:
    """Send an email via Gmail SMTP. Format: 'to:email subject:X body:Y'"""
    import smtplib, os
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASSWORD", "")

    if not SMTP_USER or not SMTP_PASS:
        return ("Email not configured. Add to .env:\n"
                "SMTP_USER=your@gmail.com\n"
                "SMTP_PASSWORD=your_app_password\n"
                "Get app password: https://myaccount.google.com/apppasswords")

    try:
        to_m      = re.search(r'to[:\s]+([^\s,;]+@[^\s,;]+)', query, re.I)
        subj_m    = re.search(r'subject[:\s]+"?([^"]+?)"?\s*(?:body|message|$)', query, re.I)
        body_m    = re.search(r'(?:body|message)[:\s]+"?(.+?)(?:"|$)', query, re.I | re.DOTALL)

        if not to_m:
            return "Please specify recipient: 'send email to:someone@example.com subject:Hello body:Hi there'"

        to_addr = to_m.group(1).strip()
        subject = subj_m.group(1).strip() if subj_m else "Message from NexusBot"
        body    = body_m.group(1).strip() if body_m else query

        msg = MIMEMultipart()
        msg["From"]    = SMTP_USER
        msg["To"]      = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return f"✅ Email sent to **{to_addr}**\nSubject: {subject}"
    except Exception as e:
        return f"Email failed: {e}"


# ── Update TOOL_REGISTRY with new tools ───────────────────────
TOOL_REGISTRY.update({
    "define_word":    define_word,
    "generate_qr":   generate_qr,
    "unit_convert":   unit_convert,
    "send_email":     send_email,
})