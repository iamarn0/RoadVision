from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCodes:
    VIDEO_INVALID = "VIDEO_INVALID"
    VIDEO_UNSUPPORTED = "VIDEO_UNSUPPORTED"
    VIDEO_CORRUPTED = "VIDEO_CORRUPTED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    CUDA_OUT_OF_MEMORY = "CUDA_OUT_OF_MEMORY"
    OCR_INITIALIZATION_FAILED = "OCR_INITIALIZATION_FAILED"
    WORKER_UNAVAILABLE = "WORKER_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    EXPORT_FAILED = "EXPORT_FAILED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"


class ApiErrorBody(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] = {}


class AppError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiErrorBody(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        ).model_dump(),
    )


def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error_code" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiErrorBody(
            error_code=ErrorCodes.VALIDATION_ERROR if exc.status_code < 500 else ErrorCodes.PROCESSING_FAILED,
            message=str(detail),
            details={},
        ).model_dump(),
    )
