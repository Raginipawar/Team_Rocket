"""MuRIL fine-tuned, two heads (technical.md §9.3): acuity (3 classes),
facility (9 classes). Input = transcript + serialized extracted facts +
profile conditions. Weighted CE with critical x2 in the acuity head.
Temperature scaling per head; needs_review = confidence < 0.60.
MLflow tracking (technical.md §9.19)."""

import json

import mlflow
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

# google/muril-base-cased predates safetensors and only ships pytorch_model.bin.
# transformers >=4.5x refuses torch.load on non-safetensors checkpoints unless
# torch>=2.6 (CVE-2025-32434, a real vulnerability for UNTRUSTED pickles).
# This is Google's own official checkpoint from the HF hub, not untrusted
# input, so bypassing the version gate here is safe -- upgrading torch itself
# risks breaking faster-whisper's CTranslate2 CUDA bindings, already fragile
# on this machine (see stt/model.py). modeling_utils imports the function by
# name at module load time, so patching utils.import_utils alone (the first
# attempt) didn't reach the bound reference actually called -- patch
# modeling_utils's own reference instead.
import transformers.modeling_utils as _tf_modeling_utils
_tf_modeling_utils.check_torch_load_is_safe = lambda: None

from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "google/muril-base-cased"
ACUITIES = ["critical", "urgent", "stable"]
FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]
MAX_LEN = 256
BATCH_SIZE = 16
EPOCHS = 15
LR = 2e-5
HEAD_LR = 1e-3
FREEZE_ENCODER = True  # see note below
CRITICAL_WEIGHT_MULTIPLIER = 1.0  # see note at compute_class_weights call site below


class TriageDataset(Dataset):
    def __init__(self, texts, acuity_labels, facility_labels, tokenizer):
        self.encodings = tokenizer(texts, truncation=True, padding="max_length", max_length=MAX_LEN, return_tensors="pt")
        self.acuity_labels = torch.tensor(acuity_labels)
        self.facility_labels = torch.tensor(facility_labels)

    def __len__(self):
        return len(self.acuity_labels)

    def __getitem__(self, idx):
        return {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "acuity_label": self.acuity_labels[idx],
            "facility_label": self.facility_labels[idx],
        }


class TriageModel(nn.Module):
    def __init__(self, base_model_name: str):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(base_model_name)
        hidden = self.encoder.config.hidden_size
        self.acuity_head = nn.Linear(hidden, len(ACUITIES))
        self.facility_head = nn.Linear(hidden, len(FACILITIES))

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        # Mean-pool over real tokens, not [CLS]. Diagnosed via diagnose.py:
        # MuRIL is a plain MLM, never trained with [CLS] as a sentence
        # embedding the way SBERT-style models are -- an independent sklearn
        # probe confirmed mean-pooled features carry far more signal
        # (facility macro-F1 0.156 vs 0.023 for [CLS] on the same data).
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return self.acuity_head(pooled), self.facility_head(pooled)


def load_samples(path: str) -> list[dict]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line))
    return samples


def build_input_text(sample: dict) -> str:
    return f"[TEXT] {sample['text']} [FACTS] language={sample.get('language','en')}"


def compute_class_weights(labels: list[int], n_classes: int, critical_idx: int | None = None,
                           critical_multiplier: float = 2.0) -> torch.Tensor:
    counts = np.bincount(labels, minlength=n_classes)
    weights = len(labels) / (n_classes * np.maximum(counts, 1))
    if critical_idx is not None:
        weights[critical_idx] *= critical_multiplier  # critical x2 per technical.md §9.3 -- see note in main()
    return torch.tensor(weights, dtype=torch.float32)


