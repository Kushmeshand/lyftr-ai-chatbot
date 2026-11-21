import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# Disable LiteLLM external pricing sync for faster, offline-ready initialization
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_MODE"] = "PRODUCTION"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

# Comma-separated key pool, at least 2 keys. Key ids are key_1, key_2, ...
raw_keys = os.getenv("LLM_API_KEYS", "dummy_key_1,dummy_key_2")
_parsed_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
if not _parsed_keys:
    _parsed_keys = ["placeholder_key_1", "placeholder_key_2"]

LLM_API_KEYS: List[str] = _parsed_keys

# Structured key pool with key_ids
KEY_POOL: List[Dict[str, str]] = [
    {"key_id": f"key_{i+1}", "api_key": key}
    for i, key in enumerate(LLM_API_KEYS)
]

ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: List[str] = [origin.strip() for origin in ALLOWED_ORIGINS_RAW.split(",") if origin.strip()]

ENABLE_FAILURE_SIMULATION = os.getenv("ENABLE_FAILURE_SIMULATION", "true").lower() in ("true", "1", "yes")

LLM_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
DEFAULT_SYSTEM_PROMPT = os.getenv("DEFAULT_SYSTEM_PROMPT", "You are a helpful and concise AI assistant.")
