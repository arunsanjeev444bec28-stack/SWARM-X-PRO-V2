import os
import time
import joblib
import pandas as pd

_model = None
_model_path = "data/risk_model.joblib"

def load_model():
    global _model
    if _model is None and os.path.exists(_model_path):
        _model = joblib.load(_model_path)
    return _model

def predict_risk(features: dict) -> dict:
    """
    Returns risk probability and class.
    Graceful fallback if model is not trained.
    """
    model = load_model()
    if not model:
        return {
            "risk_probability": 0.0,
            "risk_class": 0,
            "error": "Model not trained"
        }
        
    # We must ensure the features match exactly the expected columns.
    # We can infer the columns from model.feature_names_in_ if available.
    try:
        feature_cols = model.feature_names_in_
        # Convert dictionary to DataFrame with exactly those columns
        # Missing features will be set to 0.0
        row = {c: features.get(c, 0.0) for c in feature_cols}
        df = pd.DataFrame([row])
        
        prob = float(model.predict_proba(df)[0, 1])
        cls = int(model.predict(df)[0])
        
        return {
            "risk_probability": prob,
            "risk_class": cls
        }
    except Exception as e:
        return {
            "risk_probability": 0.0,
            "risk_class": 0,
            "error": str(e)
        }
