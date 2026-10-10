"""Real LightGBM LambdaRank model for hospital ranking (technical.md
Section9.13) -- the capability was mock-only before this (model.py just
sorted candidates by eta_sec, no trained model, no explanation ever
generated). Trains on generate_data.py's simulated-episode utility labels,
reports NDCG@3 against the held-out query groups, and fits a SHAP
TreeExplainer so model.py can produce real per-prediction explanations."""

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

FEATURES = [
    "facility_match", "required_resources_available_prob", "p_bed_available_at_eta",
    "eta_sec", "eta_high_sec", "road_comfort", "specialist_on_duty_at_eta",
    "staleness_min", "occupancy_ratio", "rejection_rate_24h", "incoming_reserved_count",
    "stabilization_capable", "fragility_high", "fragility_medium",
]


def _ndcg_at_k(y_true: np.ndarray, y_pred: np.ndarray, k: int = 3) -> float:
    order = np.argsort(-y_pred)[:k]
    gains = (2 ** y_true[order] - 1)
    discounts = 1 / np.log2(np.arange(2, len(order) + 2))
    dcg = float(np.sum(gains * discounts))

    ideal_order = np.argsort(-y_true)[:k]
    ideal_gains = (2 ** y_true[ideal_order] - 1)
    idcg = float(np.sum(ideal_gains * discounts[:len(ideal_order)]))
    return dcg / idcg if idcg > 0 else 1.0


def main() -> None:
    df = pd.read_csv("services/ml/data/hospital_rank/lambdarank_train.csv")

    splitter = GroupShuffleSplit(test_size=0.15, random_state=42)
    train_idx, test_idx = next(splitter.split(df, groups=df["query_id"]))
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]

    train_group_sizes = train_df.groupby("query_id", sort=False).size().to_numpy()
    model = lgb.LGBMRanker(objective="lambdarank", n_estimators=200, max_depth=5,
                            learning_rate=0.05, verbose=-1)
    model.fit(train_df[FEATURES], train_df["relevance"], group=train_group_sizes)

    ndcg_scores = []
    for qid, group in test_df.groupby("query_id"):
        preds = model.predict(group[FEATURES])
        ndcg_scores.append(_ndcg_at_k(group["relevance"].to_numpy(), preds, k=3))
    mean_ndcg_at_3 = float(np.mean(ndcg_scores))

    model.booster_.save_model("services/ml/artifacts/hospital_rank/lambdarank.txt")

    # LightGBM's own pred_contrib=True gives real TreeSHAP values natively --
    # the external `shap` package's numba dependency conflicts with this
    # environment's numpy 2.2 (ImportError: "Numba needs NumPy 2.0 or
    # less"), the same category of numpy-ecosystem version conflict already
    # found and worked around elsewhere in this project (services/ml/app/
    # registry.py). No external dependency needed for this.
    sample = test_df[FEATURES].sample(min(200, len(test_df)), random_state=42)
    contrib = model.booster_.predict(sample, pred_contrib=True)  # shape: (n, n_features + 1), last col is bias
    shap_values = contrib[:, :-1]
    mean_abs_shap = {f: round(float(np.mean(np.abs(shap_values[:, i]))), 4) for i, f in enumerate(FEATURES)}

    report = {
        "n_train_rows": len(train_df), "n_test_rows": len(test_df),
        "n_train_queries": train_df["query_id"].nunique(), "n_test_queries": test_df["query_id"].nunique(),
        "ndcg_at_3": round(mean_ndcg_at_3, 4),
        "mean_abs_shap_by_feature": dict(sorted(mean_abs_shap.items(), key=lambda kv: -kv[1])),
        "features": FEATURES,
    }
    with open("services/ml/training/hospital_rank/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
