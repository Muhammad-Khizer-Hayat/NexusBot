# backend/services/llm.py
# LangChain Groq LLM — created once, shared everywhere

import time
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage
from config import Config
print("GROQ KEY LOADED:", Config.GROQ_API_KEY)
_llm = ChatGroq(
    api_key=Config.GROQ_API_KEY,
    model_name=Config.MODEL_NAME,
    temperature=0.7,
    max_tokens=2048,
)

def call_llm(messages: list, max_retries: int = 3) -> str:
    """Call LLM with automatic retry on rate limit."""
    for attempt in range(max_retries):
        try:
            response = _llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err or "too many" in err:
                wait = 20 * (attempt + 1)
                print(f"[NexusBot] Rate limit. Waiting {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                continue
            raise e
    return "I'm experiencing high traffic. Please try again in a moment."

def get_llm():
    return _llm