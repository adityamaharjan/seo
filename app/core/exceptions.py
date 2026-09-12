"""Custom exception hierarchy and FastAPI handlers.

All application errors derive from :class:`AppException` and are serialized
into a consistent envelope::

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """Base class for all expected, handled application errors."""

    status_code: int = 400
    code: str = "bad_request"
    message: str = "Bad request"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppException):
    status_code = 400
    code = "bad_request"
    message = "Bad request"


class ServiceUnavailableError(AppException):
    status_code = 503
    code = "service_unavailable"
    message = "A required service is temporarily unavailable"


class NotFoundError(AppException):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppException):
    status_code = 409
    code = "conflict"
    message = "Resource already exists"


class AuthenticationError(AppException):
    status_code = 401
    code = "authentication_failed"
    message = "Could not validate credentials"


class PermissionError_(AppException):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action"


class QuotaExceededError(AppException):
    status_code = 429
    code = "quota_exceeded"
    message = "Quota exceeded"


def _serializable_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten pydantic errors into something JSON can encode.

    Pydantic puts the original exception object in ``ctx`` whenever a custom
    validator raises, which is not serializable and would leak internals, so
    it is dropped and only the rendered message is kept.
    """
    cleaned: list[dict[str, Any]] = []
    for err in errors:
        item: dict[str, Any] = {
            "type": err.get("type"),
            "loc": [str(part) for part in err.get("loc", ())],
            "msg": err.get("msg"),
        }
        if "input" in err:
            try:
                json.dumps(err["input"])
                item["input"] = err["input"]
            except (TypeError, ValueError):
                item["input"] = str(err["input"])
        cleaned.append(item)
    return cleaned


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exc(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_error",
                "Request validation failed",
                _serializable_errors(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exc(_: Request, exc: Exception) -> JSONResponse:
        # Last-resort handler; details are intentionally omitted from the body.
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "An internal error occurred"),
        )
