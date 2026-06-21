# backend/nodes/node_intent_classifier.py
import re
from agents.state import AgentState
from services.rag_service import has_documents

WEATHER_WORDS = ["weather","temperature","rain","sunny","cloudy","forecast",
                 "humid","wind","hot today","cold today","raining","snowing"]
MATH_WORDS    = ["calculate","compute","% of","percent of","multiply","divide"]
CODING_WORDS  = ["write code","write a","python","javascript","java","c++","html",
                 "css","sql","function","class","program","script","debug",
                 "fix my code","error in","explain code","what does this code"]
CHAT_WORDS    = ["hello","hi","how are you","who are you","what can you do",
                 "thanks","thank you","bye","good morning","good night",
                 "what is your name","are you ai","are you a bot"]

# ← CHANGE: replaced loose IMAGE_WORDS/IMAGE_VERBS/IMAGE_NOUNS
# with STRICT exact trigger phrases only
IMAGE_TRIGGER_PHRASES = [
    "generate image","generate an image","generate a image","generate the image",
    "create image","create an image","create a image","create the image",
    "make image","make an image","make a image","make the image",
    "draw image","draw me a","draw me an","draw me the",
    "generate photo","generate a photo","generate the photo",
    "create photo","create a photo","create the photo",
    "make photo","make a photo",
    "generate art","create art","make art",
    "ai image of","ai art of",
    "generate picture","generate a picture","generate the picture",
    "create picture","create a picture","create the picture",
    "make picture","make a picture","make the picture",
    "show me image of","show me a picture of","show me a photo of",
    "make me an image","make me a picture","make me a photo",
    "paint a picture","paint an image","paint a",
    "sketch a picture","sketch an image","sketch a",
    "generate me an image","generate me a picture",
]

# ← ADD: queries starting with these are NEVER image requests
NEVER_IMAGE = [
    "who is","who was","who are","who were",
    "what is","what was","what are","what were",
    "where is","where was","when is","when was",
    "how is","how was","why is","why was",
    "which is","which was","is there","is the",
    "tell me","explain","describe","define",
    "translate","summarize","list","give me",
    "find","search","look up","show me the",
    "draw a conclusion","draw attention","draw from","draw on","draw up",
]

# ── Pure conceptual questions → LLM answers directly (no search needed)
GENERAL_KNOWLEDGE_STARTERS = [
    "what is","what are","how does","how do","how did","how is","how are",
    "why is","why are","why does","why do","why did",
    "explain ","define ","difference between","compare ","versus"," vs ",
    "pros and cons","how to ","how can i ","how should i","steps to","guide to",
    "is it possible","can you explain","help me understand",
    "what happens when","what would happen","what will happen",
    "write ","draft ","give me a ",
]

# ── These always go to web_search — specific entity or person lookups
ALWAYS_SEARCH_STARTERS = [
    "tell me about","about ","who founded","founder of","ceo of","head of",
    "who runs","who owns","who made","who created","who built","who leads",
    "history of","background of","overview of","profile of",
    "what does","what did","when was","when did","where is","where was",
    "who is","who was","who are","who were",
    "find ","search ","look up","research ",
]

# ── These keywords force web_search even if it looks like a knowledge Q
REALTIME_WORDS = [
    "today","right now","currently","latest","recent","news","live",
    "price","stock","score","match","election","update","results",
    "trending","breaking","this week","this month","this year",
    "2024","2025","2026","now","at the moment","as of",
    "who won","who is winning","what happened today","what's happening",
    "new release","just released","just launched","announced",
]

VAGUE_PATTERNS = [
    r"^can you help\??$",
    r"^help me\??$",
    r"^i need help\??$",
    r"^help\??$",
    r"^yes\??$",
    r"^ok\??$",
    r"^okay\??$",
    r"^sure\??$",
    r"^please help\??$",
    r"^i have a question\??$",
    r"^i want to ask\??$",
    r"^can you do something\??$",
]

