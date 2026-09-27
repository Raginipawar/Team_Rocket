"""Field-level accuracy on the synthetic eval set (technical.md §9.2).
Symptoms are scored by set-overlap F1 (order-independent, partial credit);
scalar fields (sex, mechanism, breathing, bleeding, conscious, pregnant,
for_whom) are scored by exact match, skipping fields where ground truth is
None (not asserted either way by the template)."""

import asyncio
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.capabilities.extract.model import real_extract

SCALAR_FIELDS = ["sex", "mechanism", "breathing", "bleeding", "conscious", "pregnant", "for_whom"]


def symptom_f1(true_set: set, pred_set: set) -> float:
    if not true_set and not pred_set:
        return 1.0
    if not true_set or not pred_set:
        return 0.0
    tp = len(true_set & pred_set)
    precision = tp / len(pred_set)
    recall = tp / len(true_set)
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


async def main() -> None:
    samples = json.loads(Path("services/ml/data/extraction/eval_set.json").read_text(encoding="utf-8"))

    field_correct = {f: 0 for f in SCALAR_FIELDS}
    field_total = {f: 0 for f in SCALAR_FIELDS}
    symptom_f1_scores = []
    errors = []

    for i, sample in enumerate(samples):
        try:
            pred = await real_extract({"text": sample["text"], "language": sample["language"]})
        except Exception as exc:
            errors.append({"text": sample["text"], "error": str(exc)})
            continue

        true = sample["true"]
        for field in SCALAR_FIELDS:
            if field not in true or true[field] is None:
                continue
            field_total[field] += 1
            if pred.get(field) == true[field]:
                field_correct[field] += 1

        true_symptoms = set(true.get("symptoms", []))
        pred_symptoms = set(pred.get("symptoms", []))
        symptom_f1_scores.append(symptom_f1(true_symptoms, pred_symptoms))

        if i < 5:
            print(f"[{i}] {sample['language']} {sample['text'][:60]!r} -> {pred}")

    accuracy_per_field = {
        f: round(field_correct[f] / field_total[f], 4) if field_total[f] else None
        for f in SCALAR_FIELDS
    }
    mean_symptom_f1 = sum(symptom_f1_scores) / len(symptom_f1_scores) if symptom_f1_scores else 0.0

    report = {
        "n_samples": len(samples), "n_errors": len(errors),
        "accuracy_per_scalar_field": accuracy_per_field,
        "mean_symptom_f1": round(mean_symptom_f1, 4),
        "note": "Synthetic eval set (training/extraction/generate_eval_set.py), ground truth is "
                "the template's known fields, not human-labelled -- legitimate for this capability "
                "per the note in generate_eval_set.py, but distinct from the triage holdout.",
    }
    Path("services/ml/training/extraction/REPORT.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