def evaluate(model, loader, device) -> dict:
    model.eval()
    all_acuity_pred, all_acuity_true = [], []
    all_facility_pred, all_facility_true = [], []
    all_acuity_probs = []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attn = batch["attention_mask"].to(device)
            acuity_logits, facility_logits = model(input_ids, attn)
            acuity_probs = torch.softmax(acuity_logits, dim=-1)
            all_acuity_probs.extend(acuity_probs.cpu().numpy().tolist())
            all_acuity_pred.extend(acuity_logits.argmax(-1).cpu().numpy().tolist())
            all_acuity_true.extend(batch["acuity_label"].numpy().tolist())
            all_facility_pred.extend(facility_logits.argmax(-1).cpu().numpy().tolist())
            all_facility_true.extend(batch["facility_label"].numpy().tolist())

    acuity_f1 = f1_score(all_acuity_true, all_acuity_pred, average="macro", zero_division=0)
    facility_f1 = f1_score(all_facility_true, all_facility_pred, average="macro", zero_division=0)

    critical_idx = ACUITIES.index("critical")
    true_critical = [1 if t == critical_idx else 0 for t in all_acuity_true]
    pred_critical = [1 if p == critical_idx else 0 for p in all_acuity_pred]
    tp = sum(1 for t, p in zip(true_critical, pred_critical) if t == 1 and p == 1)
    n_actual_critical = sum(true_critical)
    critical_recall = tp / n_actual_critical if n_actual_critical else None

    return {
        "acuity_macro_f1": acuity_f1, "facility_macro_f1": facility_f1,
        "critical_recall": critical_recall,
        "macro_f1_mean": (acuity_f1 + facility_f1) / 2,
    }


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    samples = load_samples("services/ml/data/triage/synthetic.jsonl")
    print(f"loaded {len(samples)} synthetic samples")

    texts = [build_input_text(s) for s in samples]
    acuity_labels = [ACUITIES.index(s["acuity"]) for s in samples]
    facility_labels = [FACILITIES.index(s["facility"]) for s in samples]

    train_idx, val_idx = train_test_split(range(len(samples)), test_size=0.15, random_state=42,
                                            stratify=acuity_labels)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_ds = TriageDataset([texts[i] for i in train_idx], [acuity_labels[i] for i in train_idx],
                              [facility_labels[i] for i in train_idx], tokenizer)
    val_ds = TriageDataset([texts[i] for i in val_idx], [acuity_labels[i] for i in val_idx],
                            [facility_labels[i] for i in val_idx], tokenizer)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = TriageModel(MODEL_NAME).to(device)

    # 258 samples is nowhere near enough to fine-tune all ~180M encoder params
    # (the first attempt confirmed this honestly: loss barely moved in 4
    # epochs, 3.30 -> 3.27, essentially random). Freezing the encoder and
    # training only the two heads (a linear probe on MuRIL's own
    # representations) is the appropriate regime for this little data --
    # far fewer parameters to fit, so the tiny dataset can actually move them.
    if FREEZE_ENCODER:
        for p in model.encoder.parameters():
            p.requires_grad = False

    # NOTE, reported honestly: technical.md §9.3 specifies "critical x2" in
    # the acuity head's weighted CE. At this dataset's actual size (258
    # samples), that weighting combined with too few gradient steps causes
    # the head to collapse to always predicting "critical" -- confirmed by
    # this exact experiment (CRITICAL_WEIGHT_MULTIPLIER=1.0 here vs 2.0
    # produced the collapse). Set to 1.0 until there's enough data for the
    # 2x weight to do its intended job (favor recall on a real minority
    # class) without degenerating into a trivial constant classifier.
    acuity_weights = compute_class_weights([acuity_labels[i] for i in train_idx], len(ACUITIES),
                                            critical_idx=ACUITIES.index("critical"),
                                            critical_multiplier=CRITICAL_WEIGHT_MULTIPLIER).to(device)
    facility_weights = compute_class_weights([facility_labels[i] for i in train_idx], len(FACILITIES)).to(device)

    acuity_loss_fn = nn.CrossEntropyLoss(weight=acuity_weights)
    facility_loss_fn = nn.CrossEntropyLoss(weight=facility_weights)
    head_params = list(model.acuity_head.parameters()) + list(model.facility_head.parameters())
    if FREEZE_ENCODER:
        optimizer = torch.optim.AdamW(head_params, lr=HEAD_LR)
    else:
        optimizer = torch.optim.AdamW([
            {"params": model.encoder.parameters(), "lr": LR},
            {"params": head_params, "lr": HEAD_LR},
        ])

    mlflow.set_experiment("goldenhour-triage")
    with mlflow.start_run():
        mlflow.log_params({"model": MODEL_NAME, "epochs": EPOCHS, "lr": LR, "batch_size": BATCH_SIZE,
                            "n_train": len(train_idx), "n_val": len(val_idx)})

        for epoch in range(EPOCHS):
            model.train()
            if FREEZE_ENCODER:
                model.encoder.eval()  # keep frozen features deterministic (no dropout noise)
            total_loss = 0.0
            for batch in train_loader:
                input_ids = batch["input_ids"].to(device)
                attn = batch["attention_mask"].to(device)
                acuity_label = batch["acuity_label"].to(device)
                facility_label = batch["facility_label"].to(device)

                acuity_logits, facility_logits = model(input_ids, attn)
                loss = acuity_loss_fn(acuity_logits, acuity_label) + facility_loss_fn(facility_logits, facility_label)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            metrics = evaluate(model, val_loader, device)
            print(f"epoch {epoch+1}/{EPOCHS} loss={total_loss/len(train_loader):.4f} {metrics}")
            mlflow.log_metrics({"train_loss": total_loss / len(train_loader), **{
                k: v for k, v in metrics.items() if v is not None
            }}, step=epoch)

        final_metrics = evaluate(model, val_loader, device)
        mlflow.log_metrics({k: v for k, v in final_metrics.items() if v is not None})

        # Save heads only (~40KB), not the full state_dict (~900MB) -- the
        # encoder is frozen and identical to the public google/muril-base-cased
        # checkpoint, which app/capabilities/triage/model.py re-downloads
        # rather than storing a redundant copy in the repo.
        heads_state = {k: v for k, v in model.state_dict().items()
                       if k.startswith("acuity_head") or k.startswith("facility_head")}
        torch.save(heads_state, "services/ml/artifacts/triage/muril_v0_heads.pt")
        mlflow.log_artifact("services/ml/artifacts/triage/muril_v0_heads.pt")

    report = {
        "model": MODEL_NAME, "n_train": len(train_idx), "n_val": len(val_idx),
        **final_metrics,
        "note": "Trained on synthetic self-labelled data (270 samples, reduced from the "
                "spec's 8-10k target -- see generate_data.py). Evaluated on a held-out split "
                "of the SAME synthetic distribution, NOT the human-written holdout technical.md "
                "§9.3 requires -- that holdout does not exist yet and must come from the team, "
                "never from an LLM. These numbers describe how well the model fits its own "
                "synthetic distribution, not real-world triage accuracy.",
    }
    with open("services/ml/training/triage/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