FOLLOWUP_PATTERNS = [
    r"^(tell me more|more details|elaborate|explain more|go on|continue)",
    r"^(what about|how about|and what about)",
    r"^(what else|anything else|what more)",
    r"\b(you (just |previously |already )?(said|mentioned|told|explained))\b",
    r"^(first point|second point|last point|point \d)",
    r"^(previous|earlier|above|that) (answer|response|result|point|topic)",
    r"^(summarize|summary of) (that|this|what you said|above)",
    r"^(repeat|say it again|rephrase)",
]

def _is_vague(msg: str) -> bool:
    clean = msg.lower().strip()
    words = clean.split()
    if len(words) <= 3 and not any(w in clean for w in CHAT_WORDS):
        for pattern in VAGUE_PATTERNS:
            if re.match(pattern, clean):
                return True
    return False

def _is_followup(msg: str) -> bool:
    clean = msg.lower().strip()
    for pattern in FOLLOWUP_PATTERNS:
        if re.search(pattern, clean):
            return True
    return False

def _is_image_request(msg: str) -> bool:
    msg_lower = msg.lower().strip()

    # ← CHANGE: hard exclusion first — never image for question words
    if any(msg_lower.startswith(p) for p in NEVER_IMAGE):
        return False

    # ← CHANGE: only match STRICT exact phrases — default is False
    if any(phrase in msg_lower for phrase in IMAGE_TRIGGER_PHRASES):
        return True

    return False  # ← default FALSE — never guess

def _is_knowledge_question(msg: str) -> bool:
    msg_lower = msg.lower().strip()

    # Real-time data needed → always search
    if any(w in msg_lower for w in REALTIME_WORDS):
        return False

    # Specific entity/person/company lookups → always search
    # (LLM won't know small companies, local businesses, specific people)
    if any(msg_lower.startswith(w) for w in ALWAYS_SEARCH_STARTERS):
        return False

    # Pure conceptual questions → LLM handles these perfectly
    if any(msg_lower.startswith(w) for w in GENERAL_KNOWLEDGE_STARTERS):
        return True

    return False

