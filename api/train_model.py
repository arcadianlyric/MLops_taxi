#!/usr/bin/env python3
"""
Train a scikit-learn GradientBoosting model on Chicago Taxi data.
Saves the model as a joblib file for use by taxi_full_api.py.

Usage:
    python api/train_model.py
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder

DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tfx_pipeline", "data", "simple", "data.csv"
)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "tip_model.joblib")
META_PATH = os.path.join(MODEL_DIR, "sklearn_meta.json")

NUMERIC_FEATURES = [
    "fare", "trip_miles", "trip_seconds",
    "pickup_community_area", "dropoff_community_area",
    "trip_start_hour", "trip_start_day", "trip_start_month",
]
CATEGORICAL_FEATURES = ["payment_type", "company"]


def train():
    print(f"Loading data from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    print(f"  Loaded {len(df)} rows")

    # Clean target
    df["tips"] = pd.to_numeric(df["tips"], errors="coerce")
    df = df.dropna(subset=["tips"])
    df = df[df["tips"] >= 0]

    # Prepare features
    for col in NUMERIC_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Encode categoricals
    label_encoders = {}
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            le = LabelEncoder()
            df[col + "_enc"] = le.fit_transform(df[col].astype(str))
            label_encoders[col] = le

    feature_cols = [c for c in NUMERIC_FEATURES if c in df.columns] + \
                   [c + "_enc" for c in CATEGORICAL_FEATURES if c in df.columns]

    X = df[feature_cols].values
    y = df["tips"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

    # Train model
    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        min_samples_leaf=10,
        random_state=42,
    )
    print("Training GradientBoostingRegressor ...")
    model.fit(X_train, y_train)

    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    train_mae = mean_absolute_error(y_train, y_pred_train)
    test_mae = mean_absolute_error(y_test, y_pred_test)
    train_r2 = r2_score(y_train, y_pred_train)
    test_r2 = r2_score(y_test, y_pred_test)

    print(f"  Train MAE: {train_mae:.4f}  R²: {train_r2:.4f}")
    print(f"  Test  MAE: {test_mae:.4f}  R²: {test_r2:.4f}")

    # Feature importances
    importances = dict(zip(feature_cols, model.feature_importances_.tolist()))

    # Save
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"model": model, "label_encoders": label_encoders, "feature_cols": feature_cols}, MODEL_PATH)

    meta = {
        "model_type": "GradientBoostingRegressor",
        "n_estimators": 200,
        "max_depth": 5,
        "feature_cols": feature_cols,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "train_mae": round(train_mae, 4),
        "test_mae": round(test_mae, 4),
        "train_r2": round(train_r2, 4),
        "test_r2": round(test_r2, 4),
        "feature_importances": importances,
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Model saved to {MODEL_PATH}")
    print(f"Metadata saved to {META_PATH}")
    return meta


if __name__ == "__main__":
    train()
