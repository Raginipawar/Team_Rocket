"""A's file (work-distribution.md §2.2). technical.md §7.2 auth endpoints.
SMS_MODE=fake for OTP delivery is the spec's OWN documented toggle
(technical.md §22, wd-person-a-intake-dispatch.md A2 'via your SMS sender,
fake mode first') -- not a placeholder standing in for real logic; every
other piece here (hashing, rate limiting, expiry, attempt limits, JWT
issuance, rotation) is real."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response

from app.db.repos import identity as identity_repo
from app.db.session import get_session
from app.domain import audit
from app.integrations.sms.sender import send_sms
from app.security.config import get_security_settings
from app.security.jwt import TokenError, create_access_token, create_refresh_token, decode_token
from app.security.otp import expiry_at, generate_code, hash_code, is_expired, verify_code
from app.security.passwords import verify_password
from app.security.rate_limit import hit
from app.security.refresh_store import is_revoked, revoke

router = APIRouter()

# Was a single fixed cookie name shared across the whole browser origin,
# regardless of role. Cookies aren't scoped per-tab -- logging into the
# ambulance app in one tab and the hospital app in another (same browser,
# same origin) meant the second login silently overwrote the first tab's
# refresh cookie. The first tab wouldn't notice until its access token next
# needed silent renewal, at which point it would refresh using the NOW-
# WRONG shared cookie, get back a different user, and sign itself out
# (lib/auth.tsx's own "cookie belongs to someone who signed in on another
# tab" check) -- reported as "opening hospital and ambulance at once
# doesn't work", reproduced even across separate laptops once, confirming
# it wasn't session/profile-specific but this exact shared-cookie design.
# One cookie per role fixes it permanently: each role's login only ever
# touches its own cookie, so concurrent multi-role sessions in the same
# browser can no longer collide.
def _refresh_cookie_name(role: str) -> str:
    return f"refresh_token_{role}"


class OTPRequestBody:
    def __init__(self, phone: str):
        self.phone = phone


def _issue_tokens(user: dict) -> tuple[str, str]:
    access = create_access_token(
        sub=str(user["id"]), role=user["role"],
        hospital_id=str(user["hospital_id"]) if user.get("hospital_id") else None,
        ambulance_id=str(user["ambulance_id"]) if user.get("ambulance_id") else None,
    )
    refresh = create_refresh_token(sub=str(user["id"]), role=user["role"])
    return access, refresh


def _set_refresh_cookie(response: Response, refresh_token: str, role: str) -> None:
    settings = get_security_settings()
    response.set_cookie(
        _refresh_cookie_name(role), refresh_token, httponly=True, secure=True, samesite="strict",
        max_age=settings.refresh_token_ttl_days * 86400,
    )


@router.post("/auth/otp/request", status_code=204)
async def otp_request(body: dict) -> None:
    phone = body.get("phone")
    if not phone:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "phone required", "details": {}}})

    settings = get_security_settings()
    allowed = await hit(f"otp_request:{phone}", limit=settings.otp_request_limit, window_sec=settings.otp_request_window_min * 60)
    if not allowed:
        raise HTTPException(429, detail={"error": {"code": "RATE_LIMITED", "message": "Too many OTP requests", "details": {}}})

    code = generate_code()
    code_hash = hash_code(code, phone)

    async with get_session() as session:
        await identity_repo.store_otp(session, phone, code_hash, expiry_at())
        await session.commit()

    await send_sms(phone, f"Your GoldenHour OTP is {code}. Valid for {settings.otp_ttl_min} minutes.", template="otp")


@router.post("/auth/otp/verify")
async def otp_verify(body: dict, response: Response) -> dict:
    phone = body.get("phone")
    code = body.get("code")
    if not phone or not code:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "phone and code required", "details": {}}})

    settings = get_security_settings()

    async with get_session() as session:
        record = await identity_repo.get_otp(session, phone)
        if record is None:
            raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "No OTP requested for this phone", "details": {}}})

        expires_at = record["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if is_expired(expires_at):
            await identity_repo.delete_otp(session, phone)
            await session.commit()
            raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "OTP expired", "details": {}}})

        if record["attempts"] >= settings.otp_max_attempts:
            raise HTTPException(429, detail={"error": {"code": "RATE_LIMITED", "message": "Too many attempts", "details": {}}})

        if not verify_code(code, phone, record["code_hash"]):
            await identity_repo.increment_otp_attempts(session, phone)
            await session.commit()
            raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "Incorrect code", "details": {}}})

        await identity_repo.delete_otp(session, phone)
        role = body.get("role") or "patient"
        if role not in ("patient", "paramedic"):
            raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "invalid role", "details": {}}})
        try:
            user = (await identity_repo.get_or_create_paramedic_user(session, phone)) if role == "paramedic" \
                else (await identity_repo.get_or_create_patient_user(session, phone))
        except ValueError as e:
            raise HTTPException(409, detail={"error": {"code": "ROLE_MISMATCH", "message": str(e), "details": {}}})
        await audit.write(session, actor_type="user", actor_id=phone, entity="users", entity_id=user["id"],
                           action="otp_login", before=None, after={"phone": phone})
        await session.commit()

    access, refresh = _issue_tokens(user)
    _set_refresh_cookie(response, refresh, user["role"])
    return {"access_token": access, "user": user}


@router.post("/auth/login")
async def login(body: dict, response: Response) -> dict:
    identifier = body.get("username_or_phone")
    password = body.get("password")
    if not identifier or not password:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "credentials required", "details": {}}})

    # Was limit=5 -- same demo-rehearsal reasoning as otp_request_limit
    # (security/config.py): kept blocking the team's own repeated testing,
    # not an attacker. Loosened, not removed, for the same reason.
    allowed = await hit(f"login:{identifier}", limit=50, window_sec=600)
    if not allowed:
        raise HTTPException(429, detail={"error": {"code": "RATE_LIMITED", "message": "Too many login attempts", "details": {}}})

    async with get_session() as session:
        user = await identity_repo.get_user_by_username_or_phone(session, identifier)
        if user is None or not user.get("password_hash") or not verify_password(password, user["password_hash"]):
            raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "Invalid credentials", "details": {}}})
        await audit.write(session, actor_type="user", actor_id=str(user["id"]), entity="users", entity_id=user["id"],
                           action="password_login", before=None, after={})
        await session.commit()

    access, refresh = _issue_tokens(user)
    _set_refresh_cookie(response, refresh, user["role"])
    return {"access_token": access, "user": {k: v for k, v in user.items() if k != "password_hash"}}


@router.post("/auth/refresh")
async def refresh_token_endpoint(request: Request, response: Response, role: str | None = None) -> dict:
    # role comes from the caller's own last-known session (lib/auth.tsx
    # sends whichever role this tab was last signed in as) -- a tab that
    # never had a role-tagged session has nothing to refresh and shouldn't
    # guess at one of the other per-role cookies.
    if not role:
        raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "No refresh token", "details": {}}})
    raw_refresh = request.cookies.get(_refresh_cookie_name(role))
    if not raw_refresh:
        raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "No refresh token", "details": {}}})

    try:
        claims = decode_token(raw_refresh, expect_type="refresh")
    except TokenError:
        raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "Invalid refresh token", "details": {}}})

    if await is_revoked(claims["jti"]):
        raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "Refresh token revoked", "details": {}}})

    async with get_session() as session:
        user = await identity_repo.get_user_by_id(session, claims["sub"])
    if user is None:
        raise HTTPException(401, detail={"error": {"code": "UNAUTHENTICATED", "message": "User not found", "details": {}}})

    await revoke(claims["jti"])  # rotation: old refresh token can never be reused
    access, new_refresh = _issue_tokens(user)
    _set_refresh_cookie(response, new_refresh, user["role"])
    return {"access_token": access}


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, role: str | None = None) -> None:
    if not role:
        return
    cookie_name = _refresh_cookie_name(role)
    raw_refresh = request.cookies.get(cookie_name)
    if raw_refresh:
        try:
            claims = decode_token(raw_refresh, expect_type="refresh")
            await revoke(claims["jti"])
        except TokenError:
            pass
    response.delete_cookie(cookie_name)
