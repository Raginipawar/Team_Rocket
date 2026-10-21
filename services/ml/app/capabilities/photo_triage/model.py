"""Real photo-triage: two independent reads of the same image (technical.md's
"never a single model deciding alone" principle, same as triage's keyword
safety net under the LLM). 1) a vision-capable Ollama model (moondream) reads
the photo directly and describes/classifies what it sees -- genuinely
understands image content, zero fine-tuning. 2) a MobileNetV2 fine-tuned on
our own labeled set (training/photo_severity/) gives a second, independently
produced classification. Neither is trusted alone: `agreement` in the
response is true only when both land on the same label, and the caller
(core's photo_triage() wrapper) treats disagreement as needs_review, same
spirit as triage's low-confidence-forces-ALS rule."""

import base64
import io
import logging
from functools import lru_cache
from pathlib import Path

import httpx
import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms

from .schemas import PhotoTriageResult

logger = logging.getLogger("photo_triage")

OLLAMA_URL = "http://localhost:11434"
VISION_MODEL = "moondream"
# First real call loads moondream into memory cold -- measured ~30s+ for
# that alone, same "CPU/first-load inference is slow" lesson already
# documented for STT/extract/triage's own timeouts (integrations/ml/intake.py
# on the core side). Generous margin here rather than repeating that
# discovery through a second silent-fallback bug.
OLLAMA_TIMEOUT_S = 60.0

# __file__-relative, not CWD-relative (training/prank/model.py's own
# ARTIFACT_PATH pattern) -- a CWD-relative string silently resolves
# differently depending on whether the service was launched from the repo
# root or from services/ml, found by this exact mismatch returning
# "unclear" with 0 confidence instead of a real read.
CLASSIFIER_PATH = Path(__file__).parent.parent.parent.parent / "artifacts" / "photo_severity" / "mobilenet_v2_finetuned.pt"

PHOTO_CLASSES = ["bleeding", "burn", "bruise_fracture", "none_minor"]
SEVERITY_WORDS = ["mild", "moderate", "severe"]

# moondream (1.7GB, CPU-friendly) is a small VLM -- tried Ollama's
# format="json" constrained decoding here first, same as extract/triage use
# with Qwen, but moondream doesn't reliably honor it (produced truncated,
# unparseable JSON on real test images -- a genuine model-capability
# difference, not a prompt bug). Asking for one bare word is something a
# small VLM follows reliably; parsed with a strict match against the known
# class list rather than trusted as free-form JSON.
#
# Tried folding severity into this SAME one-word ask (asking for two words
# instead of one) to save a round trip -- measured, not assumed: it broke
# the label's own reliability, label dropped to "unclear" on every single
# real test image that previously worked. A small VLM given a harder
# instruction got worse at the easier part of it too. Severity is now a
# genuinely separate follow-up call (_call_severity_llm below), fired only
# when the label itself came back confidently -- an extra ~1s only when
# there's something worth asking about, instead of degrading the read that
# already works.
VISION_PROMPT = (
    "Look at this photo from a medical emergency call. Reply with exactly "
    "ONE of these words and nothing else: " + ", ".join(PHOTO_CLASSES) + ". "
    "Use none_minor if there is no visible significant injury (e.g. just a "
    "person or the scene, nothing alarming)."
)
_DESCRIPTIONS = {
    "bleeding": "Visible active bleeding in the photo.",
    "burn": "Visible burn injury in the photo.",
    "bruise_fracture": "Visible bruising or suspected fracture in the photo.",
    "none_minor": "No significant visible injury in the photo.",
    "unclear": "Could not confidently classify the photo.",
}


class ModelNotLoaded(RuntimeError):
    pass


async def _call_vision_llm(image_b64: str) -> dict:
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_S) as client:
        try:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": VISION_MODEL,
                "prompt": VISION_PROMPT,
                "images": [image_b64],
                "options": {"temperature": 0},
                "stream": False,
            })
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ModelNotLoaded(f"Ollama vision model not reachable: {exc}") from exc

    raw_text = response.json().get("response", "").strip().lower()
    # Strict match: the model may still wrap the word in a sentence despite
    # the prompt asking for just the word -- find a known class as a whole
    # word in whatever it said, rather than requiring an exact-equals match.
    label = next((c for c in PHOTO_CLASSES if c in raw_text), "unclear")
    severity = "unknown"
    if label not in ("unclear", "none_minor"):
        severity = await _call_severity_llm(image_b64)
    return {
        "label": label,
        "severity": severity,
        "description": _DESCRIPTIONS[label],
        # A clean single-word match is a real (if coarse) confidence signal;
        # the model rambling or not matching any known class isn't.
        "confidence": 0.75 if label != "unclear" else 0.0,
    }


SEVERITY_PROMPT = (
    "Look at this injury photo. Reply with exactly ONE of these words and "
    "nothing else, for how severe it looks: " + ", ".join(SEVERITY_WORDS) + "."
)


async def _call_severity_llm(image_b64: str) -> str:
    """Separate call, fired only when the label call above already came
    back confident -- see the comment on VISION_PROMPT for why this isn't
    folded into that same call."""
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_S) as client:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": VISION_MODEL, "prompt": SEVERITY_PROMPT, "images": [image_b64],
                "options": {"temperature": 0}, "stream": False,
            })
            response.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException):
        return "unknown"
    raw = response.json().get("response", "").strip().lower()
    return next((s for s in SEVERITY_WORDS if s in raw), "unknown")


_TRANSFORM = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


@lru_cache
def _load_classifier():
    checkpoint = torch.load(CLASSIFIER_PATH, map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = nn.Linear(model.last_channel, len(classes))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, classes


def _run_classifier(image: Image.Image) -> dict:
    try:
        model, classes = _load_classifier()
    except FileNotFoundError:
        logger.warning("photo_severity classifier artifact missing -- run training/photo_severity/{generate_data,train}.py")
        return {"label": "unclear", "confidence": 0.0}
    with torch.no_grad():
        tensor = _TRANSFORM(image.convert("RGB")).unsqueeze(0)
        probs = torch.softmax(model(tensor), dim=1)[0]
        top_idx = int(torch.argmax(probs))
    return {"label": classes[top_idx], "confidence": round(float(probs[top_idx]), 4)}


async def real_photo_triage(payload: dict) -> dict:
    image_b64 = payload["image_b64"]
    image = Image.open(io.BytesIO(base64.b64decode(image_b64)))

    classifier_read = _run_classifier(image)
    try:
        vision_read = await _call_vision_llm(image_b64)
    except ModelNotLoaded:
        # Honest partial result, not a hard failure -- the fine-tuned
        # classifier still ran and still produces a real read even if the
        # vision LLM (a separate, heavier local dependency) is briefly down.
        vision_read = {"label": "unclear", "severity": "unknown", "description": "vision model unavailable", "confidence": 0.0}

    agreement = vision_read["label"] == classifier_read["label"] and vision_read["label"] != "unclear"
    result = PhotoTriageResult(
        vision_llm=vision_read, finetuned_classifier=classifier_read,
        agreement=agreement,
        # Disagreement (or either read being low-confidence) means a human
        # should look at the actual photo -- never silently pick one read.
        needs_review=not agreement or classifier_read["confidence"] < 0.6 or vision_read["confidence"] < 0.4,
    )
    return result.model_dump(exclude={"model_version", "latency_ms"})
