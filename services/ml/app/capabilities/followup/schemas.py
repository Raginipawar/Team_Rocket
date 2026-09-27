from pydantic import BaseModel


class AnsweredQuestion(BaseModel):
    question_id: str
    answer: str


class FollowupNextRequest(BaseModel):
    facility: str
    acuity: str
    extracted: dict = {}
    answers: list[AnsweredQuestion] = []
    language: str = "en"


class QuestionOut(BaseModel):
    id: str
    text: str
    answer_type: str  # yes_no | number | choice | free
    choices: list[str] | None = None
    audio_url: str | None = None


class FollowupNextResponse(BaseModel):
    question: QuestionOut | None = None
    done: bool = False
    model_version: str = ""
    latency_ms: float = 0.0


class FollowupParseRequest(BaseModel):
    question_id: str
    raw_answer: str
    language: str = "en"


class FollowupParseResponse(BaseModel):
    parsed: str | int | bool | None
    model_version: str = ""
    latency_ms: float = 0.0
