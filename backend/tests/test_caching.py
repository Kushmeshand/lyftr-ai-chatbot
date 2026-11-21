import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_caching.db"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"

from app.main import app
from app.database import init_db, get_session_messages
from app.llm_gateway import litellm_cache

@pytest.fixture(autouse=True)
def setup_test_db():
    if os.path.exists("./test_caching.db"):
        os.remove("./test_caching.db")
    init_db()
    # Reset in-memory cache if possible
    if hasattr(litellm_cache, "cache") and hasattr(litellm_cache.cache, "cache_dict"):
        litellm_cache.cache.cache_dict.clear()
    yield
    if os.path.exists("./test_caching.db"):
        os.remove("./test_caching.db")

client = TestClient(app)

def make_mock_completion(content="The capital of France is Paris."):
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp.choices = [mock_choice]
    mock_resp.usage.prompt_tokens = 42
    mock_resp.usage.completion_tokens = 9
    mock_resp.model = "gemini/gemini-2.0-flash"
    return mock_resp

def test_cache_hit_on_same_prompt_in_new_session():
    with patch("litellm.completion", return_value=make_mock_completion()) as mock_llm:
        # 1. First call in session 1 -> LIVE_INFERENCE
        resp1 = client.post(
            "/chat",
            json={"session_id": "session-1", "message": "What is the capital of France?"}
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert data1["metadata"]["key_id"] == "key_1"
        assert data1["metadata"]["fallback_attempts"] == 0
        assert data1["metadata"]["input_tokens"] == 42
        assert data1["metadata"]["output_tokens"] == 9
        assert mock_llm.call_count == 1

        # 2. Same first message in new session 2 -> LLM_CACHE
        resp2 = client.post(
            "/chat",
            json={"session_id": "session-2", "message": "What is the capital of France?"}
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["metadata"]["resolution_source"] == "LLM_CACHE"
        assert data2["metadata"]["key_id"] is None
        assert data2["metadata"]["fallback_attempts"] == 0
        assert data2["metadata"]["input_tokens"] == 42
        assert data2["metadata"]["output_tokens"] == 9
        assert data2["reply"] == data1["reply"]
        # LLM completion should NOT have been called a second time
        assert mock_llm.call_count == 1

def test_multi_turn_history_and_persistence():
    call_args_list = []
    def custom_completion(*args, **kwargs):
        call_args_list.append(kwargs.get("messages", []))
        resp = make_mock_completion("About 2.1 million people.")
        return resp

    with patch("litellm.completion", side_effect=custom_completion):
        # Turn 1
        resp1 = client.post(
            "/chat",
            json={"session_id": "session-multi", "message": "What is the capital of France?"}
        )
        assert resp1.status_code == 200

        # Turn 2
        resp2 = client.post(
            "/chat",
            json={"session_id": "session-multi", "message": "What is its population?"}
        )
        assert resp2.status_code == 200

        # Verify messages sent to LLM on turn 2 contained previous history
        assert len(call_args_list) == 2
        second_call_msgs = call_args_list[1]
        user_msgs = [m for m in second_call_msgs if m.get("role") == "user"]
        assistant_msgs = [m for m in second_call_msgs if m.get("role") == "assistant"]
        assert len(user_msgs) == 2
        assert user_msgs[0]["content"] == "What is the capital of France?"
        assert user_msgs[1]["content"] == "What is its population?"
        assert len(assistant_msgs) == 1

        # Verify GET /sessions/{session_id}/messages
        hist_resp = client.get("/sessions/session-multi/messages")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["session_id"] == "session-multi"
        assert len(hist_data["messages"]) == 4
        assert hist_data["messages"][0]["role"] == "user"
        assert hist_data["messages"][1]["role"] == "assistant"
        assert "metadata" in hist_data["messages"][1]
        assert hist_data["messages"][1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"

def test_simulated_failure_bypasses_cache():
    with patch("litellm.completion", return_value=make_mock_completion()) as mock_llm:
        # Cache is populated first
        client.post(
            "/chat",
            json={"session_id": "s-cache-prep", "message": "Cache bypass test query"}
        )
        assert mock_llm.call_count == 1

        # Now send same query with simulation header -> should bypass cache
        resp = client.post(
            "/chat",
            json={"session_id": "s-cache-bypass", "message": "Cache bypass test query"},
            headers={"X-Simulate-Failure": "key_1=429"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1
        assert mock_llm.call_count == 2
