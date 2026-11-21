import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_failover.db"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"

from app.main import app
from app.database import init_db, get_session_messages

@pytest.fixture(autouse=True)
def setup_test_db():
    if os.path.exists("./test_failover.db"):
        os.remove("./test_failover.db")
    init_db()
    yield
    if os.path.exists("./test_failover.db"):
        os.remove("./test_failover.db")

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

def test_key_1_fails_with_429_failover_to_key_2():
    with patch("litellm.completion", return_value=make_mock_completion()) as mock_llm:
        resp = client.post(
            "/chat",
            json={"session_id": "s-test-fail-1", "message": "What is the capital of France?"},
            headers={"X-Simulate-Failure": "key_1=429"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "The capital of France is Paris."
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1
        assert data["metadata"]["resolution_source"] == "LIVE_INFERENCE"

def test_key_1_fails_with_500_failover_to_key_2():
    with patch("litellm.completion", return_value=make_mock_completion()) as mock_llm:
        resp = client.post(
            "/chat",
            json={"session_id": "s-test-fail-2", "message": "What is the capital of France?"},
            headers={"X-Simulate-Failure": "key_1=500"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "The capital of France is Paris."
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1
        assert data["metadata"]["resolution_source"] == "LIVE_INFERENCE"

def test_all_keys_fail_returns_503_and_empty_history():
    with patch("litellm.completion", return_value=make_mock_completion()):
        resp = client.post(
            "/chat",
            json={"session_id": "s-test-all-fail", "message": "What is the capital of France?"},
            headers={"X-Simulate-Failure": "*=429"}
        )
        assert resp.status_code == 503
        assert resp.json() == {"detail": "all providers unavailable"}

        # Verify nothing was added to history
        hist_resp = client.get("/sessions/s-test-all-fail/messages")
        assert hist_resp.status_code == 404
        assert hist_resp.json() == {"detail": "session not found"}
