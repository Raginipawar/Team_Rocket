"""Bed-availability nowcasting training data (technical.md Section9.14).
Rewritten: the previous generator (1) used room types (ER/ICU/Ward/OR/NICU)
that don't match the real rooms.type enum (0001_init.sql: er_bed/resus_bay/
trauma_bay/icu_bed/labour_room/burns_unit/pediatric_er), and (2) stored
arrivals_next_1h/discharges_next_1h -- the ACTUAL realized future draws --
as if they were input features, which is data leakage (a real nowcast call
can't know the future arrival count, only a historical/estimated rate).
Fixed: features are the hospital's estimated rate going in, not the
realized outcome; the realized outcome is only ever the label."""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(13)
N_HOSPITALS = 10
ROOM_TYPES = ["er_bed", "resus_bay", "trauma_bay", "icu_bed", "labour_room", "burns_unit", "pediatric_er"]
DAYS = 60
ETA_CHOICES = [5, 10, 15, 20, 30, 45, 60, 90]


def main() -> None:
    rows = []
    for h in range(N_HOSPITALS):
        hospital_id = f"h_{h}"
        for room_type in ROOM_TYPES:
            capacity = RNG.integers(4, 30)
            occupancy = RNG.integers(0, capacity + 1)

            for day in range(DAYS):
                weekday = day % 7
                for hour in range(24):
                    peak = 9 <= hour <= 11 or 18 <= hour <= 20
                    lambda_arr_per_hr = 1.5 if peak else 0.4
                    discharge_rate_per_hr = occupancy / 4.0  # avg 4h length of stay

                    # Advance real state by one hour (ground truth simulation).
                    arrivals = RNG.poisson(lambda_arr_per_hr)
                    discharges = RNG.poisson(discharge_rate_per_hr)
                    occupancy = int(np.clip(occupancy + arrivals - discharges, 0, capacity))
                    free_now = capacity - occupancy

                    # One training example per hour: report at this hour,
                    # eta some minutes later. eta outcome continues the SAME
                    # rates forward (a real system would estimate these from
                    # recent history, not see the future draw).
                    eta_min = int(RNG.choice(ETA_CHOICES))
                    frac = eta_min / 60.0
                    eta_arrivals = RNG.poisson(lambda_arr_per_hr * frac)
                    eta_discharges = RNG.poisson(discharge_rate_per_hr * frac)
                    free_at_eta = int(np.clip(free_now - eta_arrivals + eta_discharges, 0, capacity))

                    rows.append({
                        "hospital_id": hospital_id, "room_type": room_type,
                        "last_reported_free": free_now,
                        "minutes_since_report": float(RNG.integers(0, 30)),
                        "eta_min": float(eta_min), "hour": hour, "weekday": weekday,
                        "arrival_rate_1h": round(lambda_arr_per_hr, 3),
                        "discharge_rate_1h": round(discharge_rate_per_hr, 3),
                        "incoming_reserved": int(RNG.poisson(0.5)),
                        "target_free_at_eta": free_at_eta,
                        "is_available_at_eta": int(free_at_eta >= 1),
                    })

    df = pd.DataFrame(rows)
    df.to_csv("services/ml/data/nowcast/nowcast_train.csv", index=False)
    print(f"wrote {len(df)} rows, availability rate: {df['is_available_at_eta'].mean():.3f}")


if __name__ == "__main__":
    main()
