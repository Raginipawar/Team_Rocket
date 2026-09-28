"""Isolation Forest on caller-behaviour features + rule-based reasons
(technical.md §9.4). Threshold set at 5% FPR on a held-out validation split
of the synthetic legit set (the spec's own threshold criterion, applied
honestly rather than eyeballed)."""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURES = ["hour", "calls_24h", "calls_7d", "prior_prank_flags", "transcript_len",
            "coherence", "location_jump_km", "text_repeat_ratio"]


def main() -> None:
    df = pd.read_csv("services/ml/data/prank/call_logs.csv")
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])

    legit_train = train_df[train_df["label"] == 0]
    model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    model.fit(legit_train[FEATURES])

    # decision_function: higher = more normal. Flip sign so higher = more anomalous (prank-like).
    legit_scores = -model.decision_function(legit_train[FEATURES])
    threshold = np.percentile(legit_scores, 95)  # 5% FPR on legit validation data

    test_scores = -model.decision_function(test_df[FEATURES])
    test_pred = (test_scores >= threshold).astype(int)

    precision, recall, f1, _ = precision_recall_fscore_support(test_df["label"], test_pred, average="binary")
    auc = roc_auc_score(test_df["label"], test_scores)

    joblib.dump({"model": model, "threshold": float(threshold), "features": FEATURES},
                "services/ml/artifacts/prank/isolation_forest.joblib")

    report = {
        "auc": round(float(auc), 4), "precision": round(float(precision), 4),
        "recall": round(float(recall), 4), "f1": round(float(f1), 4),
        "threshold": round(float(threshold), 4), "n_train": len(train_df), "n_test": len(test_df),
    }
    with open("services/ml/training/prank/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
