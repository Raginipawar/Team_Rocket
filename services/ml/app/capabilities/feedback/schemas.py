from pydantic import BaseModel


class TriageFeedback(BaseModel):
    emergency_id: str
    text: str
    extracted: dict = {}
    predicted_acuity: str
    predicted_facility: str
    confirmed_acuity: str
    confirmed_facility: str


class FeedbackAck(BaseModel):
    accepted: bool = True


class RetrainJob(BaseModel):
    job_id: str
    status: str  # queued | running | done | failed | rejected
    progress: float = 0.0
    detail: str | None = None


class ModelInfo(BaseModel):
    name: str
    version: str
    active: bool
    macro_f1: float | None = None
    critical_recall: float | None = None
