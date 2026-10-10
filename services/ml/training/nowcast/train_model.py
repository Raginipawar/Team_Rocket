import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import pickle

def generate_nowcast_dataset(n_samples=5000):
    np.random.seed(42)
    last_reported_free = np.random.randint(0, 30, n_samples)
    minutes_since_report = np.random.uniform(0, 120, n_samples)
    eta_min = np.random.uniform(5, 60, n_samples)
    hour = np.random.randint(0, 24, n_samples)
    weekday = np.random.randint(0, 7, n_samples)
    arrival_rate_1h = np.random.uniform(0.1, 5.0, n_samples)
    discharge_rate_1h = np.random.uniform(0.1, 5.0, n_samples)
    incoming_reserved = np.random.randint(0, 5, n_samples)
    
    # Calculate target (simulated realistic physics)
    # Expected free at ETA = last_reported_free - incoming_reserved 
    #                        - arrivals_during_time + discharges_during_time
    total_time_min = minutes_since_report + eta_min
    total_time_hr = total_time_min / 60.0
    
    # add some noise
    arrivals = np.random.poisson(arrival_rate_1h * total_time_hr)
    discharges = np.random.poisson(discharge_rate_1h * total_time_hr)
    
    expected_free = last_reported_free - incoming_reserved - arrivals + discharges
    
    df = pd.DataFrame({
        "last_reported_free": last_reported_free,
        "minutes_since_report": minutes_since_report,
        "eta_min": eta_min,
        "hour": hour,
        "weekday": weekday,
        "arrival_rate_1h": arrival_rate_1h,
        "discharge_rate_1h": discharge_rate_1h,
        "incoming_reserved": incoming_reserved,
        "target_free": expected_free
    })
    
    return df

def train_nowcast():
    df = generate_nowcast_dataset()
    features = [
        "last_reported_free", "minutes_since_report", "eta_min", 
        "hour", "weekday", "arrival_rate_1h", "discharge_rate_1h", 
        "incoming_reserved"
    ]
    X = df[features]
    y = df["target_free"]
    
    model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
    model.fit(X, y)
    
    model_dir = "../../app/capabilities/bed_nowcast/models"
    os.makedirs(model_dir, exist_ok=True)
    
    with open(f"{model_dir}/nowcast_rf.pkl", "wb") as f:
        pickle.dump(model, f)
        
    print(f"Nowcast model saved to {model_dir}/nowcast_rf.pkl")

if __name__ == "__main__":
    train_nowcast()
