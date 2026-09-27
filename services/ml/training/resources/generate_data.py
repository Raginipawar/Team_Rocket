"""Noisy dataset from mapping.csv (facility x acuity x facts -> items),
technical.md §9.10. Extracted-facts modifiers on top of the clinician-style
base table: severe bleeding raises blood-type probs, anesthetist follows an
operating theatre need, pregnant raises obstetric items regardless of
facility label (unconfirmed triage), age<14 raises pediatric items."""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(21)
ITEMS = [
    "emergency_physician", "cardiologist", "neurologist", "trauma_surgeon", "burns_surgeon",
    "obstetrician", "pediatrician", "pulmonologist", "anesthetist", "er_nurse",
    "ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator", "dialysis", "operating_theatre",
    "blood_o_neg", "blood_o_pos", "blood_a_pos", "blood_b_pos", "blood_ab_pos",
]
FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory", "obstetric", "pediatric", "poisoning", "general"]
ACUITIES = ["critical", "urgent", "stable"]
N_SAMPLES = 6000


def load_mapping() -> dict:
    df = pd.read_csv("services/ml/training/resources/mapping.csv")
    table = {}
    for _, row in df.iterrows():
        table.setdefault((row["facility"], row["acuity"]), {})[row["item"]] = row["base_prob"]
    return table


def sample_row(mapping: dict, facility: str, acuity: str) -> dict:
    bleeding = RNG.choice(["none", "mild", "severe"], p=[0.6, 0.25, 0.15])
    pregnant = RNG.random() < (0.15 if facility == "obstetric" else 0.02)
    age = int(np.clip(RNG.normal(38, 20), 0, 90))
    needs_surgery_signal = RNG.random() < 0.2

    base = mapping.get((facility, acuity), {})
    row = {"facility": facility, "acuity": acuity, "bleeding": bleeding,
           "pregnant": pregnant, "age": age}

    for item in ITEMS:
        p = base.get(item, 0.03)  # small background noise probability for unrelated items
        if item.startswith("blood_") and bleeding == "severe":
            p = max(p, 0.5)
        elif item.startswith("blood_") and bleeding == "mild":
            p = max(p, 0.15)
        if item == "anesthetist" and (needs_surgery_signal or base.get("operating_theatre", 0) > 0.3):
            p = max(p, 0.5)
        if item == "obstetrician" and pregnant:
            p = max(p, 0.6)
        if item == "pediatrician" and age < 14:
            p = max(p, 0.6)

        row[item] = int(RNG.random() < np.clip(p + RNG.normal(0, 0.05), 0, 1))  # noise on top of base_prob

    return row


def main() -> None:
    mapping = load_mapping()
    rows = []
    for _ in range(N_SAMPLES):
        facility = RNG.choice(FACILITIES)
        acuity = RNG.choice(ACUITIES, p=[0.3, 0.4, 0.3])
        rows.append(sample_row(mapping, facility, acuity))

    df = pd.DataFrame(rows)
    df.to_csv("services/ml/data/resources/samples.csv", index=False)
    print(f"wrote {len(df)} rows; positive rate per item:")
    print(df[ITEMS].mean().round(3))


if __name__ == "__main__":
    main()
