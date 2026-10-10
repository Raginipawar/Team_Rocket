"""Real bed-nowcast models (technical.md Section9.14) -- the capability was
a 3-line hand-written decay formula inlined directly in router.py, never
trained on anything, ignoring 7 of the 10 real request fields entirely.
Trains two LightGBM models on the real feature set: a classifier for
p_available_at_eta and a regressor for expected_free_at_eta."""

import json

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.model_selection import train_test_split

ROOM_TYPES = ["er_bed", "resus_bay", "trauma_bay", "icu_bed", "labour_room", "burns_unit", "pediatric_er"]
FEATURES = [
    "last_reported_free", "minutes_since_report", "eta_min", "hour", "weekday",
    "arrival_rate_1h", "discharge_rate_1h", "incoming_reserved", "room_type_enc",
]


def main() -> None:
    df = pd.read_csv("services/ml/data/nowcast/nowcast_train.csv")
    df["room_type_enc"] = df["room_type"].apply(lambda r: ROOM_TYPES.index(r) if r in ROOM_TYPES else len(ROOM_TYPES))

    train_df, test_df = train_test_split(df, test_size=0.15, random_state=42, stratify=df["is_available_at_eta"])

    clf = lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.05, verbose=-1)
    clf.fit(train_df[FEATURES], train_df["is_available_at_eta"])
    proba = clf.predict_proba(test_df[FEATURES])[:, 1]
    auc = roc_auc_score(test_df["is_available_at_eta"], proba)
    brier = brier_score_loss(test_df["is_available_at_eta"], proba)

    reg = lgb.LGBMRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, verbose=-1)
    reg.fit(train_df[FEATURES], train_df["target_free_at_eta"])
    pred_free = reg.predict(test_df[FEATURES])
    mae = mean_absolute_error(test_df["target_free_at_eta"], pred_free)

    clf.booster_.save_model("services/ml/artifacts/nowcast/availability_classifier.txt")
    reg.booster_.save_model("services/ml/artifacts/nowcast/free_regressor.txt")

    report = {
        "auc": round(float(auc), 4), "brier": round(float(brier), 4),
        "mae_free_beds": round(float(mae), 3),
        "n_train": len(train_df), "n_test": len(test_df), "features": FEATURES,
    }
    with open("services/ml/training/nowcast/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
