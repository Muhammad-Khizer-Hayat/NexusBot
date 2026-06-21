# backend/nodes/node_formatter.py
import re
from agents.state import AgentState
from services.llm import call_llm
from services.memory import load_history
from prompts import get_synthesis_prompt, get_chat_system, get_datetime
from langchain_core.messages import SystemMessage, HumanMessage

def _parse_weather(raw: str, city_hint: str = "") -> str:
    data = {}
    city_m = re.search(r'[Ww]eather in ([A-Za-z\s]+?),\s*([A-Za-z\s]+?)[\:\n]', raw)
    if city_m:
        data["city"]    = city_m.group(1).strip()
        data["country"] = city_m.group(2).strip()
    else:
        data["city"]    = city_hint.title() if city_hint else "Unknown"
        data["country"] = ""
    temps = re.findall(r'(?:around|~)?\s*([\d.]+)\s*°C', raw)
    data["temp"]       = temps[0] if temps else "0"
    feel_m = re.search(r'[Ff]eels like\s*([\d.]+)\s*°C', raw)
    data["feels_like"] = feel_m.group(1) if feel_m else (temps[1] if len(temps)>1 else data["temp"])
    high_m = re.search(r'[Hh]igh[:\s~*|]*~?([\d.]+)\s*°C', raw)
    low_m  = re.search(r'[Ll]ow[:\s~*|]*~?([\d.]+)\s*°C', raw)
    try:
        data["high"] = high_m.group(1) if high_m else str(round(float(data["temp"])+3))
        data["low"]  = low_m.group(1)  if low_m  else str(round(float(data["temp"])-6))
    except:
        data["high"] = "--"; data["low"] = "--"
    hum_m = re.search(r'([\d.]+)\s*%\s*humidity|humidity[:\s]*([\d.]+)', raw, re.IGNORECASE)
    data["humidity"] = (hum_m.group(1) or hum_m.group(2)) if hum_m else "0"
    wind_m = re.search(r'[Ww]ind[:\s]*([\d.]+)\s*km/h', raw)
    data["wind"] = wind_m.group(1) if wind_m else "0"
    cond_m = re.search(
        r'(Clear sky|Mainly clear|Partly cloudy|Overcast|Foggy|Light rain|Rain|'
        r'Heavy rain|Snow|Thunderstorm|Drizzle|Showers|Cloudy)', raw, re.IGNORECASE)
    data["condition"] = cond_m.group(1) if cond_m else "Clear"
    cond = data["condition"].lower()
    if any(w in cond for w in ["rain","drizzle","shower","thunder"]):
        data["advice"] = "Carry an umbrella today."
    elif any(w in cond for w in ["snow","icy","fog"]):
        data["advice"] = "Drive carefully and dress warmly."
    elif any(w in cond for w in ["clear","mainly clear","sunny"]):
        data["advice"] = "Great day to go outside! Stay hydrated."
    else:
        data["advice"] = "Check local forecasts for updates."
    return (
        f"[WEATHER_CARD]\ncity={data['city']}\ncountry={data['country']}\n"
        f"condition={data['condition']}\ntemp={data['temp']}\n"
        f"feels_like={data['feels_like']}\nhumidity={data['humidity']}\n"
        f"wind={data['wind']}\nhigh={data['high']}\nlow={data['low']}\n"
        f"advice={data['advice']}\n[/WEATHER_CARD]"
    )

