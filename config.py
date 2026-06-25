"""All knobs in one place."""
import os
from dotenv import load_dotenv
load_dotenv()

BRAND = os.getenv("BRAND", "Liaison")
DB_PATH = os.getenv("DB_PATH", "/tmp/liaison.db")

# WhatsApp concierge number users message after signup (Wassist inbound handoff).
CONCIERGE_WA_NUMBER = os.getenv("CONCIERGE_WA_NUMBER", "447883319107")

# Hermes matchmaking brain — OpenAI-compatible (Ollama serving Hermes locally).
#   ollama pull hermes3   ->   LLM_MODEL=hermes3:8b
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "hermes3:8b")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")

# Stripe — used at the unlock step after signup
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
UNLOCK_PRICE_PENCE = int(os.getenv("UNLOCK_PRICE_PENCE", "50"))  # 50p in pence
UNLOCK_CURRENCY = os.getenv("UNLOCK_CURRENCY", "gbp")