def intent_classifier_node(state: AgentState) -> AgentState:
    msg  = state["input"].lower()
    text = state["input"]

    # ── Vague ──────────────────────────────────────────────────
    if _is_vague(text):
        print(f"[Node 2] → clarify (vague input)")
        return {**state, "intent": "clarify"}

    # ── Image BEFORE follow-up check ───────────────────────────
    if _is_image_request(msg):
        # ← CHANGE: extract by removing trigger phrase first (more accurate)
        cleaned = msg.lower()
        for phrase in sorted(IMAGE_TRIGGER_PHRASES, key=len, reverse=True):
            if phrase in cleaned:
                cleaned = cleaned.replace(phrase, " ").strip()
                break

        # Remove leftover junk words at start
        for junk in ["of the","of a","of an","of","the","a","an","please","me"]:
            if cleaned.startswith(junk + " "):
                cleaned = cleaned[len(junk):].strip()

        prompt = cleaned.strip()

        # If prompt is too short or just one word, use everything after the trigger phrase
        if not prompt or len(prompt) < 3 or len(prompt.split()) < 2:
            # Try to extract: everything after "image of", "photo of", "picture of" etc
            subject_m = re.search(
                r'(?:image|photo|picture|art|drawing|sketch|painting)\s+(?:of\s+)?(.+)',
                msg.lower()
            )
            if subject_m:
                prompt = subject_m.group(1).strip()
            else:
                prompt = text

        # Still too short — just use original input
        if not prompt or len(prompt) < 3:
            prompt = text

        print(f"[Node 2] → generate_image: '{prompt[:50]}'")
        return {**state, "intent":"tool","tool_name":"generate_image","tool_input":prompt}

    # ── Follow-up → chat ───────────────────────────────────────
    if _is_followup(text):
        print(f"[Node 2] → chat (follow-up, uses memory)")
        return {**state, "intent": "chat"}

    # ── YouTube transcript (BEFORE generic URL scrape) ────────
    if "youtube.com" in msg or "youtu.be" in msg:
        url_m2 = re.search(r'https?://\S+', text)
        print(f"[Node 2] → youtube_transcript")
        return {**state, "intent":"tool","tool_name":"youtube_transcript",
                "tool_input": url_m2.group() if url_m2 else text}

    # ── QR Code ────────────────────────────────────────────────
    QR_PHRASES = ["qr code", "qr for", "generate qr", "create qr", "make qr"]
    if any(p in msg for p in QR_PHRASES):
        # Use original text (not lowercased) to preserve URLs, phone numbers, etc.
        text_m = re.search(r'(?:qr code|qr for|generate qr|create qr|make qr)\s+(?:for\s+)?(.+)', text, re.I)
        qr_text = text_m.group(1).strip() if text_m else text
        print(f"[Node 2] → generate_qr: '{qr_text[:40]}'")
        return {**state, "intent":"tool","tool_name":"generate_qr","tool_input":qr_text}

    # ── Currency converter ─────────────────────────────────────
    if re.search(r'\b\d[\d,]*(?:\.\d+)?\s*[A-Za-z]{3}\s*(?:to|in|into)\s*[A-Za-z]{3}\b', text, re.I):
        print(f"[Node 2] → currency_convert")
        return {**state, "intent":"tool","tool_name":"currency_convert","tool_input":text}
    CURRENCY_WORDS = ["convert","exchange rate","how much is","currency"]
    if any(w in msg for w in CURRENCY_WORDS) and re.search(r'\b[A-Z]{3}\b', text):
        print(f"[Node 2] → currency_convert")
        return {**state, "intent":"tool","tool_name":"currency_convert","tool_input":text}

    # ── Unit converter ─────────────────────────────────────────
    UNIT_UNITS = ["km","miles","kg","lbs","celsius","fahrenheit","meter","feet",
                  "inch","gallon","liter","mph","kmh","km/h","oz","gram","pound"]
    if re.search(r'\d', text) and any(u in msg for u in UNIT_UNITS) and        any(w in msg for w in ["to","in","into","convert"]):
        print(f"[Node 2] → unit_convert")
        return {**state, "intent":"tool","tool_name":"unit_convert","tool_input":text}

    # ── Dictionary ─────────────────────────────────────────────
    DICT_PHRASES = ["define ","definition of","meaning of","what does","dictionary"]
    if any(p in msg for p in DICT_PHRASES):
        word_m = re.search(r'(?:define|definition of|meaning of|what does)\s+(\w+)', msg)
        word = word_m.group(1) if word_m else text.strip()
        print(f"[Node 2] → define_word: '{word}'")
        return {**state, "intent":"tool","tool_name":"define_word","tool_input":word}

    # ── News ───────────────────────────────────────────────────
    NEWS_PHRASES = ["latest news","top news","breaking news","news about",
                    "what's in the news","today's news","current news",
                    "headlines","news on","recent news","pakistan news",
                    "tech news","sports news","health news","ai news"]
    if any(p in msg for p in NEWS_PHRASES):
        topic = "latest"
        for t in ["tech","technology","world","business","sports","sport",
                  "science","health","pakistan","ai","politics"]:
            if t in msg:
                topic = t
                break
        print(f"[Node 2] → get_news: '{topic}'")
        return {**state, "intent":"tool","tool_name":"get_news","tool_input":topic}

    # ── Email ──────────────────────────────────────────────────
    EMAIL_PHRASES = ["send email","send mail","email to","write email"]
    if any(p in msg for p in EMAIL_PHRASES):
        print(f"[Node 2] → send_email")
        return {**state, "intent":"tool","tool_name":"send_email","tool_input":text}

    # ── Code executor ──────────────────────────────────────────
    RUN_PHRASES = ["run this code","execute this","run this","execute this code",
                   "run the code","execute the code","run it","test this code"]
    if any(p in msg for p in RUN_PHRASES):
        code_m = re.search(r'```(?:python)?\s*(.*?)```', text, re.DOTALL)
        code   = code_m.group(1).strip() if code_m else text
        print(f"[Node 2] → run_code")
        return {**state, "intent":"tool","tool_name":"run_code","tool_input":code}

    # ── Flowchart/Diagram → LLM generates mermaid ─────────────
    DIAGRAM_PHRASES = ["flowchart","flow chart","diagram","sequence diagram",
                       "draw a","make a diagram","create a diagram",
                       "architecture diagram","uml","er diagram","class diagram",
                       "mind map","process flow","workflow diagram"]
    if any(p in msg for p in DIAGRAM_PHRASES):
        print(f"[Node 2] → chat (diagram/flowchart request)")
        return {**state, "intent":"chat"}

    # ── URL → scrape ───────────────────────────────────────────
    url_m = re.search(r'https?://\S+', text)
    if url_m:
        print(f"[Node 2] → scrape")
        return {**state, "intent":"tool","tool_name":"scrape","tool_input":url_m.group()}

    # ── Weather ────────────────────────────────────────────────
    if any(w in msg for w in WEATHER_WORDS):
        city_m = re.search(
            r'\bin\s+([A-Za-z][A-Za-z\s]{1,25}?)(?:\s*\?|\s*$|\s*\.|today|tomorrow|now|\?)',
            text, re.IGNORECASE
        )
        if city_m:
            city = city_m.group(1).strip()
        else:
            caps = [w for w in text.split() if w and w[0].isupper()
                    and w.lower() not in WEATHER_WORDS and len(w) > 2]
            city = caps[-1] if caps else "Lahore"
        print(f"[Node 2] → weather: '{city}'")
        return {**state, "intent":"weather","tool_name":"weather","tool_input":city}

    # ── Math ───────────────────────────────────────────────────
    if bool(re.search(r'\d', text)) and any(w in msg for w in MATH_WORDS):
        # Greedily grab the full math expression including operators and spaces
        expr_m = re.search(r'(\d[\d\s+\-*/().%^]*\d|\d+)', text)
        expr   = expr_m.group().strip() if expr_m else text
        # Also try to find a standalone slash-division pattern like 81699/72
        slash_m = re.search(r'(\d+\s*/\s*\d+)', text)
        if slash_m and len(slash_m.group()) > len(expr):
            expr = slash_m.group().strip()
        print(f"[Node 2] → calculate: '{expr}'")
        return {**state, "intent":"tool","tool_name":"calculate","tool_input":expr}

    # ── RAG ────────────────────────────────────────────────────
    if has_documents():
        doc_words = ["document","file","upload","pdf","according to","from the","in the file"]
        if any(w in msg for w in doc_words):
            print("[Node 2] → rag")
            return {**state, "intent":"rag"}

    # ── Pure chat ──────────────────────────────────────────────
    if any(w in msg for w in CHAT_WORDS):
        print("[Node 2] → chat (greeting)")
        return {**state, "intent":"chat"}

    # ── Coding → chat ──────────────────────────────────────────
    if any(w in msg for w in CODING_WORDS):
        print("[Node 2] → chat (coding)")
        return {**state, "intent":"chat"}

    # ── Knowledge question → chat (LLM answers directly like ChatGPT) ──────
    if _is_knowledge_question(msg):
        print(f"[Node 2] → chat (knowledge question — no search needed)")
        return {**state, "intent": "chat"}

    # ── Default → web_search (real-time / unknown / specific queries only) ──
    print(f"[Node 2] → web_search: '{text[:60]}'")
    return {**state, "intent":"tool","tool_name":"web_search","tool_input":text}