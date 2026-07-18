from __future__ import annotations

from contextvars import ContextVar
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from paper_wiki.core.logging import configure_logging

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_web_logging(verbose: bool = False) -> None:
    configure_logging(verbose)
    request_filter = RequestIDFilter()
    for logger_name in ("uvicorn.access", "uvicorn.error", "paper_wiki.web"):
        logging.getLogger(logger_name).addFilter(request_filter)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        logger = logging.getLogger("paper_wiki.web.access")
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s status=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            request_id_var.reset(token)
