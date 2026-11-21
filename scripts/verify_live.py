import os
import sys
import time
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

from app.config import KEY_POOL, LLM_MODEL, ENABLE_FAILURE_SIMULATION
from app.llm_gateway import execute_chat, AllProvidersUnavailableException

def main():
    print("=" * 60)
    print("PHASE 1: LIVE GEMINI API & GATEWAY VERIFICATION")
    print("=" * 60)

    # 1. Key pool verification
    print(f"\n1. Checking Key Pool:")
    print(f"   Configured keys count: {len(KEY_POOL)}")
    for k in KEY_POOL:
        is_set = bool(k["api_key"] and len(k["api_key"]) > 15 and "PASTE" not in k["api_key"])
        print(f"   - {k['key_id']}: {'[LOADED]' if is_set else '[MISSING/INVALID]'}")

    if any("PASTE" in k["api_key"] or "placeholder" in k["api_key"] or "dummy" in k["api_key"] for k in KEY_POOL):
        print("\n❌ Error: Placeholder keys detected in .env!")
        print("   Please edit .env and insert your real Gemini API keys.")
        sys.exit(1)

    # 2. Live inference test with key_1
    print(f"\n2. Testing Live Gemini Inference ({LLM_MODEL}):")
    test_messages = [{"role": "user", "content": "What is the capital of France? Answer in one short sentence."}]
    
    t0 = time.perf_counter()
    res1 = execute_chat(test_messages)
    elapsed1 = int((time.perf_counter() - t0) * 1000)
    
    print(f"   ✅ Reply: {res1['reply'].strip()}")
    print(f"   - Resolution: {res1['metadata']['resolution_source']}")
    print(f"   - Key Used: {res1['metadata']['key_id']}")
    print(f"   - Fallback Attempts: {res1['metadata']['fallback_attempts']}")
    print(f"   - Input Tokens: {res1['metadata']['input_tokens']}")
    print(f"   - Output Tokens: {res1['metadata']['output_tokens']}")
    print(f"   - Latency: {res1['metadata']['latency_ms']} ms (wall clock: {elapsed1} ms)")

    assert res1['metadata']['resolution_source'] == "LIVE_INFERENCE", "Expected LIVE_INFERENCE"
    assert res1['metadata']['key_id'] == "key_1", "Expected key_1 to answer"

    # 3. Response Caching Test
    print(f"\n3. Testing LiteLLM Response Caching (Identical Query):")
    t0 = time.perf_counter()
    res2 = execute_chat(test_messages)
    elapsed2 = int((time.perf_counter() - t0) * 1000)

    print(f"   ✅ Reply: {res2['reply'].strip()}")
    print(f"   - Resolution: {res2['metadata']['resolution_source']}")
    print(f"   - Key ID: {res2['metadata']['key_id']}")
    print(f"   - Latency: {res2['metadata']['latency_ms']} ms (wall clock: {elapsed2} ms)")
    
    assert res2['metadata']['resolution_source'] == "LLM_CACHE", "Expected LLM_CACHE"
    assert res2['metadata']['key_id'] is None, "Expected key_id=None on cache hit"
    assert res2['reply'] == res1['reply'], "Expected identical response text"
    assert res2['metadata']['input_tokens'] == res1['metadata']['input_tokens'], "Expected identical input tokens"
    assert res2['metadata']['output_tokens'] == res1['metadata']['output_tokens'], "Expected identical output tokens"
    print("   ✅ Cache verified: Returned identical reply and tokens with key_id=null!")

    # 4. Failover Simulation Test (key_1=429 -> key_2)
    print(f"\n4. Testing Key Failover (X-Simulate-Failure: key_1=429):")
    res3 = execute_chat(test_messages, simulate_header="key_1=429")
    print(f"   ✅ Reply: {res3['reply'].strip()}")
    print(f"   - Resolution: {res3['metadata']['resolution_source']}")
    print(f"   - Key ID: {res3['metadata']['key_id']}")
    print(f"   - Fallback Attempts: {res3['metadata']['fallback_attempts']}")

    assert res3['metadata']['resolution_source'] == "LIVE_INFERENCE", "Expected LIVE_INFERENCE"
    assert res3['metadata']['key_id'] == "key_2", "Expected failover to key_2"
    assert res3['metadata']['fallback_attempts'] == 1, "Expected 1 fallback attempt"
    print("   ✅ Failover verified: Automatically fell back to key_2!")

    # 5. Complete Failure Simulation Test (*=429 -> 503)
    print(f"\n5. Testing Total Provider Outage (X-Simulate-Failure: *=429):")
    try:
        execute_chat(test_messages, simulate_header="*=429")
        print("   ❌ Error: Expected AllProvidersUnavailableException, but call succeeded!")
        sys.exit(1)
    except AllProvidersUnavailableException:
        print("   ✅ Correctly caught AllProvidersUnavailableException (503)!")

    print("\n" + "=" * 60)
    print("🎉 ALL PHASE 1 LIVE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
