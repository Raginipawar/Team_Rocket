"""LightGBM classifier (accept within OFFER_EXPIRY_SEC=20s) + regressor
(accept latency), technical.md §9.6. Reports AUC, Brier, latency MAE, and a
simulated time-to-accept comparison vs a nearest-first baseline."""

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURES = ["eta_sec", "distance_m", "hours_on_shift", "mins_since_last_job",
            "accept_rate_7d", "avg_accept_latency_s", "declines_today"]
OFFER_EXPIRY_SEC = 20


def main() -> None:
    df = pd.read_csv("services/ml/data/dispatch/offers.csv")
    df["accept_within_expiry"] = ((df["accepted"] == 1) & (df["latency_s"] <= OFFER_EXPIRY_SEC)).astype(int)

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["accept_within_expiry"])

    clf = lgb.LGBMClassifier(n_estimators=200, max_depth=5, learning_rate=0.05, verbose=-1)
    clf.fit(train_df[FEATURES], train_df["accept_within_expiry"])
    test_proba = clf.predict_proba(test_df[FEATURES])[:, 1]
    auc = roc_auc_score(test_df["accept_within_expiry"], test_proba)
    brier = brier_score_loss(test_df["accept_within_expiry"], test_proba)

    accepted_train = train_df[train_df["accepted"] == 1]
    accepted_test = test_df[test_df["accepted"] == 1]
    reg = lgb.LGBMRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, verbose=-1)
    reg.fit(accepted_train[FEATURES], accepted_train["latency_s"])
    latency_pred = reg.predict(accepted_test[FEATURES])
    latency_mae = mean_absolute_error(accepted_test["latency_s"], latency_pred)

    # Simulated A/B: technical.md §11.1 offers OFFERS_PER_ROUND=4 candidates
    # SIMULTANEOUSLY each round -- ordering among the chosen 4 doesn't matter,
    # only WHICH 4 (of a larger candidate pool) get picked. Compare our
    # top-4-by-score selection vs nearest-first-4 selection, both drawn from
    # the same 10-candidate pool, on time-to-first-accept (min latency among
    # those who accept within the offer expiry; escalation cost if none do).
    OFFERS_PER_ROUND = 4
    POOL_SIZE = 10
    rng = np.random.default_rng(0)

    def time_to_first_accept(selected: pd.DataFrame) -> float:
        accepted_within = selected[(selected["accepted"] == 1) & (selected["latency_s"] <= OFFER_EXPIRY_SEC)]
        if len(accepted_within) == 0:
            return OFFER_EXPIRY_SEC * 1.5  # no acceptance -> next round / escalation cost
        return accepted_within["latency_s"].min()

    our_times, nearest_times = [], []
    for _ in range(500):
        pool = test_df.sample(POOL_SIZE, random_state=rng.integers(0, 1_000_000))
        pool_proba = clf.predict_proba(pool[FEATURES])[:, 1]
        pool_latency = reg.predict(pool[FEATURES])
        score = pool_proba / (pool["eta_sec"].values + pool_latency)

        our_selection = pool.iloc[np.argsort(-score)[:OFFERS_PER_ROUND]]
        nearest_selection = pool.sort_values("distance_m").iloc[:OFFERS_PER_ROUND]

        our_times.append(time_to_first_accept(our_selection))
        nearest_times.append(time_to_first_accept(nearest_selection))

    clf.booster_.save_model("services/ml/artifacts/dispatch_rank/accept_classifier.txt")
    reg.booster_.save_model("services/ml/artifacts/dispatch_rank/latency_regressor.txt")

    report = {
        "auc": round(float(auc), 4), "brier": round(float(brier), 4),
        "latency_mae_s": round(float(latency_mae), 2),
        "mean_time_to_accept_ours_s": round(float(np.mean(our_times)), 2),
        "mean_time_to_accept_nearest_first_s": round(float(np.mean(nearest_times)), 2),
        "improvement_pct": round(100 * (1 - np.mean(our_times) / np.mean(nearest_times)), 1),
        "features": FEATURES, "n_train": len(train_df), "n_test": len(test_df),
    }
    with open("services/ml/training/dispatch/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
