"""Learning loop (technical.md §9.19): feedback rows append to
services/ml/data/feedback/. Retrain merges synthetic + feedback (feedback x3
weight), evaluates on the fixed human holdout (data/holdout/triage.jsonl,
never used in training), and promotes the new checkpoint only if macro-F1 AND
critical-recall are >= the current model's. MLflow tracks versions; this module
is the not-yet-implemented in-process job runner behind /retrain and /jobs/{id}."""

import json
import uuid
from pathlib import Path

FEEDBACK_DIR = Path("services/ml/data/feedback")
_JOBS: dict[str, dict] = {}


def append_feedback(row: dict) -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    path = FEEDBACK_DIR / "triage.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def start_retrain_job() -> str:
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "detail": "retrain pipeline not implemented yet -- see training/triage/",
    }
    return job_id


def get_job(job_id: str) -> dict | None:
    return _JOBS.get(job_id)
