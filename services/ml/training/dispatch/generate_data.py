"""Driver behaviour generator (technical.md §9.6): per-driver propensity
(Beta), fatigue (hours on shift), distance aversion, recent-job decline
history. Exports driver_params.json for B's simulator to use the same
per-driver parameters (wd-person-a-intake-dispatch.md A11 hand-off)."""

import json

import numpy as np
import pandas as pd

RNG = np.random.default_rng(11)
N_DRIVERS = 150
N_OFFERS_PER_DRIVER = 40


def gen_drivers(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "driver_id": [f"drv_{i:04d}" for i in range(n)],
        "base_accept_propensity": RNG.beta(6, 3, n),      # most drivers lean toward accepting
        "distance_aversion": RNG.gamma(2.0, 0.15, n),      # how much distance hurts accept prob
        "fatigue_sensitivity": RNG.gamma(2.0, 0.1, n),     # how much hours-on-shift hurts accept prob
        "base_latency_s": RNG.normal(8, 3, n).clip(2, 25), # baseline decision speed
    })


def simulate_offers(drivers: pd.DataFrame, n_per_driver: int) -> pd.DataFrame:
    rows = []
    for _, d in drivers.iterrows():
        for _ in range(n_per_driver):
            distance_m = np.clip(RNG.exponential(3000), 200, 20000)
            eta_sec = distance_m / (30_000 / 3600)  # ~30 km/h average
            hours_on_shift = RNG.uniform(0, 10)
            mins_since_last_job = np.clip(RNG.exponential(30), 0, 300)
            declines_today = RNG.poisson(1.5)
            accept_rate_7d = np.clip(d["base_accept_propensity"] + RNG.normal(0, 0.05), 0.05, 0.98)
            avg_accept_latency_s = max(2.0, d["base_latency_s"] + RNG.normal(0, 2))

            logit = (
                5.0 * (d["base_accept_propensity"] - 0.5)
                - d["distance_aversion"] * 2.5 * (distance_m / 5000)
                - d["fatigue_sensitivity"] * 2.5 * (hours_on_shift / 10)
                - 0.3 * declines_today
                + 0.5 * (1 - mins_since_last_job / 300)
            )
            accept_prob_true = 1 / (1 + np.exp(-logit))
            accepted = RNG.random() < accept_prob_true
            latency_s = max(1.0, RNG.normal(avg_accept_latency_s, 1.5)) if accepted else np.nan

            rows.append({
                "driver_id": d["driver_id"], "eta_sec": eta_sec, "distance_m": distance_m,
                "hours_on_shift": hours_on_shift, "mins_since_last_job": mins_since_last_job,
                "accept_rate_7d": accept_rate_7d, "avg_accept_latency_s": avg_accept_latency_s,
                "declines_today": declines_today, "accepted": int(accepted), "latency_s": latency_s,
            })
    return pd.DataFrame(rows)


def main() -> None:
    drivers = gen_drivers(N_DRIVERS)
    offers = simulate_offers(drivers, N_OFFERS_PER_DRIVER)
    offers.to_csv("services/ml/data/dispatch/offers.csv", index=False)

    driver_params = {
        row["driver_id"]: {
            "base_accept_propensity": round(row["base_accept_propensity"], 4),
            "distance_aversion": round(row["distance_aversion"], 4),
            "fatigue_sensitivity": round(row["fatigue_sensitivity"], 4),
            "base_latency_s": round(row["base_latency_s"], 2),
        }
        for _, row in drivers.iterrows()
    }
    with open("services/ml/data/dispatch/driver_params.json", "w") as f:
        json.dump(driver_params, f, indent=2)

    print(f"wrote {len(offers)} offers across {N_DRIVERS} drivers, "
          f"accept rate {offers['accepted'].mean():.2%}")


if __name__ == "__main__":
    main()
