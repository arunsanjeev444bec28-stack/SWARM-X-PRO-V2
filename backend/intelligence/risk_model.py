import os
import json
import joblib
import pandas as pd
import numpy as np
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

def train_model():
    dataset_path = "data/risk_dataset.csv"
    if not os.path.exists(dataset_path):
        print("Error: Dataset not found.")
        return False
        
    df = pd.read_csv(dataset_path)
    if len(df) == 0:
        print("Error: Empty dataset.")
        return False
        
    # Features and labels
    feature_cols = [c for c in df.columns if c not in ["scenario_id", "run_id", "robot_id", "task_id", "risk", "risk_reason"]]
    
    X = df[feature_cols]
    y = df["risk"]
    groups = df["scenario_id"]
    
    # Check class balance
    positive_samples = y.sum()
    total_samples = len(y)
    positive_percentage = positive_samples / total_samples if total_samples > 0 else 0
    
    print(f"Dataset Size: {total_samples}")
    print(f"Positive Samples (Risk=1): {positive_samples} ({positive_percentage*100:.1f}%)")
    
    if positive_samples == 0 or positive_samples == total_samples:
        print("Warning: Dataset has only one class. Cannot train a meaningful binary classifier.")
        return False
        
    # Grouped split to prevent data leakage from the same scenario
    gss = GroupShuffleSplit(n_splits=1, train_size=0.8, random_state=42)
    
    # We will try up to 20 different random states to find a split with positive samples in both
    current_seed = 42
    valid_split = False
    
    while not valid_split and current_seed < 62:
        gss = GroupShuffleSplit(n_splits=1, train_size=0.8, random_state=current_seed)
        train_idx, test_idx = next(gss.split(X, y, groups))
        
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        if y_tr.sum() >= 5 and y_te.sum() >= 5:
            valid_split = True
        else:
            current_seed += 1
            
    if not valid_split:
        print("Warning: Could not find a grouped split that places positive samples in both train and test. Try generating more data.")
        # We will just fall back to standard split
        train_idx, test_idx = next(gss.split(X, y, groups))
    
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    # 1. Train Random Forest
    rf_clf = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42, class_weight="balanced")
    rf_clf.fit(X_train, y_train)
    
    # 2. Train XGBoost
    xgb_clf = None
    if HAS_XGB:
        # scale_pos_weight for imbalance
        scale_pos = (len(y_train) - y_train.sum()) / max(1, y_train.sum())
        xgb_clf = xgb.XGBClassifier(n_estimators=50, max_depth=8, random_state=42, scale_pos_weight=scale_pos, use_label_encoder=False, eval_metric='logloss')
        xgb_clf.fit(X_train, y_train)
    
    # Function to eval model
    def eval_model(clf, name):
        y_pred = clf.predict(X_test)
        if hasattr(clf, "predict_proba"):
            y_prob = clf.predict_proba(X_test)[:, 1]
        else:
            y_prob = y_pred
            
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        try:
            roc_auc = roc_auc_score(y_test, y_prob)
        except ValueError:
            roc_auc = 0.0
            
        # Measure latency
        start = time.time()
        for i in range(100): # Small batch
            clf.predict(X_test.iloc[0:1])
        latency = (time.time() - start) / 100 * 1000 # ms per prediction
        
        return {
            "name": name,
            "clf": clf,
            "acc": acc, "prec": prec, "rec": rec, "f1": f1, "roc_auc": roc_auc,
            "latency": latency,
            "y_pred": y_pred
        }
        
    models = [eval_model(rf_clf, "RandomForest")]
    if xgb_clf:
        models.append(eval_model(xgb_clf, "XGBoost"))
        
    # Select best model (Prioritize Recall, F1, ROC-AUC, then Latency)
    # Give a slight edge to F1 and Recall
    for m in models:
        m["score"] = m["rec"] * 0.4 + m["f1"] * 0.4 + m["roc_auc"] * 0.2
        print(f"Model: {m['name']} | Acc: {m['acc']:.3f} | Rec: {m['rec']:.3f} | F1: {m['f1']:.3f} | ROC: {m['roc_auc']:.3f} | Latency: {m['latency']:.2f}ms")
        
    best_model_info = sorted(models, key=lambda x: x["score"], reverse=True)[0]
    best_clf = best_model_info["clf"]
    print(f"\n>> Selected Best Model: {best_model_info['name']}")
    
    y_pred = best_model_info["y_pred"]
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    # Feature Importances
    importances = best_clf.feature_importances_
    feat_imp = {feat: float(imp) for feat, imp in zip(feature_cols, importances)}
    top_features = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Save Model
    model_path = "data/risk_model.joblib"
    joblib.dump(best_clf, model_path)
    model_size_kb = os.path.getsize(model_path) / 1024.0
    
    # Save Metrics
    metrics_report = {
        "trained": True,
        "selected_model": best_model_info["name"],
        "total_samples": int(total_samples),
        "train_samples": len(train_idx),
        "test_samples": len(test_idx),
        "unique_scenarios": df["scenario_id"].nunique(),
        "positive_samples": int(positive_samples),
        "negative_samples": int(total_samples - positive_samples),
        "positive_percentage": float(positive_percentage),
        "accuracy": float(best_model_info["acc"]),
        "precision": float(best_model_info["prec"]),
        "recall": float(best_model_info["rec"]),
        "f1": float(best_model_info["f1"]),
        "roc_auc": float(best_model_info["roc_auc"]),
        "latency_ms": float(best_model_info["latency"]),
        "confusion_matrix": cm,
        "model_size_kb": float(model_size_kb),
        "feature_importance": {k: v for k, v in top_features}
    }
    
    with open("data/ai_metrics.json", "w") as f:
        json.dump(metrics_report, f, indent=2)
        
    print(f"Model saved to {model_path} ({model_size_kb:.1f} KB)")

if __name__ == "__main__":
    train_model()
