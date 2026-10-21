from pydantic import BaseModel


class PhotoTriageRequest(BaseModel):
    image_b64: str  # raw image bytes, base64-encoded, no data: URI prefix


class VisionLLMRead(BaseModel):
    label: str = "unclear"  # one of PHOTO_CLASSES, or "unclear" if the model couldn't tell
    severity: str = "unknown"  # mild | moderate | severe | unknown -- a rough visual read, not a clinical measurement
    description: str = ""
    confidence: float = 0.0  # the model's own self-reported confidence, not independently calibrated


class FinetunedClassifierRead(BaseModel):
    label: str = "unclear"
    confidence: float = 0.0  # real softmax probability of the top class


class PhotoTriageResult(BaseModel):
    vision_llm: VisionLLMRead = VisionLLMRead()
    finetuned_classifier: FinetunedClassifierRead = FinetunedClassifierRead()
    # True only when both reads agree on the same label -- two independent
    # models landing on the same answer is a real signal; either one alone
    # presented as "confident" would overstate what we actually know.
    agreement: bool = False
    needs_review: bool = True
    model_version: str = ""
    latency_ms: float = 0.0
