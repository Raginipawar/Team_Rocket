import os
import pickle
import numpy as np
import pandas as pd
from typing import List
from .schemas import BedNowcastRequest, BedNowcastResponse

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "nowcast_rf.pkl")
_model = None

def load_model():
    global _model
    if _model is None:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                _model = pickle.load(f)

async def predict_bed_availability(req: BedNowcastRequest) -> BedNowcastResponse:
    load_model()
    
    if _model is None:
        # Fallback heuristic if model not found
        if req.minutes_since_report < 10:
            p = 0.85
        else:
            p = max(0.3, 0.85 - req.minutes_since_report * 0.01)
        
        return BedNowcastResponse(
            p_available_at_eta=p,
            expected_free_at_eta=float(req.last_reported_free),
            interval=[max(0.0, req.last_reported_free - 1.0), req.last_reported_free + 1.0]
        )
        
    features = [
        "last_reported_free", "minutes_since_report", "eta_min", 
        "hour", "weekday", "arrival_rate_1h", "discharge_rate_1h", 
        "incoming_reserved"
    ]
    
    df = pd.DataFrame([{
        "last_reported_free": req.last_reported_free,
        "minutes_since_report": req.minutes_since_report,
        "eta_min": req.eta_min,
        "hour": req.hour,
        "weekday": req.weekday,
        "arrival_rate_1h": req.arrival_rate_1h,
        "discharge_rate_1h": req.discharge_rate_1h,
        "incoming_reserved": req.incoming_reserved
    }])
    
    pred_free = _model.predict(df)[0]
    
    # Estimate standard deviation for interval (dummy approach for RF without quantile prediction)
    # RF trees std dev
    preds = np.array([tree.predict(df.values) for tree in _model.estimators_])
    std_dev = preds.std()
    
    lower = max(0.0, pred_free - 1.96 * std_dev)
    upper = max(0.0, pred_free + 1.96 * std_dev)
    
    # Calculate probability of having > 0 beds using normal approximation
    from scipy.stats import norm
    
    if std_dev > 0:
        p_available = 1.0 - norm.cdf(0.5, loc=pred_free, scale=std_dev)
    else:
        p_available = 1.0 if pred_free >= 0.5 else 0.0
        
    return BedNowcastResponse(
        p_available_at_eta=float(np.clip(p_available, 0.0, 1.0)),
        expected_free_at_eta=float(max(0.0, pred_free)),
        interval=[float(lower), float(upper)]
    )
