#!/usr/bin/env python3
"""
Train a TensorFlow/Keras Wide & Deep model on Chicago Taxi data.
Same architecture as the TFX pipeline (taxi_utils.py) but runs standalone.

Outputs:
  api/model/tf_tip_model/       - TF SavedModel
  api/model/model_meta.json     - Training metrics

Usage:
    python3 api/train_tf_model.py
"""

import os
import json
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tfx_pipeline", "data", "simple", "data.csv"
)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
SAVED_MODEL_DIR = os.path.join(MODEL_DIR, "tf_tip_model")
META_PATH = os.path.join(MODEL_DIR, "model_meta.json")

# Feature definitions (matching taxi_utils.py)
DENSE_FLOAT_FEATURES = ["trip_miles", "fare", "trip_seconds"]
CATEGORICAL_FEATURES = ["payment_type", "company"]
BUCKET_FEATURES = ["pickup_latitude", "pickup_longitude", "dropoff_latitude", "dropoff_longitude"]
INT_FEATURES = ["trip_start_hour", "trip_start_day", "trip_start_month",
                "pickup_community_area", "dropoff_community_area"]
LABEL = "tips"
FARE_KEY = "fare"


def load_and_prepare_data():
    print(f"Loading data from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    print(f"  Loaded {len(df)} rows")

    # Clean: ensure numeric columns
    for col in DENSE_FLOAT_FEATURES + BUCKET_FEATURES + [LABEL, FARE_KEY]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in INT_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    df = df.dropna(subset=[LABEL, FARE_KEY])

    # Binary label: tip > 20% of fare (same as TFX pipeline)
    df["big_tipper"] = (df[LABEL] > df[FARE_KEY] * 0.2).astype(int)

    # Encode categoricals
    label_encoders = {}
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            le = LabelEncoder()
            df[col + "_enc"] = le.fit_transform(df[col].astype(str).fillna("Unknown"))
            label_encoders[col] = {cls: int(idx) for idx, cls in enumerate(le.classes_)}

    # Fill NaN
    for col in DENSE_FLOAT_FEATURES + BUCKET_FEATURES:
        df[col] = df[col].fillna(0.0)

    return df, label_encoders


def build_wide_and_deep_model(n_cat_payment, n_cat_company):
    """Build Wide & Deep Keras model matching TFX taxi_utils.py architecture."""

    # Dense float inputs
    inp_trip_miles = tf.keras.layers.Input(shape=(1,), name="trip_miles")
    inp_fare = tf.keras.layers.Input(shape=(1,), name="fare")
    inp_trip_seconds = tf.keras.layers.Input(shape=(1,), name="trip_seconds")

    # Bucket feature inputs
    inp_pickup_lat = tf.keras.layers.Input(shape=(1,), name="pickup_latitude")
    inp_pickup_lon = tf.keras.layers.Input(shape=(1,), name="pickup_longitude")
    inp_dropoff_lat = tf.keras.layers.Input(shape=(1,), name="dropoff_latitude")
    inp_dropoff_lon = tf.keras.layers.Input(shape=(1,), name="dropoff_longitude")

    # Integer feature inputs
    inp_hour = tf.keras.layers.Input(shape=(1,), name="trip_start_hour", dtype="int32")
    inp_day = tf.keras.layers.Input(shape=(1,), name="trip_start_day", dtype="int32")
    inp_month = tf.keras.layers.Input(shape=(1,), name="trip_start_month", dtype="int32")
    inp_pickup_area = tf.keras.layers.Input(shape=(1,), name="pickup_community_area", dtype="int32")
    inp_dropoff_area = tf.keras.layers.Input(shape=(1,), name="dropoff_community_area", dtype="int32")

    # Categorical inputs
    inp_payment = tf.keras.layers.Input(shape=(1,), name="payment_type_enc", dtype="int32")
    inp_company = tf.keras.layers.Input(shape=(1,), name="company_enc", dtype="int32")

    # Deep branch: continuous features
    deep = tf.keras.layers.Concatenate()([
        inp_trip_miles, inp_fare, inp_trip_seconds,
        inp_pickup_lat, inp_pickup_lon, inp_dropoff_lat, inp_dropoff_lon
    ])
    deep = tf.keras.layers.BatchNormalization()(deep)
    for units in [100, 70, 50, 25]:
        deep = tf.keras.layers.Dense(units, activation="relu")(deep)
        deep = tf.keras.layers.Dropout(0.2)(deep)

    # Wide branch: categorical + integer (one-hot / embedding)
    emb_payment = tf.keras.layers.Embedding(n_cat_payment + 1, 8)(inp_payment)
    emb_payment = tf.keras.layers.Flatten()(emb_payment)
    emb_company = tf.keras.layers.Embedding(n_cat_company + 1, 8)(inp_company)
    emb_company = tf.keras.layers.Flatten()(emb_company)

    hour_cast = tf.cast(inp_hour, tf.float32)
    day_cast = tf.cast(inp_day, tf.float32)
    month_cast = tf.cast(inp_month, tf.float32)
    area_p_cast = tf.cast(inp_pickup_area, tf.float32)
    area_d_cast = tf.cast(inp_dropoff_area, tf.float32)

    wide = tf.keras.layers.Concatenate()([
        emb_payment, emb_company,
        hour_cast, day_cast, month_cast, area_p_cast, area_d_cast
    ])

    # Combine
    combined = tf.keras.layers.Concatenate()([deep, wide])
    combined = tf.keras.layers.Dense(32, activation="relu")(combined)
    output = tf.keras.layers.Dense(1, activation="sigmoid", name="output")(combined)

    all_inputs = [
        inp_trip_miles, inp_fare, inp_trip_seconds,
        inp_pickup_lat, inp_pickup_lon, inp_dropoff_lat, inp_dropoff_lon,
        inp_hour, inp_day, inp_month, inp_pickup_area, inp_dropoff_area,
        inp_payment, inp_company,
    ]
    model = tf.keras.Model(inputs=all_inputs, outputs=output)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="binary_crossentropy",
        metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
    )
    return model


