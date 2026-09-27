import os
from functools import lru_cache


class SecuritySettings:
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
    jwt_kid: str = os.getenv("JWT_KID", "k1")
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7

    otp_length: int = 6
    otp_ttl_min: int = 5
    otp_max_attempts: int = 5
    otp_request_limit: int = 3
    otp_request_window_min: int = 10

    idempotency_ttl_h: int = int(os.getenv("IDEMPOTENCY_TTL_H", "24"))

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@lru_cache
def get_security_settings() -> SecuritySettings:
    return SecuritySettings()
