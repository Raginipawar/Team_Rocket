"""Diagnostic: extract frozen MuRIL [CLS] embeddings and fit plain sklearn
classifiers, to isolate whether the PyTorch training loop has a bug or the
synthetic data/frozen features genuinely carry weak signal at this size."""

import json
import sys

sys.path.insert(0, "services/ml")
sys.modules.pop("transformers.modeling_utils", None)
import transformers.modeling_utils as _tf_modeling_utils
_tf_modeling_utils.check_torch_load_is_safe = lambda: None

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "google/muril-base-cased"
ACUITIES = ["critical", "urgent", "stable"]
FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]


def main() -> None:
    samples = [json.loads(l) for l in open("services/ml/data/triage/synthetic.jsonl", encoding="utf-8")]
    texts = [f"[TEXT] {s['text']} [FACTS] language={s.get('language','en')}" for s in samples]
    acuity_labels = np.array([ACUITIES.index(s["acuity"]) for s in samples])
    facility_labels = np.array([FACILITIES.index(s["facility"]) for s in samples])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()

    cls_embeddings, mean_embeddings = [], []
    with torch.no_grad():
        for i in range(0, len(texts), 16):
            batch = texts[i:i + 16]
            enc = tokenizer(batch, truncation=True, padding=True, max_length=256, return_tensors="pt").to(device)
            out = model(**enc)
            cls_embeddings.append(out.last_hidden_state[:, 0].cpu().numpy())
            mask = enc["attention_mask"].unsqueeze(-1).float()
            mean_pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            mean_embeddings.append(mean_pooled.cpu().numpy())

    for pooling_name, embeds in [("CLS", cls_embeddings), ("mean-pool", mean_embeddings)]:
        X = np.concatenate(embeds, axis=0)
        print(f"[{pooling_name}] embeddings shape: {X.shape}")
        for name, y in [("acuity", acuity_labels), ("facility", facility_labels)]:
            clf = LogisticRegression(max_iter=2000, class_weight="balanced")
            scores = cross_val_score(clf, X, y, cv=5, scoring="f1_macro")
            print(f"[{pooling_name}] {name}: 5-fold macro-F1 = {scores.mean():.4f} (+/- {scores.std():.4f}), "
                  f"per-fold: {scores.round(3).tolist()}")


if __name__ == "__main__":
    main()
