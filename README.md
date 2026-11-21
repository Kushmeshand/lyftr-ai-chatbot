# Lyftr AI - Resilient LLM Chatbot Gateway

A full-stack AI chatbot application featuring automatic multi-key failover across rate-limited and degraded LLM providers, instant LiteLLM response caching, persistent multi-turn SQLite conversation history, and an interactive modern React UI.

---

## 1. Live URLs

- **Live Frontend (Vercel)**: `https://lyftr-chatbot-frontend.vercel.app` *(deploy repository to Vercel)*
- **Live Backend (Render)**: `https://lyftr-chatbot-backend.onrender.com` *(deploy backend to Render)*
- **Public GitHub Repository**: `https://github.com/Kushmeshand/lyftr-llm-chatbot`
- **Demo Video (2-3 min)**: `https://drive.google.com/file/d/11bIFntfka4crR9JzO7Us5Un-xMnIJDi8/view?usp=drive_link`

---

## 2. Run locally: with Docker and without

### Environment Setup

Create your `.env` configuration file in the project root:

```bash
cp .env.example .env
```

Set at least two valid Gemini API keys in `.env`:
```env
LLM_API_KEYS=AIzaSyD...,AIzaSyB...
DATABASE_URL=sqlite:////data/app.db
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,*
ENABLE_FAILURE_SIMULATION=true
LLM_MODEL=gemini/gemini-2.0-flash
VITE_BACKEND_URL=http://localhost:8000
```

---

### Option A: Run with Docker (Recommended)

Requires Docker and Docker Compose installed.

1. **Start the whole stack**:
   ```bash
   make up
   ```
   *(Or run directly: `docker compose up --build -d`)*