def formatter_node(state: AgentState) -> AgentState:
    output      = state.get("output", "")
    tool_result = state.get("tool_result", "")
    tool_name   = state.get("tool_name", "")
    user_input  = state.get("input", "")
    rag_chunks  = state.get("rag_chunks", [])
    session     = state.get("session_id", "default")

    print(f"[Node 5] output={bool(output)} tool={tool_name!r} result={bool(tool_result)}")

    # Pass-through — chat/clarify/memory answered, no tool used
    if output and not tool_result and not rag_chunks:
        print("[Node 5] Pass-through")
        return state

    # ── Any tool returning IMAGE_URL or IMAGE_DIRECT_URL ─────────
    # Handles: generate_image, generate_qr, and any future image tools
    if tool_result and tool_result.startswith("IMAGE_URL:"):
        image_url = tool_result.replace("IMAGE_URL:", "").strip()
        label = "QR Code" if tool_name == "generate_qr" else "Image"
        print(f"[Node 5] {label} generated ✅ (base64)")
        return {**state, "output": f"[IMAGE]{image_url}[/IMAGE]"}

    if tool_result and tool_result.startswith("IMAGE_DIRECT_URL:"):
        raw_url = tool_result.replace("IMAGE_DIRECT_URL:", "").strip()
        print(f"[Node 5] Image direct URL ✅")
        return {**state, "output": f"[IMAGE]{raw_url}[/IMAGE]"}

    if tool_result and tool_result.startswith("QR_URL:"):
        qr_url = tool_result.replace("QR_URL:", "").strip()
        print(f"[Node 5] QR URL ✅")
        return {**state, "output": f"[IMAGE]{qr_url}[/IMAGE]"}

    if tool_name == "generate_image" and tool_result and tool_result.startswith("IMAGE_ERROR"):
        return {**state, "output": f"Sorry, could not generate image. {tool_result}"}

    # ── Weather card ───────────────────────────────────────────
    if tool_name == "weather" and tool_result:
        if "°C" in tool_result:
            card = _parse_weather(tool_result, state.get("tool_input",""))
            print("[Node 5] Weather card built")
            return {**state, "output": card}
        return {**state, "output": f"Could not get weather. {tool_result}"}

    # ── OCR — clean noisy text with LLM then format ────────────
    if tool_name == "ocr" and tool_result:
        if tool_result.startswith("⚠️") or tool_result.startswith("OCR"):
            print("[Node 5] OCR error passthrough")
            return {**state, "output": tool_result}

        # ← CHANGE: truncate OCR text before sending to LLM — prevents 413 error
        ocr_text = tool_result[:1500]

        cleanup_system = """You are an OCR text cleaner.
You will receive raw OCR output from a scanned document. It may contain:
- Broken words, random symbols, misread characters like l/I/1, 0/O, rn/m

Your job:
1. Reconstruct the correct readable text
2. Fix broken words and obvious OCR errors
3. Keep ALL original information — names, numbers, dates, IDs exactly as they are
4. Format it cleanly with proper labels and sections
5. Output ONLY the cleaned document text, no explanation"""

        msgs = [
            SystemMessage(content=cleanup_system),
            HumanMessage(content=f"Clean this OCR text:\n\n{ocr_text}")  # ← CHANGE
        ]
        cleaned = call_llm(msgs)

        filename = state.get("tool_input", "image")
        formatted = (
            f"### 📄 OCR Result — `{filename}`\n\n"
            f"---\n\n"
            f"{cleaned}\n\n"
            f"---\n"
            f"*Text extracted and cleaned from image.*"
        )
        print("[Node 5] OCR cleaned + formatted")
        return {**state, "output": formatted}

    # ── RAG — uses MASTER_PROMPT via get_chat_system ───────────
    if rag_chunks and tool_result:
        # ← CHANGE: truncate RAG context — prevents 413 error
        rag_context = tool_result[:1500]
        system = get_chat_system(rag_context=rag_context)  # ← CHANGE
        msgs   = [
            SystemMessage(content=system),
            HumanMessage(content=f"Answer this using the document context: {user_input}")
        ]
        print("[Node 5] RAG answer")
        return {**state, "output": call_llm(msgs)}

    # ── YouTube transcript ─────────────────────────────────────
    if tool_name == "youtube_transcript" and tool_result:
        if tool_result.startswith("📺"):
            transcript_text = tool_result[:3000]
            system = get_chat_system()
            msgs   = [
                SystemMessage(content=system),
                HumanMessage(content=f"""Here is a YouTube video transcript:

{transcript_text}

The user sent this YouTube link: {user_input}
Please provide a clear, structured summary of the video content. Include:
- What the video is about
- Key points covered
- Main takeaways""")
            ]
            print("[Node 5] YouTube transcript summary")
            return {**state, "output": call_llm(msgs)}
        return {**state, "output": tool_result}

    # ── Web search / other tools ───────────────────────────────
    if tool_result:
        # ← CHANGE: truncate to 2000 chars — prevents 413 token limit error
        truncated_result = tool_result[:2000]

        print(f"[Node 5] Synthesizing {len(truncated_result)} chars from {tool_name}")

        # ← CHANGE: only last 2 history messages — keeps token count low
        history        = state.get("chat_history") or load_history(session)
        recent_history = history[-2:] if history else []

        system = get_synthesis_prompt(truncated_result)  # ← CHANGE
        msgs   = [SystemMessage(content=system)] + recent_history + [
            HumanMessage(content=f"User question: {user_input}")
        ]
        answer = call_llm(msgs)
        import re as _re
        answer = _re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', answer).strip()
        # Safety: if LLM returned nothing, build a simple direct answer from the tool result
        if not answer:
            answer = f"Result: {truncated_result}"
        print(f"[Node 5] Answer done ({len(answer)} chars)")
        return {**state, "output": answer}

    if output:
        return state

    return {**state, "output": "Sorry, I could not generate a response. Please try again."}