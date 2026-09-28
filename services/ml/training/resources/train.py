"""LightGBM one-vs-rest multi-label over the mapping-table dataset
(technical.md §9.10). One booster per item; reports per-label AUC and
micro-F1 across all items."""

import json

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

ITEMS = [
    "emergency_physician", "cardiologist", "neurologist", "trauma_surgeon", "burns_surgeon",
    "obstetrician", "pediatrician", "pulmonologist", "anesthetist", "er_nurse",
    "ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator", "dialysis", "operating_theatre",
    "blood_o_neg", "blood_o_pos", "blood_a_pos", "blood_b_pos", "blood_ab_pos",
]
INPUT_COLS = ["facility_enc", "acuity_enc", "bleeding_enc", "pregnant", "age"]


def main() -> None:
    df = pd.read_csv("services/ml/data/resources/samples.csv")

    facility_enc, acuity_enc, bleeding_enc = LabelEncoder(), LabelEncoder(), LabelEncoder()
    df["facility_enc"] = facility_enc.fit_transform(df["facility"])
    df["acuity_enc"] = acuity_enc.fit_transform(df["acuity"])
    df["bleeding_enc"] = bleeding_enc.fit_transform(df["bleeding"])
    df["pregnant"] = df["pregnant"].astype(int)

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

    per_label_auc, all_true, all_pred = {}, [], []
    for item in ITEMS:
        model = lgb.LGBMClassifier(n_estimators=150, max_depth=4, learning_rate=0.08, verbose=-1)
        model.fit(train_df[INPUT_COLS], train_df[item])
        proba = model.predict_proba(test_df[INPUT_COLS])[:, 1]
        pred = (proba >= 0.5).astype(int)

        if test_df[item].nunique() > 1:
            per_label_auc[item] = round(float(roc_auc_score(test_df[item], proba)), 4)
        else:
            per_label_auc[item] = None  # only one class present in test split -- AUC undefined, not faked as 1.0

        all_true.extend(test_df[item].tolist())
        all_pred.extend(pred.tolist())
        model.booster_.save_model(f"services/ml/artifacts/resources/{item}.txt")

    micro_f1 = f1_score(all_true, all_pred, average="micro")

    report = {
        "micro_f1": round(float(micro_f1), 4),
        "per_label_auc": per_label_auc,
        "n_train": len(train_df), "n_test": len(test_df), "items": ITEMS,
        "facility_classes": facility_enc.classes_.tolist(),
        "acuity_classes": acuity_enc.classes_.tolist(),
        "bleeding_classes": bleeding_enc.classes_.tolist(),
    }
    with open("services/ml/training/resources/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
