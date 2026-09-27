# Hospital Rank Utility Function

This document details the utility function used as the target label generator for our LightGBM LambdaRank model in the `hospital-rank` capability.

## Overview
The goal of ranking hospitals during an emergency is to minimize the expected time-to-definitive-care and ensure patient safety.

We define a continuous utility score for a candidate hospital $H$ for a patient $P$:

$U(H, P) = \text{ETA} + P(\text{no\_bed}) \times \text{reroute\_delay} + P(\text{no\_specialist}) \times \text{specialist\_delay} + \text{staleness\_penalty} + \text{comfort\_penalty}$

Where:
- **ETA**: Baseline travel time in seconds.
- **$P(\text{no\_bed})$**: The probability that a required bed is NOT available at ETA. (derived from `bed-nowcast`).
- **reroute\_delay**: Fixed average time (e.g., 900s) added if the ambulance has to reroute from $H$ to another facility.
- **$P(\text{no\_specialist})$**: The probability that a required specialist is not on duty or available.
- **specialist\_delay**: The average wait time (e.g., 1800s) if a specialist must be called in.
- **staleness\_penalty**: Added time to reflect uncertainty when data is old. $\text{Staleness (min)} \times 10s$.
- **comfort\_penalty**: Penalty added for poor road conditions, scaled by the patient's fragility. 

Since lower is better (it's a time/cost metric), we convert it to a maximization score:
$\text{Score} = 100000 - U(H, P)$

## Relevance Grading (0-4)
LambdaRank requires ordinal relevance grades. We generate these by computing the continuous utility score for all candidates in a query (an emergency event), and then binning them into 5 quantiles:
- **4 (Perfect)**: Top 20%
- **3 (Good)**: 20-40%
- **2 (Fair)**: 40-60%
- **1 (Poor)**: 60-80%
- **0 (Bad)**: Bottom 20%

This ensures that the ranker learns relative preference (which hospital is better for *this* emergency) rather than predicting an absolute score.
