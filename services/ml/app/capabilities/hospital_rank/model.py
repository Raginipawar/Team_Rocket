import os
import pickle
import numpy as np
import shap
import pandas as pd
from typing import List
from .schemas import HospitalRankRequest, HospitalRankResponse, Explanation

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "ranker.pkl")
_model = None
_explainer = None

def load_model():
    global _model, _explainer
    if _model is None:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                _model = pickle.load(f)
            _explainer = shap.TreeExplainer(_model)

async def rank_hospitals(req: HospitalRankRequest) -> List[HospitalRankResponse]:
    load_model()
    
    if not req.candidates:
        return []
        
    features = ["eta_sec", "p_bed_available", "staleness_min", "road_comfort"]
    
    # Check if model exists, fallback to mock-like behavior if not
    if _model is None:
        # fallback simple heuristic
        responses = []
        for i, cand in enumerate(req.candidates):
            responses.append(HospitalRankResponse(
                hospital_id=cand.hospital_id,
                score=10.0 - i,
                rank=i+1,
                explanation=[
                    Explanation(factor="heuristic", value="fallback", contribution=1.0, text="Model not loaded.")
                ],
                eligible=True
            ))
        return responses

    data = []
    for cand in req.candidates:
        data.append({
            "eta_sec": cand.features.eta_sec,
            "p_bed_available": cand.features.p_bed_available_at_eta,
            "staleness_min": cand.features.staleness_min,
            "road_comfort": cand.features.road_comfort,
        })
        
    df = pd.DataFrame(data)[features]
    
    scores = _model.predict(df)
    shap_values = _explainer.shap_values(df)
    
    # Sort candidates by score descending
    indexed_scores = list(enumerate(scores))
    indexed_scores.sort(key=lambda x: x[1], reverse=True)
    
    responses = []
    for rank, (idx, score) in enumerate(indexed_scores, start=1):
        cand = req.candidates[idx]
        
        # Build explanation
        sv = shap_values[idx]
        explanations = []
        
        feature_names_display = {
            "eta_sec": "Travel Time",
            "p_bed_available": "Bed Availability",
            "staleness_min": "Data Recency",
            "road_comfort": "Road Comfort"
        }
        
        for f_idx, f_name in enumerate(features):
            val = df.iloc[idx][f_name]
            contrib = float(sv[f_idx])
            
            # Format text based on contribution
            if f_name == "eta_sec":
                text = f"ETA is {val:.1f}s ({'Positive' if contrib > 0 else 'Negative'} impact)"
            elif f_name == "p_bed_available":
                text = f"{(val*100):.1f}% bed prob ({'Positive' if contrib > 0 else 'Negative'} impact)"
            elif f_name == "staleness_min":
                text = f"Data {val:.1f}m old ({'Positive' if contrib > 0 else 'Negative'} impact)"
            else:
                text = f"Comfort {val:.1f} ({'Positive' if contrib > 0 else 'Negative'} impact)"
                
            explanations.append(Explanation(
                factor=f_name,
                value=str(val),
                contribution=contrib,
                text=text
            ))
            
        responses.append(HospitalRankResponse(
            hospital_id=cand.hospital_id,
            score=float(score),
            rank=rank,
            explanation=explanations,
            eligible=True
        ))
        
    return responses
