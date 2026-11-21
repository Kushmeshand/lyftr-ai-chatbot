import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

from app.config import (
    KEY_POOL,
    ALLOWED_ORIGINS,
    DEFAULT_SYSTEM_PROMPT
)
from app.database import (
    init_db,
    check_db_health,
    get_session_messages,
    session_exists,
    add_message
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SessionMessagesResponse
)
from app.llm_gateway import (
    execute_chat,
    AllProvidersUnavailableException
)

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema
    init_db()
    yield

app = FastAPI(
    title="Lyftr AI - Resilient LLM Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def get_root():
    return {
        "status": "ok",
        "service": "Lyftr AI Gateway",
        "health": "/health",
        "docs": "/docs"
    }

# Custom exception handlers ensuring strict {"detail": ...} JSON contract
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(AllProvidersUnavailableException)
async def all_providers_exception_handler(request: Request, exc: AllProvidersUnavailableException):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "all providers unavailable"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal server error"}
    )

@app.get("/health", response_model=HealthResponse)
def get_health():
    """
    Returns 200 once app is running, DB is reachable and key pool is loaded.
    """
    if not check_db_health():
        raise HTTPException(status_code=500, detail="Database unreachable")
    return {
        "status": "ok",
        "keys_configured": len(KEY_POOL),
        "cache_enabled": True
    }

@app.post("/chat", response_model=ChatResponse)
def post_chat(
    req: ChatRequest,
    x_simulate_failure: Optional[str] = Header(None, alias="X-Simulate-Failure")
):
    """
    Handles multi-turn chat with failover across API keys and response caching.
    """
    # 1. Fetch previous session messages for multi-turn context
    history = get_session_messages(req.session_id)

    # 2. Build full message sequence for the LLM
    llm_messages = []
    active_prompt = req.system_prompt.strip() if req.system_prompt and req.system_prompt.strip() else DEFAULT_SYSTEM_PROMPT
    if active_prompt:
        llm_messages.append({"role": "system", "content": active_prompt})

    for h in history:
        llm_messages.append({"role": h["role"], "content": h["content"]})
    
    # Append the new user message
    llm_messages.append({"role": "user", "content": req.message})

    # 3. Execute completion with failover and caching
    try:
        result = execute_chat(
            llm_messages=llm_messages,
            simulate_header=x_simulate_failure
        )
    except AllProvidersUnavailableException:
        # Crucial: Failed requests must NOT be saved to session history
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="all providers unavailable"
        )
    except Exception as exc:
        logger.error(f"Error during chat completion: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="all providers unavailable"
        )

    # 4. Only persist to SQLite upon successful completion
    # Save user message
    add_message(
        session_id=req.session_id,
        role="user",
        content=req.message,
        metadata=None
    )

    # Save assistant message
    assistant_meta = {
        "resolution_source": result["metadata"]["resolution_source"],
        "input_tokens": result["metadata"]["input_tokens"],
        "output_tokens": result["metadata"]["output_tokens"]
    }
    add_message(
        session_id=req.session_id,
        role="assistant",
        content=result["reply"],
        metadata=assistant_meta
    )

    return {
        "session_id": req.session_id,
        "reply": result["reply"],
        "metadata": result["metadata"]
    }

@app.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_history(session_id: str):
    """
    Returns the stored history of one session from SQLite, oldest first, without system prompt.
    """
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    
    messages = get_session_messages(session_id)
    return {
        "session_id": session_id,
        "messages": messages
    }
