"""Simulated caller-behaviour logs, legitimate vs prank (technical.md §9.4).
Legitimate calls: low frequency, coherent, geographically stable, no repeat
text. Pranks: bursty calls from the same phone, incoherent/short transcripts,
large location jumps between calls, repeated stock phrases."""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
N_LEGIT = 4000
N_PRANK = 800  # real-world prank rate is far lower than half; keep the base rate realistic


def gen_legit(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "hour": RNG.integers(0, 24, n),
        "calls_24h": RNG.poisson(1.0, n).clip(0, 5),
        "calls_7d": RNG.poisson(2.0, n).clip(0, 10),
        "prior_prank_flags": np.zeros(n, dtype=int),
        "transcript_len": RNG.normal(180, 60, n).clip(20, 600),
        "coherence": RNG.beta(8, 2, n),  # skewed high
        "location_jump_km": RNG.exponential(0.5, n).clip(0, 5),
        "text_repeat_ratio": RNG.beta(1, 8, n),  # skewed low
        "label": 0,
    })


def gen_prank(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "hour": RNG.integers(0, 24, n),
        "calls_24h": RNG.poisson(6.0, n).clip(1, 30),
        "calls_7d": RNG.poisson(15.0, n).clip(2, 60),
        "prior_prank_flags": RNG.poisson(1.5, n).clip(0, 10),
        "transcript_len": RNG.normal(40, 30, n).clip(0, 200),
        "coherence": RNG.beta(2, 6, n),  # skewed low
        "location_jump_km": RNG.exponential(8, n).clip(0, 100),
        "text_repeat_ratio": RNG.beta(6, 2, n),  # skewed high
        "label": 1,
    })


def main() -> None:
    df = pd.concat([gen_legit(N_LEGIT), gen_prank(N_PRANK)], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df.to_csv("services/ml/data/prank/call_logs.csv", index=False)
    print(f"wrote {len(df)} rows ({N_LEGIT} legit, {N_PRANK} prank)")


if __name__ == "__main__":
    main()
