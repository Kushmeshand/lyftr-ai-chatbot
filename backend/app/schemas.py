from typing import Optional, List, Literal, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Message cannot be empty or only whitespace")
        if len(trimmed) > 4000:
            raise ValueError("Message cannot exceed 4000 characters after trimming whitespace")
        return trimmed

class ChatMetadata(BaseModel):
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str] = None
    fallback_attempts: int

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata

class HealthResponse(BaseModel):
    status: str
    keys_configured: int
    cache_enabled: bool

class MessageMetadata(BaseModel):
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    input_tokens: int
    output_tokens: int

class MessageItem(BaseModel):
    role: str
    content: str
    metadata: Optional[Union[MessageMetadata, Dict[str, Any]]] = None

class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: List[MessageItem]
