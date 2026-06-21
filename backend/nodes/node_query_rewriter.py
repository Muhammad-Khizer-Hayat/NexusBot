# backend/nodes/node_query_rewriter.py
# Resolves pronouns and follow-up references using conversation history
# Example: "what is its population?" → "what is the population of Paris, France?"

from agents.state import AgentState
from services.llm import call_llm
from langchain_core.messages import SystemMessage, HumanMessage

def query_rewriter_node(state: AgentState) -> AgentState:
    history     = state.get("chat_history", [])
    user_input  = state.get("input", "").strip()

    # Save original before any rewriting
    state = {**state, "original_input": user_input}

    # FIX 1: skip rewriting for image/weather/tool requests
    SKIP_REWRITE = [
        "image","picture","photo","draw","generate image",
        "create image","weather","calculate","compute",
        "translate",        # translation requests are always fresh
        "translate it",
        "translate this",
        "in urdu",
        "in english",
        "in arabic",
        "in hindi",
        "solve","divide","multiply","percent","% of",  # ← ADD: math queries
    ]
    msg_lower_check = user_input.lower()
    if any(w in msg_lower_check for w in SKIP_REWRITE):
        print(f"[Rewriter] Tool request → skipping rewrite")
        return state

    # No history → nothing to resolve
    if not history:
        return state

    # FIX 2: skip LLM if no pronouns detected — saves 2-3 sec per message
    PRONOUNS = ["it","its","this","that","they","there","same",
                "above","those","he","she","who was","who were",
                "what was","what were","when was","where was"]
    padded = f" {msg_lower_check} "
    has_pronoun = (
        any(f" {p} " in padded for p in PRONOUNS) or
        any(msg_lower_check.startswith(p) for p in
            ["who was","who were","what was","when was","where was"])
    )
    if not has_pronoun:
        print(f"[Rewriter] No pronouns → skipping LLM call")
        return state

    # Build last 3 exchanges only — strip any image data to stay under token limit
    pairs = []
    temp_human = None
    for msg in history:
        role = getattr(msg, "type", "")
        if role == "human":
            temp_human = msg.content
        elif role == "ai" and temp_human:
            ai_content = msg.content
            # Strip base64 image data
            import re as _re
            ai_content = _re.sub(r'\[IMAGE\]data:[^[]{10,}\[/IMAGE\]', '[Image was generated]', ai_content)
            ai_content = _re.sub(r'data:image/[a-z]+;base64,[A-Za-z0-9+/=]{100,}', '[image data]', ai_content)
            # Truncate long AI replies in history context
            if len(ai_content) > 300:
                ai_content = ai_content[:300] + "..."
            pairs.append(f"User: {temp_human}\nBot: {ai_content}")
            temp_human = None
    history_text = "\n\n".join(pairs[-3:])

    if not history_text:
        return state

    prompt = f"""You are a query resolver. Given a conversation history and a new message,
rewrite the message to be fully self-contained — resolving any pronouns or references.

Conversation history:
{history_text}

New message: "{user_input}"

Rules:
- If the message references something from history (uses "it", "this", "that", "its", "they", "there", "same", "above", "those", "he", "she", "the company", "the city", "who was", "what was" etc.), rewrite it fully.
- If it is already self-contained and clear, return it EXACTLY as-is.
- Return ONLY the rewritten message. No explanation. No quotes.

Rewritten message:"""

    try:
        rewritten = call_llm([
            SystemMessage(content="You are a query resolver. Return only the rewritten query."),
            HumanMessage(content=prompt)
        ]).strip().strip('"').strip("'")

        if rewritten and rewritten != user_input:
            print(f"[Rewriter] '{user_input}' → '{rewritten}'")
        else:
            rewritten = user_input

        return {**state, "input": rewritten}

    except Exception as e:
        print(f"[Rewriter] Error: {e} — using original input")
        return state