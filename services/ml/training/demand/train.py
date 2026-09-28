"""LightGBM Poisson regression with lags 1/24/168h, neighbour-cell sums,
hour/weekday/festival flags (technical.md §9.15). Reports MAE and Poisson
deviance vs a historical-average baseline."""

import json

import h3
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error


def build_hourly_grid(df: pd.DataFrame) -> pd.DataFrame:
    all_cells = df["h3_cell"].unique()
    all_hours = pd.MultiIndex.from_product(
        [all_cells, range(90), range(24)], names=["h3_cell", "day", "hour"]
    ).to_frame(index=False)
    merged = all_hours.merge(df, on=["h3_cell", "day", "hour"], how="left")
    merged["calls"] = merged["calls"].fillna(0).astype(int)
    merged["weekday"] = merged["day"] % 7
    merged["is_festival"] = merged.groupby("day")["is_festival"].transform(lambda s: s.ffill().bfill()).fillna(0).astype(int)
    merged["cell_kind"] = merged.groupby("h3_cell")["cell_kind"].transform(lambda s: s.ffill().bfill())
    merged["t"] = merged["day"] * 24 + merged["hour"]
    return merged.sort_values(["h3_cell", "t"]).reset_index(drop=True)


def add_lag_features(grid: pd.DataFrame) -> pd.DataFrame:
    grid = grid.copy()
    for lag_hours, name in [(1, "lag_1h"), (24, "lag_24h"), (168, "lag_168h")]:
        grid[name] = grid.groupby("h3_cell")["calls"].shift(lag_hours)
    return grid


def add_neighbour_sums(grid: pd.DataFrame) -> pd.DataFrame:
    hourly_totals = grid.groupby(["h3_cell", "t"])["calls"].sum().unstack("h3_cell").fillna(0)
    neighbour_sum = {}
    for cell in hourly_totals.columns:
        neighbours = [c for c in h3.grid_disk(cell, 1) if c != cell and c in hourly_totals.columns]
        neighbour_sum[cell] = hourly_totals[neighbours].sum(axis=1) if neighbours else pd.Series(0, index=hourly_totals.index)
    neighbour_df = pd.DataFrame(neighbour_sum).stack().rename("neighbour_sum_calls").reset_index()
    neighbour_df.columns = ["t", "h3_cell", "neighbour_sum_calls"]
    return grid.merge(neighbour_df, on=["h3_cell", "t"], how="left")


def main() -> None:
    df = pd.read_csv("services/ml/data/demand/calls.csv")
    grid = build_hourly_grid(df)
    grid = add_lag_features(grid)
    grid = add_neighbour_sums(grid)

    features = ["hour", "weekday", "is_festival", "lag_1h", "lag_24h", "lag_168h", "neighbour_sum_calls"]
    grid["cell_kind_enc"] = grid["cell_kind"].astype("category").cat.codes
    features.append("cell_kind_enc")

    train = grid[grid["day"] < 75].dropna(subset=features)
    test = grid[grid["day"] >= 75].dropna(subset=features)

    model = lgb.LGBMRegressor(objective="poisson", n_estimators=300, max_depth=6, learning_rate=0.05, verbose=-1)
    model.fit(train[features], train["calls"])
    pred = np.clip(model.predict(test[features]), 0, None)

    mae = mean_absolute_error(test["calls"], pred)

    baseline_by_cell_hour = train.groupby(["h3_cell", "hour"])["calls"].mean()
    baseline_pred = test.set_index(["h3_cell", "hour"]).index.map(baseline_by_cell_hour).to_numpy()
    baseline_pred = pd.Series(baseline_pred).fillna(train["calls"].mean()).to_numpy()
    baseline_mae = mean_absolute_error(test["calls"], baseline_pred)

    def poisson_deviance(y_true, y_pred):
        y_pred = np.clip(y_pred, 1e-6, None)
        y_true = np.asarray(y_true, dtype=float)
        term = np.where(y_true > 0, y_true * np.log(y_true / y_pred), 0)
        return float(2 * np.mean(term - (y_true - y_pred)))

    deviance = poisson_deviance(test["calls"], pred)
    baseline_deviance = poisson_deviance(test["calls"], baseline_pred)

    model.booster_.save_model("services/ml/artifacts/demand/lightgbm_poisson.txt")

    report = {
        "mae": round(float(mae), 4), "baseline_mae": round(float(baseline_mae), 4),
        "poisson_deviance": round(deviance, 4), "baseline_poisson_deviance": round(baseline_deviance, 4),
        "mae_improvement_pct": round(100 * (1 - mae / baseline_mae), 1),
        "n_train": len(train), "n_test": len(test), "features": features,
    }
    with open("services/ml/training/demand/REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