2. **Access the application**:
   - Frontend UI: [http://localhost:3000](http://localhost:3000)
   - Backend API & Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Health Check: [http://localhost:8000/health](http://localhost:8000/health)

3. **Stop the stack**:
   ```bash
   make down
   ```

4. **Run backend automated tests**:
   ```bash
   make test
   ```

---

### Option B: Run locally without Docker

#### 1. Backend Setup (Python 3.11+)

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run backend test suite
pytest -v

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will start at `http://localhost:8000`.

#### 2. Frontend Setup (Node.js 18+)

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend will start at `http://localhost:3000`.

---

## 3. Design decisions: key fallback, caching, SQLite session storage

### Key Pool & Automatic Failover
- **Key Pool Architecture**: The gateway accepts a comma-separated list of API keys via `LLM_API_KEYS`, assigned sequential identifiers (`key_1`, `key_2`, etc.).
- **Graceful Error Recovery**: When an API key encounters HTTP 429 (Rate Limit), Quota Exhaustion (resource exhausted), or 5xx Server Errors (500, 502, 503, 504), the gateway catches the exception, increments `fallback_attempts`, and seamlessly falls back to the next available key in the pool.
- **Fail-Safe Contract**: If all configured keys fail or are exhausted, the gateway responds with HTTP 503 `{"detail": "all providers unavailable"}` without crashing, emitting stack traces, or writing partial state to the database.

### LiteLLM Response Caching
- **Built-in LiteLLM Caching**: Built directly on LiteLLM's `Cache` system (`litellm.cache = Cache(type="local")`).
- **Context-Aware Cache Key**: Cache keys are computed from `model` and the full message list (`system_prompt` + previous conversation history + new message). Crucially, the cache key **does not include the `session_id`**. Therefore, a brand new session with an identical initial prompt immediately receives an `LLM_CACHE` hit.
- **Deterministic Usage**: Cache hits report `resolution_source="LLM_CACHE"`, `key_id=null`, `fallback_attempts=0`, and preserve the exact token counts from the original completion.
- **Simulation Isolation**: When failure simulation headers are provided, cache lookup is bypassed and results are not stored in cache, guaranteeing clean failover demonstration without polluting cache entries.

### SQLite Session Storage
- **Isolated & Persistent**: Stored as a single SQLite file (`DATABASE_URL=sqlite:////data/app.db`) mounted to a Docker named volume (`sqlite_data`). Data persists across container restarts and builds.
- **Strict Transaction Handling**: Only successful user requests and completed assistant replies are saved to SQLite. Failed requests (422 validation errors or 503 provider outages) never enter session history.
- **Indexed History Retrieval**: Messages are indexed by `session_id` and retrieved chronologically (`ORDER BY id ASC`), feeding prior turns directly into multi-turn LLM completions while omitting system prompts from history endpoint output.

---

## 4. Verification: how to see failover, cache hits and per-message token usage

### 1. Verification of Key Failover (`X-Simulate-Failure`)

When `ENABLE_FAILURE_SIMULATION=true`, send `X-Simulate-Failure` headers to test failover scenarios without exhausting real quota:

#### Failover from `key_1` to `key_2` (HTTP 429):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id": "s-verify-1", "message": "What is the capital of France?"}'
```
**Expected response**:
- Status: `200 OK`
- `metadata.resolution_source`: `"LIVE_INFERENCE"`
- `metadata.key_id`: `"key_2"`
- `metadata.fallback_attempts`: `1`

#### Failover from `key_1` to `key_2` (HTTP 500):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=500" \
  -d '{"session_id": "s-verify-2", "message": "What is the capital of France?"}'
```
**Expected response**:
- Status: `200 OK`
- `metadata.key_id`: `"key_2"`
- `metadata.fallback_attempts`: `1`

#### Complete Outage / All Keys Fail (`*=429`):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id": "s-verify-fail", "message": "Hello"}'
```
**Expected response**:
- Status: `503 Service Unavailable`
- Body: `{"detail": "all providers unavailable"}`
- Nothing added to SQLite database (`GET /sessions/s-verify-fail/messages` returns 404).

---

### 2. Verification of Response Caching

1. Send a new prompt in Session 1:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id": "session-A", "message": "Explain solar energy in one sentence."}'
   ```
   **Result**: `resolution_source`: `"LIVE_INFERENCE"`, `latency_ms` ~ 800-1200 ms, `key_id`: `"key_1"`.

2. Send the identical prompt in Session 2:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id": "session-B", "message": "Explain solar energy in one sentence."}'
   ```
   **Result**: `resolution_source`: `"LLM_CACHE"`, `latency_ms` ~ 1-5 ms, `key_id`: `null`, identical `reply`, identical `input_tokens` and `output_tokens`.

---

### 3. Verification of Per-Request Token Usage

- In the frontend UI and JSON response, every assistant message displays `input_tokens` and `output_tokens`.
- Sending equal-length prompts in new sessions will report identical or near-identical `input_tokens` (measuring only `system_prompt` + `history` + `message`, never a cumulative running total).

---

### 4. Running Backend Automated Tests

Run the full pytest suite (9 tests covering health, 422 validations, 404 session handling, failover, caching, and multi-turn state):
```bash
cd backend
pytest -v
```

---

## 5. Setup Used: your editor and AI tools

- **Editor**: Visual Studio Code / JetBrains Fleet
- **AI Tools**: Google Antigravity (Gemini 2.0 / Gemini 3.8 Flash)
- **Runtime Environment**: Python 3.11.9, Node.js v24.18.0, Docker Engine & Compose
- **Key Libraries**:
  - `FastAPI 0.110+` & `Uvicorn` for high-performance ASGI API serving
  - `LiteLLM 1.40+` for unified LLM gateway orchestration and built-in caching
  - `React 18` + `Vite 5` + `Tailwind CSS` for responsive, accessible web UI
  - `Lucide React` for clean iconography

---

## 6. Bonus features (if any): what you added beyond the requirements and why

1. **Integrated In-App Failover Simulator**:
   - Added a settings drawer directly in the frontend header allowing evaluators to simulate failure scenarios (`key_1=429`, `key_1=500`, `*=429`) with a single dropdown selection during live demonstrations or recordings.
2. **Real-time Gateway Health Monitor**:
   - The UI includes an automatic health-check poller displaying live backend status, active key pool count, and cache operational status in the header.
3. **Comprehensive Automated Test Suite**:
   - 9 full unit and integration tests (`test_api.py`, `test_failover.py`, `test_caching.py`) testing every error status code (422, 404, 503), multi-turn context retention, cache bypass, and mockable failover scenarios.
4. **Enhanced UI / UX & Presets**:
   - Modern dark mode styling with smooth scroll-to-bottom, keyboard shortcut support (Enter to send, Shift+Enter for newline), quick sample prompt buttons, and clear error banners.
