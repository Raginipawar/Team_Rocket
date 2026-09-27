import os
from functools import lru_cache


class Settings:
    ml_mode: str = os.getenv("ML_MODE", "mock")  # "real" | "mock"
    ml_mock_capabilities: set[str] = set(
        filter(None, os.getenv("ML_MOCK_CAPABILITIES", "").split(","))
    )
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    osrm_url: str = os.getenv("OSRM_URL", "http://localhost:5000")
    mapbox_token: str = os.getenv("MAPBOX_TOKEN", "")
    geo_mode: str = os.getenv("GEO_MODE", "fixtures")  # "live" | "fixtures"
    artifacts_dir: str = os.getenv("ML_ARTIFACTS_DIR", "services/ml/app/artifacts")

    def capability_mode(self, name: str) -> str:
        """Per-capability override: ML_MOCK_CAPABILITIES=stt,triage forces those to mock
        even when ML_MODE=real, so a not-yet-trained model doesn't block the rest."""
        if name in self.ml_mock_capabilities:
            return "mock"
        return self.ml_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
