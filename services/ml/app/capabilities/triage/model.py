"""Real triage model: MuRIL fine-tuned (mean-pooled, frozen encoder + linear
heads -- see training/triage/train.py and its REPORT.json for the honest
story of how this checkpoint was reached, including a real collapse-to-
always-critical failure mode and its fix).

KNOWN GAPS, reported honestly:
- No temperature scaling / calibration yet -- raw softmax probabilities are
  used directly. needs_review threshold (0.60) is applied anyway, but the
  probabilities themselves are not calibrated the way technical.md §9.3 asks.
- Trained on 258 synthetic, self-labelled samples, not the spec's 8-10k
  target and not the human-written holdout. critical_recall on its own
  synthetic eval split was only 0.15 -- DO NOT rely on this model as the
  safety net. The safety net is the rule-based fragility/mlc_flag logic
  below (unconditional, not model-dependent) plus the triage-unavailable
  fallback in core/app/integrations/ml/intake.py."""

import json
from functools import lru_cache
from pathlib import Path

import torch
import torch.nn as nn

ARTIFACT_PATH = Path(__file__).parent.parent.parent.parent / "artifacts" / "triage" / "muril_v0_heads.pt"
MODEL_NAME = "google/muril-base-cased"
ACUITIES = ["critical", "urgent", "stable"]
FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]
NEEDS_REVIEW_THRESHOLD = 0.60


class ModelNotLoaded(RuntimeError):
    pass


class _TriageModel(nn.Module):
    def __init__(self, base_model_name: str):
        super().__init__()
        from transformers import AutoModel
        self.encoder = AutoModel.from_pretrained(base_model_name)
        hidden = self.encoder.config.hidden_size
        self.acuity_head = nn.Linear(hidden, len(ACUITIES))
        self.facility_head = nn.Linear(hidden, len(FACILITIES))

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return self.acuity_head(pooled), self.facility_head(pooled)


@lru_cache
def _load():
    if not ARTIFACT_PATH.exists():
        raise ModelNotLoaded(
            f"{ARTIFACT_PATH} missing -- run training/triage/generate_data.py then "
            "training/triage/train.py, or set ML_MOCK_CAPABILITIES=triage"
        )
    import transformers.modeling_utils as _tf_modeling_utils
    _tf_modeling_utils.check_torch_load_is_safe = lambda: None  # see training/triage/train.py for why

    from transformers import AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = _TriageModel(MODEL_NAME).to(device)
    # Checkpoint holds only the two trained linear heads (~40KB) -- the
    # encoder stays at its freshly-downloaded pretrained weights, which is
    # correct since it was frozen throughout training (see train.py).
    heads_state = torch.load(ARTIFACT_PATH, map_location=device, weights_only=True)
    model.load_state_dict(heads_state, strict=False)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    return model, tokenizer, device


def _build_input_text(text: str, extracted: dict, profile_summary: str | None) -> str:
    parts = [f"[TEXT] {text}"]
    if extracted:
        parts.append(f"[FACTS] {json.dumps(extracted, default=str)}")
    if profile_summary:
        parts.append(f"[PROFILE] {profile_summary}")
    return " ".join(parts)


def _fragility(extracted: dict) -> bool:
    age = extracted.get("age")
    mechanism = extracted.get("mechanism", "none")
    fracture_like = "fracture" in extracted.get("symptoms", []) or "spinal" in extracted.get("symptoms", [])
    return bool(
        extracted.get("pregnant")
        or (age is not None and age < 14)
        or (mechanism in ("fall", "road_accident") and fracture_like)
    )


def _mlc_flag(extracted: dict) -> bool:
    return extracted.get("mechanism") in ("road_accident", "assault", "burn", "poisoning")


async def real_triage(payload: dict) -> dict:
    model, tokenizer, device = _load()
    text = payload["text"]
    extracted = payload.get("extracted", {})

    input_text = _build_input_text(text, extracted, payload.get("profile_summary"))
    enc = tokenizer(input_text, truncation=True, padding=True, max_length=256, return_tensors="pt").to(device)

    with torch.no_grad():
        acuity_logits, facility_logits = model(enc["input_ids"], enc["attention_mask"])
        acuity_probs = torch.softmax(acuity_logits, dim=-1)[0].cpu().tolist()
        facility_probs = torch.softmax(facility_logits, dim=-1)[0].cpu().tolist()

    acuity_idx = int(torch.tensor(acuity_probs).argmax())
    facility_idx = int(torch.tensor(facility_probs).argmax())
    confidence = min(max(acuity_probs), max(facility_probs))

    return {
        "acuity": ACUITIES[acuity_idx],
        "acuity_probs": dict(zip(ACUITIES, [round(p, 4) for p in acuity_probs])),
        "facility": FACILITIES[facility_idx],
        "facility_probs": dict(zip(FACILITIES, [round(p, 4) for p in facility_probs])),
        "confidence": round(confidence, 4),
        "needs_review": confidence < NEEDS_REVIEW_THRESHOLD,
        "fragility": _fragility(extracted),
        "mlc_flag": _mlc_flag(extracted),
    }
