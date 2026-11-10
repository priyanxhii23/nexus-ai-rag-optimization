"""Centralised error handling.

Every error leaves the API in one shape:
    {"error": {"code": "...", "message": "...", "request_id": "..."}}
Internal details (stack traces, SQL, file paths) are logged, never returned.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_var

log = get_logger("errors")


class AppError(Exception):
    """An expected, user-facing error (bad input, missing document, ...)."""

    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request", extra: dict | None = None):
        super().__init__(message)
        self.message, self.status_code, self.code, self.extra = message, status_code, code, extra or {}


def _body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id_var.get(), **extra}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, **exc.extra), status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large", 429: "rate_limited"}.get(
            exc.status_code, "http_error")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg", "")}
                  for e in exc.errors()]
        return JSONResponse(_body("validation_error", "The request is invalid.", fields=fields), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(_body("internal_error", "Something went wrong on the server. See data/logs/nexus.log."),
                            status_code=500)
