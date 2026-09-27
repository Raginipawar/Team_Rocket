"""FastAPI auth dependencies -- the interface work-distribution.md §4.1 promises
to B: get_current_user, require_role(*roles), require_hospital_scope,
require_ambulance_scope. RBAC + ownership are enforced here, never UI-only
(technical.md §18), so every router in services/core just depends on these."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .jwt import TokenError, decode_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    role: str
    hospital_id: str | None = None
    ambulance_id: str | None = None


def _unauthenticated(message: str = "missing or invalid token") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": {"code": "UNAUTHENTICATED", "message": message, "details": {}}},
    )


def _forbidden(message: str = "not allowed") -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={"error": {"code": "FORBIDDEN", "message": message, "details": {}}},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    token = credentials.credentials if credentials else request.query_params.get("token")
    if not token:
        raise _unauthenticated()

    try:
        claims = decode_token(token, expect_type="access")
    except TokenError as exc:
        raise _unauthenticated(str(exc)) from exc

    return CurrentUser(
        id=claims["sub"],
        role=claims["role"],
        hospital_id=claims.get("hospital_id"),
        ambulance_id=claims.get("ambulance_id"),
    )


def require_role(*roles: str):
    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise _forbidden(f"requires role in {roles}")
        return user

    return _dep


def require_hospital_scope(hospital_id_param: str = "hospital_id"):
    """Staff may only act on their own hospital_id (path/query param must match)."""

    async def _dep(request: Request, user: CurrentUser = Depends(require_role("hospital_staff"))) -> CurrentUser:
        target = request.path_params.get(hospital_id_param) or request.query_params.get(hospital_id_param)
        if target and target != user.hospital_id:
            raise _forbidden("not scoped to this hospital")
        return user

    return _dep


def require_ambulance_scope(ambulance_id_param: str = "ambulance_id"):
    """Paramedics may only act on their own ambulance_id."""

    async def _dep(request: Request, user: CurrentUser = Depends(require_role("paramedic"))) -> CurrentUser:
        target = request.path_params.get(ambulance_id_param) or request.query_params.get(ambulance_id_param)
        if target and target != user.ambulance_id:
            raise _forbidden("not scoped to this ambulance")
        return user

    return _dep
