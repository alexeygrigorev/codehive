"""Unified error handling: ErrorResponse schema, exception handlers, request ID middleware."""

import logging
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error code mapping from HTTP status codes
# ---------------------------------------------------------------------------
_STATUS_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "auth_error",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


def _error_code_for_status(status_code: int) -> str:
    """Return a short error code string for the given HTTP status code."""
    if status_code in _STATUS_TO_ERROR:
        return _STATUS_TO_ERROR[status_code]
    if 400 <= status_code < 500:
        return "client_error"
    return "internal_error"


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Unified error response returned by all error handlers."""

    error: str
    detail: str | list
    request_id: str
    status_code: int


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------


def _get_request_id(request: Request) -> str:
    """Return the request ID from the header or generate a new UUID."""
    header_value = request.headers.get("x-request-id")
    if header_value:
        return header_value
    return str(uuid.uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and echo it in the response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _get_request_id(request)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def _get_request_id_from_request(request: Request) -> str:
    """Safely extract request_id from request.state."""
    return getattr(request.state, "request_id", str(uuid.uuid4()))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Re-format FastAPI/Starlette HTTPException into ErrorResponse."""
    request_id = _get_request_id_from_request(request)
    body = ErrorResponse(
        error=_error_code_for_status(exc.status_code),
        detail=exc.detail,
        request_id=request_id,
        status_code=exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 with field-level validation errors."""
    request_id = _get_request_id_from_request(request)
    # Sanitise errors: strip the 'ctx' key which may contain non-serializable
    # exception objects, and keep only JSON-safe fields.
    sanitised = []
    for err in exc.errors():
        clean = {
            "loc": err.get("loc"),
            "msg": err.get("msg"),
            "type": err.get("type"),
        }
        if "input" in err:
            clean["input"] = err["input"]
        sanitised.append(clean)
    body = ErrorResponse(
        error="validation_error",
        detail=sanitised,
        request_id=request_id,
        status_code=422,
    )
    return JSONResponse(
        status_code=422,
        content=body.model_dump(),
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: return a safe 500 and log the full traceback."""
    request_id = _get_request_id_from_request(request)
    logger.error(
        "Unhandled exception (request_id=%s):\n%s",
        request_id,
        traceback.format_exc(),
    )
    body = ErrorResponse(
        error="internal_error",
        detail="An internal error occurred. Please try again later.",
        request_id=request_id,
        status_code=500,
    )
    return JSONResponse(
        status_code=500,
        content=body.model_dump(),
        headers={"X-Request-ID": request_id},
    )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_error_handling(app: FastAPI) -> None:
    """Register request-ID middleware and all exception handlers on *app*."""
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]
