from pydantic import BaseModel
from typing import Any, Dict
from app.core.error_codes import ErrorCode


class Message(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error_code: ErrorCode
    user_message: str | None = None
    details: Dict[str, Any] | None = None