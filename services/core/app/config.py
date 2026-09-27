from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/db"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET: str = "secret"
    JWT_KID: str = "kid1"
    
    ML_BASE_URL: str = "http://localhost:8001"
    ML_MODE: str = "real"
    ML_MOCK_CAPABILITIES: str = ""
    
    OSRM_URL: str = "http://localhost:5000"
    MAPBOX_TOKEN: str = ""
    GEO_MODE: str = "osrm"
    
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3"
    
    SMS_MODE: str = "mock"
    SMS_PROVIDER: str = "twilio"
    SMS_API_KEY: str = ""
    SMS_WEBHOOK_SECRET: str = ""
    SMS_GATEWAY_NUMBER: str = ""
    
    TELEGRAM_MODE: str = "mock"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_GROUP_CHAT_ID: str = ""
    
    FCM_PROJECT_ID: str = ""
    FCM_SERVICE_ACCOUNT_JSON: str = ""
    
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    SIM_ENABLED: bool = False
    SIM_SPEED: float = 1.0
    
    DISPATCH_RADII_KM: list[int] = [5, 10, 20]
    OFFERS_PER_ROUND: int = 4
    OFFER_EXPIRY_SEC: int = 20
    DISPATCH_ROUND_INTERVAL_SEC: int = 30
    NO_AMBULANCE_ESCALATE_AFTER_ROUND: int = 3
    HOSPITAL_TIMEOUT_CRITICAL_SEC: int = 45
    HOSPITAL_TIMEOUT_OTHER_SEC: int = 60
    HOLD_PENDING_TTL_SEC: int = 70
    HOLD_CONFIRMED_MIN_SEC: int = 600
    HEARTBEAT_INTERVAL_SEC: int = 5
    SIGNAL_WEAK_SEC: int = 30
    SIGNAL_LOST_SEC: int = 120
    OFFLINE_HOLD_GRACE_SEC_EXTRA: int = 900
    ESCALATION_REPEAT_SEC: int = 60
    ESCALATION_DEFAULT_SEC: int = 120
    FRESH_MAX_MIN: int = 10
    AGING_MAX_MIN: int = 30
    DUPLICATE_RADIUS_M: int = 500
    DUPLICATE_WINDOW_MIN: int = 15
    DUPLICATE_SIM: float = 0.80
    MCI_PATIENT_THRESHOLD: int = 5
    TRIAGE_REVIEW_CONFIDENCE: float = 0.60
    PRANK_VERIFY_WAIT_SEC: int = 30
    GEOFENCE_SCENE_M: int = 75
    GEOFENCE_HOSPITAL_M: int = 150
    IDLE_ALERT_SEC: int = 90
    IDLE_REASSIGN_SEC: int = 150
    OFFLOAD_DELAY_ALERT_MIN: int = 15
    DETERIORATION_DIVERT_GAIN_SEC: int = 180
    IDEMPOTENCY_TTL_H: int = 24
    OPS_LINK_TTL_MIN: int = 15
    OPS_SESSION_H: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
