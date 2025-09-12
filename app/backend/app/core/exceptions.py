from fastapi import HTTPException, status
from typing import Any, Dict
from app.core.error_codes import ErrorCode

class AppException(HTTPException):
    def __init__(
        self,
        *,
        error_code: ErrorCode,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        user_message: str | None = None,
        details: Dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={"error_code": error_code, "user_message": user_message, "details": details},
        )
        self.error_code = error_code
        self.details = details

def raise_error(
    code: ErrorCode,
    status_code: int,
    user_message: str | None = None,
    details: Dict[str, Any] | None = None,
) -> None:
    raise AppException(error_code=code, status_code=status_code, user_message=user_message, details=details)
