import os
from dotenv import load_dotenv

load_dotenv(override=True)
class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    MODEL_NAME   = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    # JWT_SECRET   = os.getenv("JWT_SECRET", "nexusbot-secret-key-2024-change-me")
    DEBUG        = os.getenv("DEBUG", "True") == "True"
    MAX_UPLOAD   = 16 * 1024 * 1024

    @classmethod
    def validate(cls):
        if not cls.GROQ_API_KEY:
            print("❌ ERROR: GROQ_API_KEY is missing in .env file!")
            print("   1. Go to https://console.groq.com")
            print("   2. Create an API key")
            print("   3. Add it to backend/.env as: GROQ_API_KEY=gsk_...")
            raise ValueError("GROQ_API_KEY not set")

        if not cls.GROQ_API_KEY.startswith("gsk_"):
            print("⚠️  WARNING: GROQ_API_KEY looks invalid (should start with 'gsk_')")

        # Only show first 8 chars for security
        safe_key = cls.GROQ_API_KEY[:8] + "..." + cls.GROQ_API_KEY[-4:]
        print(f"✅ GROQ KEY: {safe_key}")
        print(f"✅ MODEL:    {cls.MODEL_NAME}")