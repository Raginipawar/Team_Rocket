from fastapi import APIRouter, HTTPException

from .model import append_feedback, get_job, start_retrain_job
from .schemas import FeedbackAck, RetrainJob, TriageFeedback

router = APIRouter()


@router.post("/feedback/triage", response_model=FeedbackAck)
async def feedback_triage(req: TriageFeedback) -> dict:
    append_feedback(req.model_dump())
    return {"accepted": True}


@router.post("/retrain/triage", response_model=RetrainJob, status_code=202)
async def retrain_triage() -> dict:
    job_id = start_retrain_job()
    return get_job(job_id)


@router.get("/jobs/{job_id}", response_model=RetrainJob)
async def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@router.get("/models")
async def list_models() -> list[dict]:
    return [{"name": "triage", "version": "v0-mock", "active": True,
             "macro_f1": None, "critical_recall": None}]
