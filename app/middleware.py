from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_ID_PATTERN = re.compile(r"req-[0-9a-f]{8}")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Start each request with a clean context so metadata cannot leak between requests.
        clear_contextvars()

        requested_id = request.headers.get("x-request-id", "")
        correlation_id = (
            requested_id
            if REQUEST_ID_PATTERN.fullmatch(requested_id)
            else f"req-{uuid.uuid4().hex[:8]}"
        )
        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = correlation_id
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"
            return response
        finally:
            clear_contextvars()
