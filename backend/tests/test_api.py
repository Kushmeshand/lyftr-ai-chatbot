import pytest
from fastapi.testclient import TestClient
import os

# Ensure test DB
os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"

from app.main import app
from app.database import init_db, get_session_messages

@pytest.fixture(autouse=True)
def setup_test_db():
    if os.path.exists("./test_api.db"):
        os.remove("./test_api.db")
    init_db()
    yield
    if os.path.exists("./test_api.db"):
        os.remove("./test_api.db")

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] >= 2
    assert data["cache_enabled"] is True

def test_validation_errors():
    # Empty message
    resp = client.post("/chat", json={"session_id": "s-123", "message": "   "})
    assert resp.status_code == 422
    assert "detail" in resp.json()

    # Missing session_id
    resp = client.post("/chat", json={"message": "hello"})
    assert resp.status_code == 422
    assert "detail" in resp.json()

    # Message over 4000 characters
    long_msg = "a" * 4001
    resp = client.post("/chat", json={"session_id": "s-123", "message": long_msg})
    assert resp.status_code == 422
    assert "detail" in resp.json()

    # Empty session_id
    resp = client.post("/chat", json={"session_id": "", "message": "hello"})
    assert resp.status_code == 422
    assert "detail" in resp.json()

def test_unknown_session_404():
    resp = client.get("/sessions/unknown-session-9999/messages")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "session not found"}
