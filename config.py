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

# PayPal — used at the UNLOCK step (downstream of matching), not at signup.
PAYPAL_ENVIRONMENT = os.getenv("PAYPAL_ENVIRONMENT", "SANDBOX")  # SANDBOX | PRODUCTION
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
UNLOCK_PRICE = os.getenv("UNLOCK_PRICE", "0.50")
UNLOCK_CURRENCY = os.getenv("UNLOCK_CURRENCY", "GBP")
