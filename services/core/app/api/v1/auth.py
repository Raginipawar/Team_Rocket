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

REFRESH_COOKIE = "refresh_token"


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


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_security_settings()
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, httponly=True, secure=True, samesite="strict",
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
        user = await identity_repo.get_or_create_patient_user(session, phone)
        await audit.write(session, actor_type="user", actor_id=phone, entity="users", entity_id=user["id"],
                           action="otp_login", before=None, after={"phone": phone})
        await session.commit()

    access, refresh = _issue_tokens(user)
    _set_refresh_cookie(response, refresh)
    return {"access_token": access, "user": user}


@router.post("/auth/login")
async def login(body: dict, response: Response) -> dict:
    identifier = body.get("username_or_phone")
    password = body.get("password")
    if not identifier or not password:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "credentials required", "details": {}}})

    allowed = await hit(f"login:{identifier}", limit=5, window_sec=600)
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
    _set_refresh_cookie(response, refresh)
    return {"access_token": access, "user": {k: v for k, v in user.items() if k != "password_hash"}}


@router.post("/auth/refresh")
async def refresh_token_endpoint(request: Request, response: Response) -> dict:
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
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
    _set_refresh_cookie(response, new_refresh)
    return {"access_token": access}


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        try:
            claims = decode_token(raw_refresh, expect_type="refresh")
            await revoke(claims["jti"])
        except TokenError:
            pass
    response.delete_cookie(REFRESH_COOKIE)
