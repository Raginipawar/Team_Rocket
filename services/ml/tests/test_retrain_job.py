"""Learning loop (technical.md §9.19) -- previously start_retrain_job()
always returned status="queued" with detail="not implemented yet" and the
retrain/promote/reject pipeline didn't exist at all. These tests exercise
the real promote and reject branches with controlled (mocked) metrics, so
they're fast and deterministic rather than depending on real training
actually improving a tiny sample -- the real end-to-end mechanics (data
merge, fine-tuning, artifact save/restore) were separately verified by hand
against the real MuRIL model and a real checkpoint file."""

import shutil
from unittest.mock import patch

import pytest

import app.capabilities.feedback.retrain_job as rj


@pytest.fixture(autouse=True)
def _tiny_and_isolated(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(rj, "EPOCHS", 1)
    monkeypatch.setattr(rj, "SYNTHETIC_SAMPLE_CAP", 20)
    # Never touch the real serving artifact, or depend on whatever real
    # feedback has accumulated on disk from actual API use, in a test run.
    fake_full = tmp_path / "muril_v0_full.pt"
    fake_candidate = tmp_path / "muril_v0_candidate.pt"
    monkeypatch.setattr(rj, "FULL_ARTIFACT_PATH", fake_full)
    monkeypatch.setattr(rj, "CANDIDATE_ARTIFACT_PATH", fake_candidate)

    fake_feedback = tmp_path / "feedback_triage.jsonl"
    fake_feedback.write_text(
        json.dumps({"text": "test feedback row", "confirmed_acuity": "critical",
                    "confirmed_facility": "cardiac", "language": "en"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rj, "FEEDBACK_PATH", fake_feedback)
    yield


def _fake_evaluate_sequence(*result_dicts):
    calls = {"n": 0}

    def _fake(model, loader, device):
        result = result_dicts[min(calls["n"], len(result_dicts) - 1)]
        calls["n"] += 1
        return result

    return _fake


def test_candidate_worse_is_rejected_and_serving_artifact_untouched():
    jobs = {"job1": {"job_id": "job1", "status": "queued", "progress": 0.0, "detail": ""}}
    tm = rj._load_train_module()
    fake_eval = _fake_evaluate_sequence(
        {"acuity_macro_f1": 0.3, "facility_macro_f1": 0.2, "critical_recall": 0.3, "macro_f1_mean": 0.25},
        {"acuity_macro_f1": 0.1, "facility_macro_f1": 0.1, "critical_recall": 0.1, "macro_f1_mean": 0.10},
    )
    with patch.object(tm, "evaluate", fake_eval), patch.object(rj, "_load_train_module", return_value=tm):
        rj._run_retrain_sync("job1", jobs)

    assert jobs["job1"]["status"] == "rejected"
    assert jobs["job1"]["result"]["promoted"] is False
    assert not rj.FULL_ARTIFACT_PATH.exists(), "rejected candidate must never overwrite the serving artifact"
    assert rj.CANDIDATE_ARTIFACT_PATH.exists(), "rejected candidate should still be saved for inspection"


def test_candidate_better_on_both_metrics_is_promoted():
    jobs = {"job1": {"job_id": "job1", "status": "queued", "progress": 0.0, "detail": ""}}
    tm = rj._load_train_module()
    fake_eval = _fake_evaluate_sequence(
        {"acuity_macro_f1": 0.3, "facility_macro_f1": 0.2, "critical_recall": 0.3, "macro_f1_mean": 0.25},
        {"acuity_macro_f1": 0.5, "facility_macro_f1": 0.4, "critical_recall": 0.5, "macro_f1_mean": 0.45},
    )
    with patch.object(tm, "evaluate", fake_eval), patch.object(rj, "_load_train_module", return_value=tm):
        rj._run_retrain_sync("job1", jobs)

    assert jobs["job1"]["status"] == "done"
    assert jobs["job1"]["result"]["promoted"] is True
    assert rj.FULL_ARTIFACT_PATH.exists(), "a genuinely better candidate must be promoted to the serving artifact"


def test_candidate_better_on_one_metric_but_worse_on_other_is_rejected():
    """Both metrics must hold, not just one -- a recall gain can't excuse a
    macro-F1 regression (or vice versa)."""
    jobs = {"job1": {"job_id": "job1", "status": "queued", "progress": 0.0, "detail": ""}}
    tm = rj._load_train_module()
    fake_eval = _fake_evaluate_sequence(
        {"acuity_macro_f1": 0.3, "facility_macro_f1": 0.2, "critical_recall": 0.3, "macro_f1_mean": 0.25},
        {"acuity_macro_f1": 0.1, "facility_macro_f1": 0.1, "critical_recall": 0.9, "macro_f1_mean": 0.10},
    )
    with patch.object(tm, "evaluate", fake_eval), patch.object(rj, "_load_train_module", return_value=tm):
        rj._run_retrain_sync("job1", jobs)

    assert jobs["job1"]["status"] == "rejected"
    assert jobs["job1"]["result"]["candidate_metrics"]["critical_recall"] == 0.9
    assert not rj.FULL_ARTIFACT_PATH.exists()


def test_no_feedback_submitted_rejects_without_training():
    jobs = {"job1": {"job_id": "job1", "status": "queued", "progress": 0.0, "detail": ""}}
    with patch.object(rj, "FEEDBACK_PATH", rj.FEEDBACK_PATH.parent / "does_not_exist.jsonl"):
        rj._run_retrain_sync("job1", jobs)

    assert jobs["job1"]["status"] == "rejected"
    assert "no feedback" in jobs["job1"]["detail"]
