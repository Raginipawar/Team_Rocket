import os
import pandas as pd
import lightgbm as lgb
import pickle
from generate_data import generate_hospital_rank_data

def train_hospital_rank():
    if not os.path.exists("lambdarank_train.csv"):
        generate_hospital_rank_data()
        
    df = pd.read_csv("lambdarank_train.csv")
    
    # Sort by query_id for lambdarank
    df = df.sort_values("query_id")
    
    features = ["eta_sec", "p_bed_available", "staleness_min", "road_comfort"]
    X = df[features]
    y = df["relevance"]
    group = df.groupby("query_id").size().values
    
    # Train LGBMRanker
    model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        importance_type="gain",
        min_child_samples=5
    )
    
    model.fit(
        X, y,
        group=group
    )
    
    # Ensure model directory exists
    model_dir = "../../app/capabilities/hospital_rank/models"
    os.makedirs(model_dir, exist_ok=True)
    
    with open(f"{model_dir}/ranker.pkl", "wb") as f:
        pickle.dump(model, f)
        
    print(f"Model saved to {model_dir}/ranker.pkl")

if __name__ == "__main__":
    train_hospital_rank()
