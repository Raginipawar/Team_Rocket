"""Base HTTP client for calling services/ml (technical.md §9). Every capability
has a timeout; on timeout/failure the caller gets a typed MLUnavailable so the
domain layer can apply its documented fallback (e.g. triage failure -> acuity
critical/needs_review=true, never a silent None)."""

import os

import httpx

ML_BASE_URL = os.getenv("ML_BASE_URL", "http://localhost:8001")


class MLUnavailable(Exception):
    def __init__(self, capability: str, cause: Exception | None = None):
        self.capability = capability
        self.cause = cause
        super().__init__(f"ML capability '{capability}' unavailable: {cause}")


async def call_ml(
    method: str,
    path: str,
    *,
    capability: str,
    timeout_s: float,
    json: dict | None = None,
    files: dict | None = None,
    data: dict | None = None,
    params: dict | None = None,
) -> dict:
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=timeout_s) as client:
            response = await client.request(method, path, json=json, files=files, data=data, params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        raise MLUnavailable(capability, exc) from exc
