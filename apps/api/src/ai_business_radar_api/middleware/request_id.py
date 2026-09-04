"""Request correlation ID middleware."""

import logging
import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger(__name__)


def resolve_request_id(candidate: str | None) -> str:
    if candidate is not None:
        normalized = candidate.strip()
        if _SAFE_REQUEST_ID.fullmatch(normalized):
            return normalized
    return str(uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)

        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "request method=%s path=%s status=%s request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                request_id,
            )
            return response
        finally:
            request_id_context.reset(token)
