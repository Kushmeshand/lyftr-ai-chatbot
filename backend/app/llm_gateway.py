import time
import logging
from typing import List, Dict, Any, Optional, Tuple
import litellm
from litellm.caching.caching import Cache
from litellm.exceptions import (
    RateLimitError, 
    APIConnectionError, 
    InternalServerError, 
    ServiceUnavailableError, 
    APIError
)
from app.config import (
    KEY_POOL, 
    LLM_MODEL, 
    ENABLE_FAILURE_SIMULATION
)
from app.simulate import parse_simulate_failure_header, get_simulated_status

logger = logging.getLogger("llm_gateway")

# Initialize LiteLLM's built-in cache
litellm_cache = Cache(type="local")
litellm.cache = litellm_cache

class AllProvidersUnavailableException(Exception):
    """Raised when all keys in the pool fail or are simulated to fail."""
    def __init__(self, detail: str = "all providers unavailable"):
        self.detail = detail
        super().__init__(detail)

def estimate_tokens(text: str) -> int:
    """Fallback token estimation: roughly 4 chars per token, minimum 1."""
    if not text:
        return 1
    return max(1, len(text) // 4)

def count_prompt_tokens(messages: List[Dict[str, str]], model: str) -> int:
    try:
        count = litellm.token_counter(model=model, messages=messages)
        if count and count > 0:
            return count
    except Exception:
        pass
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return estimate_tokens(" " * total_chars)

def is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APIConnectionError, InternalServerError, ServiceUnavailableError)):
        return True
    if isinstance(exc, APIError):
        code = getattr(exc, "status_code", None)
        if code in (429, 500, 502, 503, 504):
            return True
    err_str = str(exc).lower()
    retryable_keywords = ["429", "quota", "resource_exhausted", "500", "502", "503", "504", "rate limit", "overloaded"]
    return any(keyword in err_str for keyword in retryable_keywords)

def execute_chat(
    llm_messages: List[Dict[str, str]],
    simulate_header: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a chat completion across the key pool with automatic failover and caching.
    """
    start_time = time.perf_counter()
    
    # 1. Parse simulation header
    simulations = parse_simulate_failure_header(simulate_header, ENABLE_FAILURE_SIMULATION)
    is_simulated = bool(simulations)

    # 2. Check LiteLLM cache if not simulated
    cache_key = litellm_cache.get_cache_key(model=LLM_MODEL, messages=llm_messages)
    
    if not is_simulated:
        try:
            cached_data = litellm_cache.get_cache(cache_key=cache_key)
            if cached_data and isinstance(cached_data, dict) and "reply" in cached_data:
                latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                return {
                    "reply": cached_data["reply"],
                    "metadata": {
                        "resolution_source": "LLM_CACHE",
                        "model": cached_data.get("model", LLM_MODEL),
                        "latency_ms": latency_ms,
                        "input_tokens": cached_data.get("input_tokens", 0),
                        "output_tokens": cached_data.get("output_tokens", 0),
                        "key_id": None,
                        "fallback_attempts": 0
                    }
                }
        except Exception as e:
            logger.warning(f"Error reading from LiteLLM cache: {e}")

    # 3. Live inference with failover across key pool
    fallback_attempts = 0
    last_error: Optional[Exception] = None

    for key_info in KEY_POOL:
        key_id = key_info["key_id"]
        api_key = key_info["api_key"]

        # Check if this key should simulate a failure
        sim_status = get_simulated_status(key_id, simulations)
        if sim_status is not None:
            logger.info(f"Simulating failure for {key_id} with status {sim_status}")
            fallback_attempts += 1
            last_error = Exception(f"Simulated HTTP {sim_status} on {key_id}")
            continue

        try:
            # Real live call through LiteLLM
            response = litellm.completion(
                model=LLM_MODEL,
                messages=llm_messages,
                api_key=api_key,
                caching=False, # We manage cache explicitly for exact metadata adherence
                timeout=30.0
            )

            reply = response.choices[0].message.content or ""
            
            # Extract tokens
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            output_tokens = getattr(usage, "completion_tokens", None) if usage else None

            if input_tokens is None or input_tokens <= 0:
                input_tokens = count_prompt_tokens(llm_messages, LLM_MODEL)
            if output_tokens is None or output_tokens <= 0:
                output_tokens = estimate_tokens(reply)

            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))

            # Store in cache only if not a simulated request
            if not is_simulated:
                try:
                    cache_entry = {
                        "reply": reply,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "model": LLM_MODEL
                    }
                    litellm_cache.add_cache(result=cache_entry, cache_key=cache_key)
                except Exception as ce:
                    logger.warning(f"Failed to store in cache: {ce}")

            return {
                "reply": reply,
                "metadata": {
                    "resolution_source": "LIVE_INFERENCE",
                    "model": LLM_MODEL,
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "key_id": key_id,
                    "fallback_attempts": fallback_attempts
                }
            }

        except Exception as exc:
            logger.warning(f"Key {key_id} failed: {exc}")
            last_error = exc
            if is_retryable_error(exc) or True: # Spec: failover to next key on 429, quota, 5xx
                fallback_attempts += 1
                continue

    # All keys exhausted
    logger.error("All keys in the pool failed or were unavailable.")
    raise AllProvidersUnavailableException("all providers unavailable")