def train():
    df, label_encoders = load_and_prepare_data()

    n_cat_payment = max(label_encoders.get("payment_type", {}).values(), default=0) + 1
    n_cat_company = max(label_encoders.get("company", {}).values(), default=0) + 1

    feature_cols_float = DENSE_FLOAT_FEATURES + BUCKET_FEATURES
    feature_cols_int = INT_FEATURES
    feature_cols_cat = [c + "_enc" for c in CATEGORICAL_FEATURES]

    X_float = df[feature_cols_float].values.astype(np.float32)
    X_int = df[feature_cols_int].values.astype(np.int32)
    X_cat = df[feature_cols_cat].values.astype(np.int32)
    y = df["big_tipper"].values.astype(np.float32)

    # Split
    idx_train, idx_test = train_test_split(range(len(y)), test_size=0.2, random_state=42)

    def make_inputs(indices):
        return [
            X_float[indices, 0:1], X_float[indices, 1:2], X_float[indices, 2:3],  # dense
            X_float[indices, 3:4], X_float[indices, 4:5], X_float[indices, 5:6], X_float[indices, 6:7],  # bucket
            X_int[indices, 0:1], X_int[indices, 1:2], X_int[indices, 2:3],  # int
            X_int[indices, 3:4], X_int[indices, 4:5],
            X_cat[indices, 0:1], X_cat[indices, 1:2],  # cat
        ]

    X_train = make_inputs(idx_train)
    X_test = make_inputs(idx_test)
    y_train = y[idx_train]
    y_test = y[idx_test]

    print(f"  Train: {len(y_train)}, Test: {len(y_test)}")
    print(f"  Big tipper rate: {y.mean():.2%}")

    model = build_wide_and_deep_model(n_cat_payment, n_cat_company)
    model.summary()

    print("\nTraining Wide & Deep model ...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=20,
        batch_size=64,
        verbose=1,
    )

    # Final eval
    loss, accuracy, auc = model.evaluate(X_test, y_test, verbose=0)
    print(f"\n  Test Loss:     {loss:.4f}")
    print(f"  Test Accuracy: {accuracy:.4f}")
    print(f"  Test AUC:      {auc:.4f}")

    # Save model
    os.makedirs(MODEL_DIR, exist_ok=True)
    model.save(SAVED_MODEL_DIR)
    print(f"\nSavedModel saved to {SAVED_MODEL_DIR}")

    # Save metadata
    meta = {
        "framework": "tensorflow",
        "tf_version": tf.__version__,
        "model_type": "Wide & Deep (Keras)",
        "architecture": "Dense(100,70,50,25) + Embedding + Sigmoid",
        "task": "binary_classification",
        "label": "big_tipper (tip > 20% of fare)",
        "feature_cols_float": feature_cols_float,
        "feature_cols_int": feature_cols_int,
        "feature_cols_cat": feature_cols_cat,
        "label_encoders": label_encoders,
        "n_cat_payment": n_cat_payment,
        "n_cat_company": n_cat_company,
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "epochs": 20,
        "test_loss": round(float(loss), 4),
        "test_accuracy": round(float(accuracy), 4),
        "test_auc": round(float(auc), 4),
        "big_tipper_rate": round(float(y.mean()), 4),
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Metadata saved to {META_PATH}")

    return meta


if __name__ == "__main__":
    train()
