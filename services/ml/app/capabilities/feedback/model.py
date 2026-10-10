"""Learning loop (technical.md §9.19): feedback rows append to
services/ml/data/feedback/. Retrain merges synthetic + feedback (feedback x3
weight), evaluates on the holdout (data/holdout/triage.jsonl, never used in
training), and promotes the new checkpoint only if macro-F1 AND
critical-recall are >= the current model's -- real now (retrain_job.py);
this used to always return status="queued" with detail="not implemented
yet" and never actually do anything."""

import asyncio
import json
import uuid
from pathlib import Path

from .retrain_job import run_retrain_job

FEEDBACK_DIR = Path(__file__).resolve().parents[3] / "data" / "feedback"
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
        "detail": "queued",
    }
    asyncio.create_task(run_retrain_job(job_id, _JOBS))
    return job_id


def get_job(job_id: str) -> dict | None:
    return _JOBS.get(job_id)
