"""Real retrain job (technical.md Section9.19). Previously start_retrain_job()
only ever returned status="queued" with detail="not implemented yet" -- the
feedback/retrain/promotion loop didn't exist. This module: merges feedback
(weighted 3x, per spec) into the synthetic training set, fine-tunes a
candidate checkpoint starting from the currently-serving weights (not from
random init -- this is "learn a bit more", not "retrain from scratch" on
every submission), evaluates both the candidate AND the currently-serving
model fresh against the same holdout, and only promotes the candidate if it
is >= the current model on BOTH macro-F1 and critical-recall. Runs in a
thread (torch training is CPU/GPU-bound, blocking) so it never blocks the
ML service's event loop."""

import asyncio
import importlib.util
import json
import logging
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader

logger = logging.getLogger("feedback_retrain")

ML_DIR = Path(__file__).resolve().parents[3]  # services/ml
SYNTHETIC_PATH = ML_DIR / "data" / "triage" / "synthetic.jsonl"
FEEDBACK_PATH = ML_DIR / "data" / "feedback" / "triage.jsonl"
HOLDOUT_PATH = ML_DIR / "data" / "holdout" / "triage.jsonl"
FULL_ARTIFACT_PATH = ML_DIR / "artifacts" / "triage" / "muril_v0_full.pt"
HEADS_ARTIFACT_PATH = ML_DIR / "artifacts" / "triage" / "muril_v0_heads.pt"
CANDIDATE_ARTIFACT_PATH = ML_DIR / "artifacts" / "triage" / "muril_v0_candidate.pt"

FEEDBACK_WEIGHT = 3  # technical.md: feedback rows weighted 3x relative to synthetic
EPOCHS = 8  # fewer than train.py's 15 -- this fine-tunes further from an
            # already-trained checkpoint, not training from random init
BATCH_SIZE = 16
SYNTHETIC_SAMPLE_CAP = 1500  # deliberate choice, documented honestly: re-running all
            # 8,478 synthetic samples through 8 epochs on every single retrain
            # trigger would make this far too slow to demo live (this is meant to be
            # triggerable during a demo and finish in a reasonable time, not a
            # from-scratch retrain). A random subsample keeps the "don't forget the
            # original distribution while learning from new feedback" property
            # without the full cost. A periodic/offline full retrain (all synthetic
            # data, no cap) is a reasonable future improvement, not done here.


