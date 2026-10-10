# Kaggle GPU version of train.py + eval_holdout.py, combined. Same model,
# same hyperparameters, same honest-reporting logic as the local files --
# only the compute moves to a Kaggle T4 instead of the local 6GB laptop GPU,
# per the project's own rule: local GPU for inference/Ollama, Kaggle for
# heavy training.

import json

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

import transformers.modeling_utils as _tf_modeling_utils
_tf_modeling_utils.check_torch_load_is_safe = lambda: None  # google/muril-base-cased predates safetensors

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
FREEZE_ENCODER = False  # 8,478 real samples -- enough to fine-tune the encoder, unlike the original 258-sample run
CRITICAL_WEIGHT_MULTIPLIER = 2.0  # technical.md's real spec value


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


def compute_class_weights(labels, n_classes, critical_idx=None, critical_multiplier=2.0):
    counts = np.bincount(labels, minlength=n_classes)
    weights = len(labels) / (n_classes * np.maximum(counts, 1))
    if critical_idx is not None:
        weights[critical_idx] *= critical_multiplier
    return torch.tensor(weights, dtype=torch.float32)


def evaluate(model, loader, device) -> dict:
    model.eval()
    all_acuity_pred, all_acuity_true = [], []
    all_facility_pred, all_facility_true = [], []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attn = batch["attention_mask"].to(device)
            acuity_logits, facility_logits = model(input_ids, attn)
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
        "critical_recall": critical_recall, "macro_f1_mean": (acuity_f1 + facility_f1) / 2,
    }


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device, flush=True)
    samples = load_samples("/kaggle/input/goldenhour-triage-data/synthetic.jsonl")
    print(f"loaded {len(samples)} training samples", flush=True)

    texts = [build_input_text(s) for s in samples]
    acuity_labels = [ACUITIES.index(s["acuity"]) for s in samples]
    facility_labels = [FACILITIES.index(s["facility"]) for s in samples]

    train_idx, val_idx = train_test_split(range(len(samples)), test_size=0.15, random_state=42, stratify=acuity_labels)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_ds = TriageDataset([texts[i] for i in train_idx], [acuity_labels[i] for i in train_idx],
                              [facility_labels[i] for i in train_idx], tokenizer)
    val_ds = TriageDataset([texts[i] for i in val_idx], [acuity_labels[i] for i in val_idx],
                            [facility_labels[i] for i in val_idx], tokenizer)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = TriageModel(MODEL_NAME).to(device)
    if FREEZE_ENCODER:
        for p in model.encoder.parameters():
            p.requires_grad = False

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

    for epoch in range(EPOCHS):
        model.train()
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
        print(f"epoch {epoch+1}/{EPOCHS} loss={total_loss/len(train_loader):.4f} {metrics}", flush=True)

    final_metrics = evaluate(model, val_loader, device)
    torch.save(model.state_dict(), "/kaggle/working/muril_v0_full.pt")

    report = {
        "model": MODEL_NAME, "n_train": len(train_idx), "n_val": len(val_idx),
        "freeze_encoder": FREEZE_ENCODER, "critical_weight_multiplier": CRITICAL_WEIGHT_MULTIPLIER,
        **final_metrics,
        "note": f"Trained on synthetic self-labelled data ({len(samples)} samples, in the spec's "
                "8-10k target range, after dropping 27/8505 CJK-contaminated generations found by "
                "post-hoc inspection). These metrics are a same-distribution fit check, not a "
                "real-world accuracy claim -- see holdout_report.json for the separate-distribution "
                "check, which itself is LLM-generated (not independently human-verified).",
    }
    with open("/kaggle/working/report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("TRAIN REPORT:", json.dumps(report, indent=2), flush=True)

    # Holdout eval, same model, no retraining
    holdout_samples = load_samples("/kaggle/input/goldenhour-triage-data/holdout.jsonl")
    h_texts = [build_input_text(s) for s in holdout_samples]
    h_acuity = [ACUITIES.index(s["acuity"]) for s in holdout_samples]
    h_facility = [FACILITIES.index(s["facility"]) for s in holdout_samples]
    h_ds = TriageDataset(h_texts, h_acuity, h_facility, tokenizer)
    h_loader = DataLoader(h_ds, batch_size=BATCH_SIZE)
    h_metrics = evaluate(model, h_loader, device)
    h_report = {
        **h_metrics, "n_holdout": len(holdout_samples),
        "caveat": "This holdout is LLM-generated (generate_holdout.py, different prompt/seed/"
                  "temperature than training data), NOT the independently human-written holdout "
                  "technical.md Section9.3 requires. A stress-test, not a verified safety claim.",
    }
    with open("/kaggle/working/holdout_report.json", "w") as f:
        json.dump(h_report, f, indent=2)
    print("HOLDOUT REPORT:", json.dumps(h_report, indent=2), flush=True)


if __name__ == "__main__":
    main()
