"""Runs the 100-pair eval set through the real duplicate-check model
end-to-end (embedding similarity + spatial/temporal gate), reports
precision/recall/F1 (technical.md §9.5)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # services/ml

from app.capabilities.duplicate.model import real_duplicate


async def main() -> None:
    pairs = json.loads(Path("services/ml/data/duplicate/eval_pairs.json").read_text(encoding="utf-8"))

    tp = fp = tn = fn = 0
    for i, pair in enumerate(pairs):
        payload = {
            "emergency": {"text": pair["text_a"], "location": pair["loc_a"], "time": "0",
                          "extracted": {"patient_count": 1}},
            "candidates": [{
                "emergency_id": f"cand-{i}", "text": pair["text_b"], "location": pair["loc_b"],
                "time": str(pair["time_gap_sec"]), "extracted": {"patient_count": 1},
            }],
        }
        result = await real_duplicate(payload)
        predicted = 1 if result["same_incident"] else 0
        actual = pair["label"]

        if predicted == 1 and actual == 1:
            tp += 1
        elif predicted == 1 and actual == 0:
            fp += 1
        elif predicted == 0 and actual == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(pairs)

    report = {
        "n_pairs": len(pairs), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4), "accuracy": round(accuracy, 4),
    }
    Path("services/ml/training/duplicate/REPORT.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