def _load_train_module():
    """Imports training/triage/train.py by file path (it isn't a package)
    to reuse TriageModel/TriageDataset/evaluate/etc. rather than duplicating
    them -- keeps the retrain job's model definition identical to the one
    that produced the currently-serving checkpoint."""
    path = ML_DIR / "training" / "triage" / "train.py"
    spec = importlib.util.spec_from_file_location("triage_train", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _build_dataset(tm, samples: list[dict], tokenizer):
    texts = [tm.build_input_text(s) for s in samples]
    acuity = [tm.ACUITIES.index(s["acuity"]) for s in samples]
    facility = [tm.FACILITIES.index(s["facility"]) for s in samples]
    return tm.TriageDataset(texts, acuity, facility, tokenizer)


def _load_model_from(tm, device, path: Path):
    model = tm.TriageModel(tm.MODEL_NAME).to(device)
    if path.exists():
        state = torch.load(path, map_location=device, weights_only=True)
        model.load_state_dict(state, strict=(path == FULL_ARTIFACT_PATH))
    return model


def _run_retrain_sync(job_id: str, jobs: dict) -> None:
    def set_job(**kwargs):
        jobs[job_id].update(kwargs)

    try:
        set_job(status="running", progress=0.05, detail="loading data")
        tm = _load_train_module()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        synthetic = _load_jsonl(SYNTHETIC_PATH)
        feedback = _load_jsonl(FEEDBACK_PATH)
        holdout = _load_jsonl(HOLDOUT_PATH)
        if not synthetic:
            set_job(status="failed", progress=0.0, detail=f"no synthetic data at {SYNTHETIC_PATH}")
            return
        if not feedback:
            set_job(status="rejected", progress=1.0,
                     detail="no feedback submitted yet -- nothing new to learn from")
            return
        if not holdout:
            set_job(status="failed", progress=0.0, detail=f"no holdout data at {HOLDOUT_PATH}")
            return

        # Feedback rows carry confirmed_acuity/confirmed_facility (the
        # paramedic's correction), not acuity/facility -- reshape to the
        # training sample shape train.py's TriageDataset expects.
        feedback_samples = [
            {"text": r["text"], "acuity": r["confirmed_acuity"], "facility": r["confirmed_facility"],
             "language": r.get("language", "en")}
            for r in feedback
        ]
        if len(synthetic) > SYNTHETIC_SAMPLE_CAP:
            rng = np.random.default_rng(42)
            synthetic = list(rng.choice(synthetic, size=SYNTHETIC_SAMPLE_CAP, replace=False))
        training_samples = synthetic + feedback_samples * FEEDBACK_WEIGHT
        logger.info("retrain %s: %d synthetic + %d feedback x%d = %d training samples, %d holdout",
                    job_id, len(synthetic), len(feedback_samples), FEEDBACK_WEIGHT, len(training_samples), len(holdout))

        set_job(progress=0.15, detail="building datasets")
        tokenizer = tm.AutoTokenizer.from_pretrained(tm.MODEL_NAME)
        acuity_labels = [tm.ACUITIES.index(s["acuity"]) for s in training_samples]
        train_idx, val_idx = train_test_split(range(len(training_samples)), test_size=0.15,
                                               random_state=42, stratify=acuity_labels)
        train_ds = _build_dataset(tm, [training_samples[i] for i in train_idx], tokenizer)
        val_ds = _build_dataset(tm, [training_samples[i] for i in val_idx], tokenizer)
        train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)
        holdout_ds = _build_dataset(tm, holdout, tokenizer)
        holdout_loader = DataLoader(holdout_ds, batch_size=BATCH_SIZE)

        set_job(progress=0.2, detail="evaluating currently-serving model on holdout")
        current_path = FULL_ARTIFACT_PATH if FULL_ARTIFACT_PATH.exists() else HEADS_ARTIFACT_PATH
        current_model = _load_model_from(tm, device, current_path)
        current_metrics = tm.evaluate(current_model, holdout_loader, device)
        logger.info("retrain %s: current model holdout metrics %s", job_id, current_metrics)

        set_job(progress=0.3, detail="fine-tuning candidate")
        candidate = _load_model_from(tm, device, current_path)  # start from current weights, not random init
        acuity_weights = tm.compute_class_weights([acuity_labels[i] for i in train_idx], len(tm.ACUITIES),
                                                     critical_idx=tm.ACUITIES.index("critical"),
                                                     critical_multiplier=tm.CRITICAL_WEIGHT_MULTIPLIER).to(device)
        facility_labels_all = [tm.FACILITIES.index(s["facility"]) for s in training_samples]
        facility_weights = tm.compute_class_weights([facility_labels_all[i] for i in train_idx],
                                                       len(tm.FACILITIES)).to(device)
        acuity_loss_fn = torch.nn.CrossEntropyLoss(weight=acuity_weights)
        facility_loss_fn = torch.nn.CrossEntropyLoss(weight=facility_weights)
        optimizer = torch.optim.AdamW([
            {"params": candidate.encoder.parameters(), "lr": tm.LR},
            {"params": list(candidate.acuity_head.parameters()) + list(candidate.facility_head.parameters()),
             "lr": tm.HEAD_LR},
        ])

        for epoch in range(EPOCHS):
            candidate.train()
            for batch in train_loader:
                input_ids = batch["input_ids"].to(device)
                attn = batch["attention_mask"].to(device)
                acuity_label = batch["acuity_label"].to(device)
                facility_label = batch["facility_label"].to(device)
                acuity_logits, facility_logits = candidate(input_ids, attn)
                loss = acuity_loss_fn(acuity_logits, acuity_label) + facility_loss_fn(facility_logits, facility_label)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            set_job(progress=0.3 + 0.5 * (epoch + 1) / EPOCHS, detail=f"fine-tuning epoch {epoch+1}/{EPOCHS}")

        set_job(progress=0.85, detail="evaluating candidate on holdout")
        candidate_metrics = tm.evaluate(candidate, holdout_loader, device)
        logger.info("retrain %s: candidate holdout metrics %s", job_id, candidate_metrics)

        cur_f1 = current_metrics["macro_f1_mean"]
        cand_f1 = candidate_metrics["macro_f1_mean"]
        cur_recall = current_metrics["critical_recall"] or 0.0
        cand_recall = candidate_metrics["critical_recall"] or 0.0
        promote = cand_f1 >= cur_f1 and cand_recall >= cur_recall

        result = {
            "current_metrics": current_metrics, "candidate_metrics": candidate_metrics,
            "n_feedback": len(feedback_samples), "n_synthetic": len(synthetic), "promoted": promote,
        }

        try:
            import mlflow
            mlflow.set_experiment("goldenhour-triage-retrain")
            with mlflow.start_run():
                mlflow.log_params({"job_id": job_id, "n_synthetic": len(synthetic),
                                    "n_feedback": len(feedback_samples), "epochs": EPOCHS})
                mlflow.log_metrics({f"current_{k}": v for k, v in current_metrics.items() if v is not None})
                mlflow.log_metrics({f"candidate_{k}": v for k, v in candidate_metrics.items() if v is not None})
                mlflow.log_metric("promoted", int(promote))
        except Exception:
            logger.exception("retrain %s: MLflow logging failed -- continuing, this must not block promotion", job_id)

        if promote:
            torch.save(candidate.state_dict(), FULL_ARTIFACT_PATH)
            # Force the serving model (app/capabilities/triage/model.py) to
            # reload on its next call instead of keeping the old weights
            # cached for the rest of the process's lifetime.
            try:
                from app.capabilities.triage.model import _load as triage_load
                triage_load.cache_clear()
            except Exception:
                logger.exception("retrain %s: promoted but could not clear the serving model's cache", job_id)
            set_job(status="done", progress=1.0, detail="promoted: candidate >= current on both metrics", result=result)
        else:
            torch.save(candidate.state_dict(), CANDIDATE_ARTIFACT_PATH)  # kept for inspection, not served
            set_job(status="rejected", progress=1.0,
                     detail="rejected: candidate did not beat current on macro_f1 and critical_recall both",
                     result=result)

    except Exception as exc:
        logger.exception("retrain %s failed", job_id)
        jobs[job_id].update(status="failed", progress=jobs[job_id].get("progress", 0.0), detail=f"error: {exc}")


async def run_retrain_job(job_id: str, jobs: dict) -> None:
    await asyncio.to_thread(_run_retrain_sync, job_id, jobs)
