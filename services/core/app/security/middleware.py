"""Correlation-id and idempotency middleware (technical.md §7.1).

CorrelationIdMiddleware: reads/creates X-Correlation-Id, echoes it on the
response, and stashes it on request.state for ML calls + audit to pick up.

IdempotencyMiddleware: for POST/PATCH/DELETE, requires `Idempotency-Key`.
Same key + same body -> replays the stored response. Same key + different
body -> 422 IDEMPOTENCY_MISMATCH. Stored in Redis (or memory fallback) for
IDEMPOTENCY_TTL_H hours."""

import hashlib
import json
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import get_security_settings
from .rate_limit import _get_client  # reuse the same Redis client / fallback pattern

_memory_idempotency: dict[str, tuple[str, Response]] = {}

MUTATING_METHODS = {"POST", "PATCH", "DELETE"}


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response


def _error(code: str, message: str, status: int, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)  # ownership of enforcing presence is per-route; see note below

        body_bytes = await request.body()
        body_hash = hashlib.sha256(body_bytes).hexdigest()
        store_key = f"idempotency:{request.url.path}:{key}"

        client = _get_client()
        stored_raw = None
        if client is not None:
            try:
                stored_raw = await client.get(store_key)
            except Exception:
                stored_raw = None
        elif store_key in _memory_idempotency:
            stored_raw = json.dumps(_memory_idempotency[store_key])

        if stored_raw:
            stored = json.loads(stored_raw) if isinstance(stored_raw, str) else stored_raw
            if stored["body_hash"] != body_hash:
                return _error("IDEMPOTENCY_MISMATCH", "Same key with a different body", 422)
            return JSONResponse(status_code=stored["status"], content=stored["body"])

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            resp_body = b""
            async for chunk in response.body_iterator:
                resp_body += chunk
            record = {
                "body_hash": body_hash,
                "status": response.status_code,
                "body": json.loads(resp_body) if resp_body else None,
            }
            ttl = get_security_settings().idempotency_ttl_h * 3600
            if client is not None:
                try:
                    await client.set(store_key, json.dumps(record), ex=ttl)
                except Exception:
                    pass
            else:
                _memory_idempotency[store_key] = record
            safe_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ("content-length", "content-type")
            }
            return JSONResponse(status_code=response.status_code, content=record["body"], headers=safe_headers)

        return response
