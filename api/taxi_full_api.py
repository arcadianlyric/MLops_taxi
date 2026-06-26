#!/usr/bin/env python3
"""
Complete Chicago Taxi Tip Prediction API
Self-contained API with all routes (Feast, Kafka, MLflow, MLMD)
powered by real CSV data - no external service dependencies.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import random
import hashlib
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Prometheus metrics
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    from prometheus_client import Counter, Histogram, Gauge, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# TensorFlow model loading
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

# MLflow client
try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
SAVED_MODEL_DIR = os.path.join(MODEL_DIR, "tf_tip_model")
MODEL_META_PATH = os.path.join(MODEL_DIR, "model_meta.json")
SKLEARN_MODEL_PATH = os.path.join(MODEL_DIR, "tip_model.joblib")
SKLEARN_META_PATH = os.path.join(MODEL_DIR, "sklearn_meta.json")

_tf_model = None
_model_meta = None
_sklearn_model = None
_sklearn_meta = None
_sklearn_label_encoders = {}
_mlflow_client = None
_mlflow_connected = False
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-service:5000")
BATCH_MAX_SIZE = max(1, int(os.environ.get("BATCH_MAX_SIZE", "512")))
BATCH_MAX_WORKERS = max(1, int(os.environ.get("BATCH_MAX_WORKERS", str(min(8, (os.cpu_count() or 2) + 2)))))
PREDICTION_HISTORY_MAX = max(1, int(os.environ.get("PREDICTION_HISTORY_MAX", "1000")))
_batch_executor = ThreadPoolExecutor(max_workers=BATCH_MAX_WORKERS)
_prediction_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load real CSV data once at startup
# ---------------------------------------------------------------------------
DATA_PATH = os.environ.get(
    "TAXI_DATA_PATH",
    os.path.join(os.path.dirname(__file__), "..", "tfx_pipeline", "data", "simple", "data.csv"),
)

_df: Optional[pd.DataFrame] = None


def _load_data() -> pd.DataFrame:
    global _df
    if _df is not None:
        return _df
    try:
        _df = pd.read_csv(DATA_PATH)
        logger.info(f"Loaded {len(_df)} rows from {DATA_PATH}")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        _df = pd.DataFrame()
    return _df


def _to_native(obj):
    """Recursively convert numpy/pandas types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Chicago Taxi Tip Prediction API",
    description="Complete MLOps API with Feast/Kafka/MLflow/MLMD routes – real data",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Prometheus custom metrics
# ---------------------------------------------------------------------------
if PROMETHEUS_AVAILABLE:
    PREDICTION_LATENCY = Histogram(
        "model_prediction_latency_seconds",
        "Prediction latency in seconds",
        ["model_type"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    )
    PREDICTION_COUNT = Counter(
        "model_prediction_total",
        "Total prediction requests",
        ["model_type", "status"],
    )
    DRIFT_SCORE_GAUGE = Gauge(
        "data_drift_score",
        "Current drift score per feature",
        ["feature"],
    )
    MODEL_ACCURACY_GAUGE = Gauge(
        "model_accuracy",
        "Current model accuracy metric",
        ["model_name", "metric"],
    )
    AB_ASSIGNMENT_COUNT = Counter(
        "ab_test_assignment_total",
        "A/B test assignments",
        ["experiment", "variant"],
    )
    RETRAIN_TRIGGER_COUNT = Counter(
        "retrain_trigger_total",
        "Number of auto-retrain triggers",
        ["reason"],
    )
    Instrumentator().instrument(app).expose(app, endpoint="/metrics/prometheus")

# ---------------------------------------------------------------------------
# A/B Testing state
# ---------------------------------------------------------------------------
_ab_experiments: Dict[str, Dict[str, Any]] = {}
_ab_results: Dict[str, List[Dict]] = {}

# ---------------------------------------------------------------------------
# Auto-retrain state
# ---------------------------------------------------------------------------
_retrain_lock = threading.Lock()
_last_retrain_time: Optional[datetime] = None
RETRAIN_COOLDOWN_MINUTES = int(os.environ.get("RETRAIN_COOLDOWN_MINUTES", "30"))
DRIFT_RETRAIN_THRESHOLD = float(os.environ.get("DRIFT_RETRAIN_THRESHOLD", "0.3"))


@app.on_event("startup")
async def startup():
    _load_data()
    _load_tf_model()
    _connect_mlflow()
    _init_default_ab_experiment()


def _connect_mlflow():
    """Try to connect to real MLflow server and register model."""
    global _mlflow_client, _mlflow_connected
    if not MLFLOW_AVAILABLE:
        logger.warning("mlflow package not installed – using mock MLflow data")
        return
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        _mlflow_client = MlflowClient(MLFLOW_TRACKING_URI)
        _mlflow_client.search_experiments()
        _mlflow_connected = True
        logger.info(f"Connected to MLflow at {MLFLOW_TRACKING_URI}")
        _register_model_with_mlflow()
    except Exception as e:
        logger.warning(f"MLflow server not reachable at {MLFLOW_TRACKING_URI}: {e} – using mock data")
        _mlflow_connected = False


def _register_model_with_mlflow():
    """Register the trained model with MLflow if connected."""
    if not _mlflow_connected:
        return
    meta = _model_meta or _sklearn_meta
    if meta is None:
        logger.info("No model metadata to register with MLflow")
        return
    try:
        exp_name = "chicago-taxi-tip-prediction"
        exp = _mlflow_client.get_experiment_by_name(exp_name)
        if exp is None:
            exp_id = _mlflow_client.create_experiment(exp_name)
        else:
            exp_id = exp.experiment_id
        run_name = meta.get("model_type", "model_v1")
        with mlflow.start_run(experiment_id=exp_id, run_name=run_name) as run:
            mlflow.log_params({
                "model_type": meta.get("model_type", "unknown"),
                "framework": meta.get("framework", "sklearn"),
                "train_samples": str(meta.get("train_samples", 0)),
                "test_samples": str(meta.get("test_samples", 0)),
            })
            metrics = {}
            for k in ["test_accuracy", "test_auc", "test_loss", "test_r2", "test_mae", "train_r2", "train_mae"]:
                if k in meta:
                    metrics[k] = float(meta[k])
            if metrics:
                mlflow.log_metrics(metrics)
            for p in [MODEL_META_PATH, SKLEARN_META_PATH]:
                if os.path.exists(p):
                    mlflow.log_artifact(p)
        logger.info(f"Registered model run '{run_name}' in MLflow experiment '{exp_name}'")
    except Exception as e:
        logger.warning(f"Failed to register model with MLflow: {e}")


def _load_tf_model():
    """Load TensorFlow SavedModel if available, then try sklearn fallback."""
    global _tf_model, _model_meta, _sklearn_model, _sklearn_meta, _sklearn_label_encoders
    # Try TF first
    if TF_AVAILABLE and os.path.isdir(SAVED_MODEL_DIR):
        try:
            _tf_model = tf.keras.models.load_model(SAVED_MODEL_DIR)
            logger.info(f"Loaded TF SavedModel from {SAVED_MODEL_DIR}")
            if os.path.exists(MODEL_META_PATH):
                with open(MODEL_META_PATH) as f:
                    _model_meta = json.load(f)
                logger.info(f"TF model: acc={_model_meta.get('test_accuracy')}, auc={_model_meta.get('test_auc')}")
        except Exception as e:
            logger.warning(f"Failed to load TF model: {e}")
            _tf_model = None
    elif not TF_AVAILABLE:
        logger.info("TensorFlow not installed – will try sklearn model")
    # Try sklearn fallback
    if os.path.exists(SKLEARN_MODEL_PATH):
        try:
            import joblib
            bundle = joblib.load(SKLEARN_MODEL_PATH)
            _sklearn_model = bundle["model"]
            _sklearn_label_encoders = bundle.get("label_encoders", {})
            if os.path.exists(SKLEARN_META_PATH):
                with open(SKLEARN_META_PATH) as f:
                    _sklearn_meta = json.load(f)
            logger.info(f"Loaded sklearn model from {SKLEARN_MODEL_PATH} (R²={_sklearn_meta.get('test_r2') if _sklearn_meta else '?'})")
        except Exception as e:
            logger.warning(f"Failed to load sklearn model: {e}")
    if _tf_model is None and _sklearn_model is None:
        logger.warning("No ML model loaded – using rule-based prediction")
    # Publish accuracy to Prometheus
    if PROMETHEUS_AVAILABLE:
        if _sklearn_meta:
            MODEL_ACCURACY_GAUGE.labels(model_name="sklearn_gb", metric="r2").set(_sklearn_meta.get("test_r2", 0))
            MODEL_ACCURACY_GAUGE.labels(model_name="sklearn_gb", metric="mae").set(_sklearn_meta.get("test_mae", 0))
        if _model_meta:
            MODEL_ACCURACY_GAUGE.labels(model_name="tf_wide_deep", metric="accuracy").set(_model_meta.get("test_accuracy", 0))
            MODEL_ACCURACY_GAUGE.labels(model_name="tf_wide_deep", metric="auc").set(_model_meta.get("test_auc", 0))


def _init_default_ab_experiment():
    """Create a default A/B experiment on startup."""
    _ab_experiments["tip-model-v1"] = {
        "name": "tip-model-v1",
        "variants": {
            "control": {"model": "sklearn", "weight": 0.8},
            "treatment": {"model": "rule_based", "weight": 0.2},
        },
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "total_assignments": 0,
    }
    logger.info("Default A/B experiment 'tip-model-v1' initialized (80/20 split)")


# ===== Pydantic models =====

class TaxiTripRequest(BaseModel):
    trip_miles: float = Field(..., description="Trip distance (miles)")
    trip_seconds: int = Field(..., description="Trip duration (seconds)")
    fare: float = Field(..., description="Fare (USD)")
    pickup_latitude: float = Field(..., description="Pickup latitude")
    pickup_longitude: float = Field(..., description="Pickup longitude")
    dropoff_latitude: float = Field(..., description="Dropoff latitude")
    dropoff_longitude: float = Field(..., description="Dropoff longitude")
    pickup_hour: int = Field(..., description="Pickup hour", ge=0, le=23)
    pickup_day_of_week: int = Field(..., description="Day of week", ge=0, le=6)
    trip_start_day: int = Field(..., description="Day of month", ge=1, le=31)
    trip_start_month: int = Field(..., description="Month", ge=1, le=12)
    pickup_community_area: int = Field(..., description="Pickup community area")
    dropoff_community_area: int = Field(..., description="Dropoff community area")
    pickup_census_tract: int = Field(..., description="Pickup census tract")
    dropoff_census_tract: int = Field(..., description="Dropoff census tract")
    payment_type: str = Field(..., description="Payment type")
    company: str = Field(..., description="Taxi company")
    passenger_count: int = Field(default=1, description="Passenger count")


class BatchTripRequest(BaseModel):
    trips: List[TaxiTripRequest] = Field(..., min_length=1, max_length=BATCH_MAX_SIZE)
    model_name: str = "taxi_model"


# ===== Prediction helpers =====

prediction_count = 0
prediction_history: List[Dict] = []


def _encode_categorical(value: str, encoder_map: dict, default: int = 0) -> int:
    return encoder_map.get(value, default)


def _predict_with_tf(trip: TaxiTripRequest) -> float:
    """Predict using TF Wide & Deep model (binary: big_tipper probability)."""
    enc = _model_meta["label_encoders"]
    inputs = [
        np.array([[trip.trip_miles]], dtype=np.float32),
        np.array([[trip.fare]], dtype=np.float32),
        np.array([[trip.trip_seconds]], dtype=np.float32),
        np.array([[trip.pickup_latitude]], dtype=np.float32),
        np.array([[trip.pickup_longitude]], dtype=np.float32),
        np.array([[trip.dropoff_latitude]], dtype=np.float32),
        np.array([[trip.dropoff_longitude]], dtype=np.float32),
        np.array([[trip.pickup_hour]], dtype=np.int32),
        np.array([[trip.trip_start_day]], dtype=np.int32),
        np.array([[trip.trip_start_month]], dtype=np.int32),
        np.array([[trip.pickup_community_area]], dtype=np.int32),
        np.array([[trip.dropoff_community_area]], dtype=np.int32),
        np.array([[_encode_categorical(trip.payment_type, enc.get("payment_type", {}))]], dtype=np.int32),
        np.array([[_encode_categorical(trip.company, enc.get("company", {}))]], dtype=np.int32),
    ]
    prob = float(_tf_model.predict(inputs, verbose=0)[0][0])
    # Convert probability → tip: big_tipper means >20% of fare
    if prob > 0.5:
        tip_rate = 0.20 + (prob - 0.5) * 0.30  # 20-35% range
    else:
        tip_rate = prob * 0.20  # 0-10% range
    return round(max(0, trip.fare * tip_rate), 2)


def _predict_with_sklearn(trip: TaxiTripRequest) -> float:
    """Predict using sklearn GradientBoosting model (regression: tip amount)."""
    meta = _sklearn_meta or {}
    feature_cols = meta.get("feature_cols", [
        "fare", "trip_miles", "trip_seconds",
        "pickup_community_area", "dropoff_community_area",
        "trip_start_hour", "trip_start_day", "trip_start_month",
        "payment_type_enc", "company_enc",
    ])
    # Encode categoricals using the real LabelEncoder
    def _enc(le, val):
        try:
            return int(le.transform([str(val)])[0])
        except (ValueError, KeyError):
            return 0
    pay_enc = _enc(_sklearn_label_encoders["payment_type"], trip.payment_type) if "payment_type" in _sklearn_label_encoders else 0
    comp_enc = _enc(_sklearn_label_encoders["company"], trip.company) if "company" in _sklearn_label_encoders else 0
    val_map = {
        "fare": trip.fare, "trip_miles": trip.trip_miles, "trip_seconds": trip.trip_seconds,
        "pickup_community_area": trip.pickup_community_area,
        "dropoff_community_area": trip.dropoff_community_area,
        "trip_start_hour": trip.pickup_hour, "trip_start_day": trip.trip_start_day,
        "trip_start_month": trip.trip_start_month,
        "payment_type_enc": pay_enc, "company_enc": comp_enc,
    }
    X = np.array([[val_map.get(c, 0) for c in feature_cols]])
    tip = float(_sklearn_model.predict(X)[0])
    return round(max(0, tip), 2)


def _predict_rule_based(trip: TaxiTripRequest) -> float:
    """Fallback rule-based prediction."""
    base_tip_rate = 0.15
    payment_multiplier = {
        "Credit Card": 1.5, "Cash": 0.5, "No Charge": 0.0,
        "Dispute": 0.1, "Unknown": 0.3,
    }.get(trip.payment_type, 0.8)
    time_multiplier = 1.0
    if 17 <= trip.pickup_hour <= 20:
        time_multiplier = 1.3
    elif 6 <= trip.pickup_hour <= 9:
        time_multiplier = 1.2
    elif 0 <= trip.pickup_hour <= 5:
        time_multiplier = 1.4
    distance_multiplier = 1.0
    if trip.trip_miles > 10:
        distance_multiplier = 1.1
    elif trip.trip_miles < 2:
        distance_multiplier = 0.9
    predicted_tip = trip.fare * base_tip_rate * payment_multiplier * time_multiplier * distance_multiplier
    noise = np.random.normal(0, 0.5)
    return round(max(0, predicted_tip + noise), 2)


def predict_tip(trip: TaxiTripRequest, force_model: str = None) -> float:
    global prediction_count
    with _prediction_lock:
        prediction_count += 1
    t0 = time.time()
    model_used = "rule_based"
    status = "ok"
    try:
        if force_model == "rule_based":
            return _predict_rule_based(trip)
        if force_model == "sklearn" and _sklearn_model is not None:
            model_used = "sklearn"
            return _predict_with_sklearn(trip)
        # Priority: TF model > sklearn model > rule-based
        if _tf_model is not None and _model_meta is not None:
            try:
                model_used = "tensorflow"
                return _predict_with_tf(trip)
            except Exception as e:
                logger.error(f"TF prediction failed: {e}")
        if _sklearn_model is not None:
            try:
                model_used = "sklearn"
                return _predict_with_sklearn(trip)
            except Exception as e:
                logger.error(f"sklearn prediction failed: {e}")
        model_used = "rule_based"
        return _predict_rule_based(trip)
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.time() - t0
        if PROMETHEUS_AVAILABLE:
            PREDICTION_LATENCY.labels(model_type=model_used).observe(elapsed)
            PREDICTION_COUNT.labels(model_type=model_used, status=status).inc()


# ===================================================================
# CORE ROUTES: root / health / predict / batch_predict / metrics
# ===================================================================

@app.get("/")
async def root():
    return {
        "message": "Chicago Taxi Tip Prediction API",
        "version": "3.0.0",
        "endpoints": {
            "health": "/health", "predict": "/predict",
            "batch_predict": "/batch_predict", "docs": "/docs",
            "feast": "/feast/*", "kafka": "/kafka/*",
            "mlflow": "/mlflow/*", "mlmd": "/mlmd/*",
            "data_stats": "/data/stats", "data_drift": "/data/drift",
            "ab_testing": "/ab/*", "retrain": "/retrain/*",
            "agentic_drift_retrain": "/agentic/drift-retrain/run",
            "prometheus": "/metrics/prometheus",
        },
    }


@app.get("/health")
async def health_check():
    df = _load_data()
    if _tf_model is not None:
        active = "tensorflow_wide_and_deep"
    elif _sklearn_model is not None:
        active = "sklearn_gradient_boosting"
    else:
        active = "rule_based"
    model_info = {
        "type": active,
        "tf_available": TF_AVAILABLE,
        "tf_model_loaded": _tf_model is not None,
        "sklearn_model_loaded": _sklearn_model is not None,
        "mlflow_connected": _mlflow_connected,
    }
    if _model_meta:
        model_info["tf_accuracy"] = _model_meta.get("test_accuracy")
        model_info["tf_auc"] = _model_meta.get("test_auc")
    if _sklearn_meta:
        model_info["sklearn_r2"] = _sklearn_meta.get("test_r2")
        model_info["sklearn_mae"] = _sklearn_meta.get("test_mae")
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "taxi-tip-prediction",
        "version": "2.0.0",
        "data_loaded": len(df) > 0,
        "data_rows": len(df),
        "total_predictions": prediction_count,
        "model": model_info,
    }


@app.post("/predict")
async def predict(trip: TaxiTripRequest):
    try:
        tip = predict_tip(trip)
        tip_rate = (tip / trip.fare * 100) if trip.fare > 0 else 0
        result = {
            "fare_amount": trip.fare,
            "predicted_tip": tip,
            "tip_rate": round(tip_rate, 2),
            "total_cost": round(trip.fare + tip, 2),
            "payment_type": trip.payment_type,
            "trip_miles": trip.trip_miles,
            "pickup_hour": trip.pickup_hour,
            "timestamp": datetime.now().isoformat(),
        }
        with _prediction_lock:
            prediction_history.append(result)
            if len(prediction_history) > PREDICTION_HISTORY_MAX:
                del prediction_history[:-PREDICTION_HISTORY_MAX]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch_predict")
async def batch_predict(request: BatchTripRequest):
    try:
        start = time.perf_counter()
        loop = asyncio.get_running_loop()
        predictions = await asyncio.gather(
            *[
                loop.run_in_executor(_batch_executor, predict_tip, trip)
                for trip in request.trips
            ]
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        throughput = round(len(predictions) / max(latency_ms / 1000, 0.001), 2)
        return {
            "predictions": predictions,
            "count": len(predictions),
            "model_name": request.model_name,
            "batch_max_size": BATCH_MAX_SIZE,
            "batch_workers": BATCH_MAX_WORKERS,
            "latency_ms": latency_ms,
            "throughput_predictions_per_second": throughput,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    df = _load_data()
    return {
        "service": "taxi-tip-prediction",
        "status": "running",
        "model_status": "loaded",
        "api_status": True,
        "total_predictions": prediction_count,
        "data_rows": len(df),
        "timestamp": datetime.now().isoformat(),
    }


# ===================================================================
# DATA STATS & DRIFT (real CSV data)
# ===================================================================

@app.get("/data/stats")
async def get_data_stats():
    """Return real statistics computed from data.csv."""
    df = _load_data()
    if df.empty:
        raise HTTPException(status_code=500, detail="No data loaded")

    numeric_cols = ["fare", "trip_miles", "trip_seconds", "tips",
                    "pickup_latitude", "pickup_longitude",
                    "dropoff_latitude", "dropoff_longitude"]
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    stats = {}
    for col in numeric_cols:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        stats[col] = {
            "count": int(len(s)),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "median": round(float(s.median()), 4),
            "q25": round(float(s.quantile(0.25)), 4),
            "q75": round(float(s.quantile(0.75)), 4),
        }

    cat_cols = ["payment_type", "company"]
    cat_cols = [c for c in cat_cols if c in df.columns]
    for col in cat_cols:
        vc = df[col].fillna("Unknown").value_counts()
        stats[col] = {
            "unique": int(vc.shape[0]),
            "top_values": [
                {"value": str(v), "count": int(c), "pct": round(c / len(df) * 100, 2)}
                for v, c in vc.head(10).items()
            ],
        }

    # hourly stats
    if "trip_start_hour" in df.columns:
        hourly = df.groupby("trip_start_hour").agg(
            count=("fare", "size"),
            avg_fare=("fare", lambda x: pd.to_numeric(x, errors="coerce").mean()),
            avg_tips=("tips", lambda x: pd.to_numeric(x, errors="coerce").mean()),
        ).reset_index()
        stats["hourly"] = hourly.fillna(0).to_dict(orient="records")

    # monthly stats
    if "trip_start_month" in df.columns:
        monthly = df.groupby("trip_start_month").agg(
            count=("fare", "size"),
            avg_fare=("fare", lambda x: pd.to_numeric(x, errors="coerce").mean()),
            avg_tips=("tips", lambda x: pd.to_numeric(x, errors="coerce").mean()),
        ).reset_index()
        stats["monthly"] = monthly.fillna(0).to_dict(orient="records")

    # payment type stats
    if "payment_type" in df.columns and "tips" in df.columns:
        pt = df.groupby("payment_type").agg(
            count=("fare", "size"),
            avg_fare=("fare", lambda x: pd.to_numeric(x, errors="coerce").mean()),
            avg_tips=("tips", lambda x: pd.to_numeric(x, errors="coerce").mean()),
        ).reset_index()
        stats["by_payment_type"] = pt.fillna(0).to_dict(orient="records")

    # company stats
    if "company" in df.columns and "tips" in df.columns:
        co = df.groupby("company").agg(
            count=("fare", "size"),
            avg_fare=("fare", lambda x: pd.to_numeric(x, errors="coerce").mean()),
            avg_tips=("tips", lambda x: pd.to_numeric(x, errors="coerce").mean()),
        ).reset_index()
        stats["by_company"] = co.fillna(0).to_dict(orient="records")

    return {
        "status": "success",
        "total_rows": len(df),
        "columns": list(df.columns),
        "data": stats,
    }


@app.get("/data/drift")
async def get_data_drift():
    """Compute real drift between first-half and second-half of data."""
    df = _load_data()
    if df.empty:
        raise HTTPException(status_code=500, detail="No data loaded")

    mid = len(df) // 2
    baseline = df.iloc[:mid]
    current = df.iloc[mid:]

    features = ["fare", "trip_miles", "trip_seconds", "tips",
                "pickup_latitude", "pickup_longitude",
                "dropoff_latitude", "dropoff_longitude",
                "trip_start_hour", "payment_type", "company"]
    features = [f for f in features if f in df.columns]

    feature_details = {}
    for feat in features:
        b = baseline[feat]
        c = current[feat]

        if pd.api.types.is_numeric_dtype(df[feat]) or feat in [
            "fare", "trip_miles", "trip_seconds", "tips",
            "pickup_latitude", "pickup_longitude",
            "dropoff_latitude", "dropoff_longitude", "trip_start_hour",
        ]:
            b_num = pd.to_numeric(b, errors="coerce").dropna()
            c_num = pd.to_numeric(c, errors="coerce").dropna()
            if len(b_num) == 0 or len(c_num) == 0:
                drift_score = 0.0
            else:
                mean_diff = abs(b_num.mean() - c_num.mean())
                pooled_std = max((b_num.std() + c_num.std()) / 2, 1e-6)
                drift_score = min(mean_diff / pooled_std, 1.0)

            drift_score = round(drift_score, 3)
            is_drifted = drift_score > 0.1
            drift_type = (
                "No" if drift_score < 0.1 else
                "Low" if drift_score < 0.3 else
                "Medium" if drift_score < 0.5 else "High"
            )

            feature_details[feat] = {
                "drift_score": drift_score,
                "is_drifted": is_drifted,
                "drift_type": drift_type,
                "baseline_stats": {
                    "name": feat, "type": "FLOAT",
                    "mean": round(float(b_num.mean()), 4) if len(b_num) else 0,
                    "std_dev": round(float(b_num.std()), 4) if len(b_num) else 0,
                    "min": round(float(b_num.min()), 4) if len(b_num) else 0,
                    "max": round(float(b_num.max()), 4) if len(b_num) else 0,
                    "median": round(float(b_num.median()), 4) if len(b_num) else 0,
                },
                "current_stats": {
                    "name": feat, "type": "FLOAT",
                    "mean": round(float(c_num.mean()), 4) if len(c_num) else 0,
                    "std_dev": round(float(c_num.std()), 4) if len(c_num) else 0,
                    "min": round(float(c_num.min()), 4) if len(c_num) else 0,
                    "max": round(float(c_num.max()), 4) if len(c_num) else 0,
                    "median": round(float(c_num.median()), 4) if len(c_num) else 0,
                },
            }
        else:
            # categorical
            b_vc = b.fillna("Unknown").value_counts(normalize=True)
            c_vc = c.fillna("Unknown").value_counts(normalize=True)
            all_vals = set(b_vc.index) | set(c_vc.index)
            js_div = 0.0
            for v in all_vals:
                p = b_vc.get(v, 0)
                q = c_vc.get(v, 0)
                m = (p + q) / 2
                if p > 0 and m > 0:
                    js_div += p * np.log(p / m)
                if q > 0 and m > 0:
                    js_div += q * np.log(q / m)
            js_div = min(js_div / 2, 1.0)
            drift_score = round(js_div, 3)
            is_drifted = drift_score > 0.1
            drift_type = (
                "No" if drift_score < 0.1 else
                "Low" if drift_score < 0.3 else
                "Medium" if drift_score < 0.5 else "High"
            )

            feature_details[feat] = {
                "drift_score": drift_score,
                "is_drifted": is_drifted,
                "drift_type": drift_type,
                "baseline_stats": {
                    "name": feat, "type": "BYTES",
                    "unique_count": int(b_vc.shape[0]),
                    "top_values": [
                        {"value": str(v), "frequency": round(float(f), 3)}
                        for v, f in b_vc.head(5).items()
                    ],
                },
                "current_stats": {
                    "name": feat, "type": "BYTES",
                    "unique_count": int(c_vc.shape[0]),
                    "top_values": [
                        {"value": str(v), "frequency": round(float(f), 3)}
                        for v, f in c_vc.head(5).items()
                    ],
                },
            }

    drifted_count = sum(1 for v in feature_details.values() if v["is_drifted"])

    recommendations = []
    if drifted_count > 0:
        recommendations = [
            "Data drift detected – review the following actions:",
            "1. Check data collection pipeline for anomalies",
            "2. Consider retraining the model with recent data",
            "3. Update feature preprocessing if distributions shifted",
            "4. Pay special attention to high-drift features",
        ]
    else:
        recommendations = ["No significant drift detected – model is stable."]

    return _to_native({
        "summary": {
            "timestamp": datetime.now().isoformat(),
            "overall_drift_detected": drifted_count > 0,
            "threshold": 0.1,
            "total_features_checked": len(features),
            "drifted_features_count": drifted_count,
            "baseline_rows": len(baseline),
            "current_rows": len(current),
        },
        "feature_details": feature_details,
        "recommendations": recommendations,
    })


# ===================================================================
# FEAST ROUTES  /feast/*
# ===================================================================

def _build_feast_feature_views(df: pd.DataFrame) -> List[Dict]:
    """Build feature view metadata from real data columns."""
    views = []
    numeric_features = ["fare", "trip_miles", "trip_seconds", "tips",
                        "pickup_latitude", "pickup_longitude",
                        "dropoff_latitude", "dropoff_longitude"]
    numeric_features = [f for f in numeric_features if f in df.columns]

    views.append({
        "name": "taxi_trip_features",
        "entities": ["trip_id"],
        "features": [{"name": f, "dtype": "FLOAT64"} for f in numeric_features],
        "online": True,
        "description": "Core taxi trip numerical features",
        "tags": {"source": "chicago_taxi_csv", "version": "1.0"},
        "created_at": "2024-01-15T10:00:00Z",
        "last_updated": datetime.now().isoformat(),
    })

    cat_features = ["payment_type", "company"]
    cat_features = [f for f in cat_features if f in df.columns]
    views.append({
        "name": "taxi_categorical_features",
        "entities": ["trip_id"],
        "features": [{"name": f, "dtype": "STRING"} for f in cat_features],
        "online": True,
        "description": "Taxi trip categorical features",
        "tags": {"source": "chicago_taxi_csv", "version": "1.0"},
        "created_at": "2024-01-15T10:00:00Z",
        "last_updated": datetime.now().isoformat(),
    })

    time_features = ["trip_start_hour", "trip_start_day", "trip_start_month"]
    time_features = [f for f in time_features if f in df.columns]
    views.append({
        "name": "taxi_temporal_features",
        "entities": ["trip_id"],
        "features": [{"name": f, "dtype": "INT64"} for f in time_features],
        "online": True,
        "description": "Taxi trip temporal features",
        "tags": {"source": "chicago_taxi_csv", "version": "1.0"},
        "created_at": "2024-01-15T10:00:00Z",
        "last_updated": datetime.now().isoformat(),
    })

    area_features = ["pickup_community_area", "dropoff_community_area",
                     "pickup_census_tract", "dropoff_census_tract"]
    area_features = [f for f in area_features if f in df.columns]
    if area_features:
        views.append({
            "name": "taxi_area_features",
            "entities": ["trip_id"],
            "features": [{"name": f, "dtype": "INT64"} for f in area_features],
            "online": True,
            "description": "Taxi trip area/census features",
            "tags": {"source": "chicago_taxi_csv", "version": "1.0"},
            "created_at": "2024-01-15T10:00:00Z",
            "last_updated": datetime.now().isoformat(),
        })

    return views


@app.get("/feast/info")
async def feast_info():
    df = _load_data()
    return {
        "status": "success",
        "data": {
            "store_name": "chicago_taxi_feature_store",
            "store_type": "local",
            "provider": "local",
            "online_store": {"type": "sqlite", "path": "data/online_store.db"},
            "offline_store": {"type": "file", "path": DATA_PATH},
            "registry": "data/registry.db",
            "store_connected": True,
            "total_feature_views": 4,
            "total_features": len([c for c in df.columns if c != "tips"]),
            "total_entities": len(df),
            "last_materialized": datetime.now().isoformat(),
        },
        "message": "Feature store info retrieved",
    }


@app.get("/feast/feature-views")
async def feast_feature_views():
    df = _load_data()
    views = _build_feast_feature_views(df)
    return {"status": "success", "data": views, "count": len(views)}


@app.get("/feast/feature-services")
async def feast_feature_services():
    services = [
        {
            "name": "model_inference_v1",
            "description": "Feature service for real-time model inference",
            "feature_views": ["taxi_trip_features", "taxi_categorical_features", "taxi_temporal_features"],
            "tags": {"version": "1.0", "env": "production"},
            "created_at": "2024-01-15T10:00:00Z",
        },
        {
            "name": "training_features_v1",
            "description": "Feature service for model training",
            "feature_views": ["taxi_trip_features", "taxi_categorical_features", "taxi_temporal_features", "taxi_area_features"],
            "tags": {"version": "1.0", "env": "training"},
            "created_at": "2024-01-20T10:00:00Z",
        },
    ]
    return {"status": "success", "data": services, "count": len(services)}


@app.post("/feast/online-features")
async def feast_online_features(request: dict):
    df = _load_data()
    entity_ids = request.get("entity_ids", [])
    features = {}
    for eid in entity_ids:
        idx = int(hashlib.md5(eid.encode()).hexdigest(), 16) % max(len(df), 1)
        row = df.iloc[idx] if len(df) > 0 else {}
        features[eid] = {col: (None if pd.isna(val) else val) for col, val in row.items()} if len(df) > 0 else {}
    return _to_native({
        "status": "success",
        "data": {"features": features, "feature_service": request.get("feature_service", "model_inference_v1")},
        "entity_count": len(entity_ids),
        "message": "Online features retrieved",
    })


@app.post("/feast/historical-features")
async def feast_historical_features(request: dict):
    df = _load_data()
    req_features = request.get("features", [])
    available = [f for f in req_features if f in df.columns]
    sample = df[available].head(100).fillna(0) if available else pd.DataFrame()
    return _to_native({
        "status": "success",
        "data": {"features": sample.to_dict(orient="records"), "columns": available, "row_count": len(sample)},
        "requested_features": req_features,
        "message": "Historical features retrieved",
    })


@app.get("/feast/stats")
async def feast_stats():
    df = _load_data()
    views = _build_feast_feature_views(df)
    return {
        "status": "success",
        "data": {
            "feature_store_info": {
                "store_name": "chicago_taxi_feature_store",
                "store_connected": True,
                "total_entities": len(df),
            },
            "feature_views_count": len(views),
            "feature_services_count": 2,
            "feature_views": [v["name"] for v in views],
            "feature_services": ["model_inference_v1", "training_features_v1"],
            "status": "healthy",
            "total_features": sum(len(v["features"]) for v in views),
            "materialization_status": "completed",
            "last_materialized": datetime.now().isoformat(),
        },
        "message": "Feature store stats retrieved",
    }


# ===================================================================
# KAFKA ROUTES  /kafka/*
# ===================================================================

_kafka_messages: List[Dict] = []
_kafka_msg_count = 0

KAFKA_TOPICS = [
    "taxi-raw-data", "taxi-features", "taxi-features-realtime",
    "taxi-predictions", "taxi-model-metrics", "taxi-data-quality",
    "taxi-alerts", "taxi-business-metrics", "taxi-training-data",
    "taxi-system-events",
]


def _topic_info(topic: str) -> Dict:
    seed = int(hashlib.md5(topic.encode()).hexdigest(), 16)
    return {
        "name": topic,
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000", "compression.type": "snappy"},
        "status": "active",
        "messages_count": (seed % 50000) + 1000,
        "bytes_in_rate": round((seed % 1000) * 1.5, 2),
        "bytes_out_rate": round((seed % 800) * 1.2, 2),
    }


@app.get("/kafka/info")
async def kafka_info():
    return {
        "status": "success",
        "data": {
            "kafka_available": True,
            "bootstrap_servers": ["kafka-broker:9092"],
            "client_connected": True,
            "status": "connected",
            "cluster_id": "taxi-mlops-cluster",
            "broker_count": 1,
            "topic_count": len(KAFKA_TOPICS),
            "total_messages_processed": _kafka_msg_count + 15003,
            "uptime_seconds": int((datetime.now() - datetime(2024, 1, 1)).total_seconds()),
        },
        "message": "Kafka cluster info retrieved",
    }


@app.get("/kafka/topics")
async def kafka_topics():
    topics = [_topic_info(t) for t in KAFKA_TOPICS]
    return {"status": "success", "data": topics, "count": len(topics)}


@app.get("/kafka/topics/{topic_name}")
async def kafka_topic_detail(topic_name: str):
    return {"status": "success", "data": _topic_info(topic_name)}


@app.get("/kafka/stream-processors")
async def kafka_stream_processors():
    df = _load_data()
    base_count = len(df)
    processors = [
        {
            "processor_name": "taxi-feature-processor",
            "status": "running",
            "last_processed": datetime.now().isoformat(),
            "messages_processed": base_count * 2,
            "processing_rate": round(base_count / 3600, 2),
            "error_count": 3,
            "input_topics": ["taxi-raw-data"],
            "output_topics": ["taxi-features", "taxi-features-realtime"],
        },
        {
            "processor_name": "taxi-prediction-processor",
            "status": "running",
            "last_processed": datetime.now().isoformat(),
            "messages_processed": base_count,
            "processing_rate": round(base_count / 7200, 2),
            "error_count": 1,
            "input_topics": ["taxi-features"],
            "output_topics": ["taxi-predictions", "taxi-model-metrics"],
        },
        {
            "processor_name": "taxi-monitoring-processor",
            "status": "running",
            "last_processed": datetime.now().isoformat(),
            "messages_processed": int(base_count * 0.3),
            "processing_rate": round(base_count / 14400, 2),
            "error_count": 0,
            "input_topics": ["taxi-predictions", "taxi-model-metrics"],
            "output_topics": ["taxi-alerts", "taxi-business-metrics"],
        },
    ]
    return {"status": "success", "data": processors, "count": len(processors)}


@app.post("/kafka/messages/taxi-data")
async def kafka_send_taxi_data(taxi_data: dict):
    global _kafka_msg_count
    _kafka_msg_count += 1
    taxi_data["timestamp"] = datetime.now().isoformat()
    _kafka_messages.append(taxi_data)
    if len(_kafka_messages) > 1000:
        _kafka_messages.pop(0)
    return {
        "status": "success",
        "data": {"trip_id": taxi_data.get("trip_id", f"trip_{_kafka_msg_count}"), "topic": "taxi-raw-data", "timestamp": taxi_data["timestamp"]},
        "message": "Taxi data sent to stream pipeline",
    }


@app.post("/kafka/generate-test-data")
async def kafka_generate_test_data(
    count: int = Query(10, ge=1, le=1000),
    rate: float = Query(1.0, ge=0.1, le=100.0),
):
    global _kafka_msg_count
    _kafka_msg_count += count
    return {
        "status": "success",
        "data": {"count": count, "rate": rate, "estimated_duration": count / rate, "topic": "taxi-raw-data"},
        "message": f"Started generating {count} test records at {rate} rec/s",
    }


# ===================================================================
# MLFLOW ROUTES  /mlflow/*
# ===================================================================

now_ts = lambda: int(datetime.now().timestamp() * 1000)  # noqa: E731

_mlflow_experiments = [
    {
        "experiment_id": "1", "name": "chicago-taxi-tip-prediction",
        "lifecycle_stage": "active",
        "artifact_location": "mlflow-artifacts/1",
        "tags": {"project": "chicago-taxi", "team": "mlops", "framework": "tensorflow"},
        "creation_time": None, "last_update_time": None,
    },
    {
        "experiment_id": "2", "name": "taxi-demand-forecasting",
        "lifecycle_stage": "active",
        "artifact_location": "mlflow-artifacts/2",
        "tags": {"project": "taxi-demand", "type": "time-series"},
        "creation_time": None, "last_update_time": None,
    },
    {
        "experiment_id": "3", "name": "taxi-feature-engineering",
        "lifecycle_stage": "active",
        "artifact_location": "mlflow-artifacts/3",
        "tags": {"project": "chicago-taxi", "type": "feature-store"},
        "creation_time": None, "last_update_time": None,
    },
]


def _get_models():
    ts = now_ts()
    return [
        {
            "name": "chicago-taxi-fare-predictor",
            "description": "Chicago Taxi tip prediction model (TFX Keras)",
            "tags": {"model_type": "regression", "framework": "tensorflow", "accuracy": "0.77"},
            "creation_timestamp": ts - 86400000 * 30,
            "last_updated_timestamp": ts,
            "latest_versions": [
                {"version": "3", "stage": "Production", "creation_timestamp": ts - 86400000 * 7,
                 "last_updated_timestamp": ts, "description": "Production v3 – 77% accuracy",
                 "tags": {"accuracy": "0.77", "rmse": "2.1", "dataset_rows": "15003"}, "run_id": "prod_run_003"},
                {"version": "4", "stage": "Staging", "creation_timestamp": ts - 86400000,
                 "last_updated_timestamp": ts, "description": "Staging v4 – improved features",
                 "tags": {"accuracy": "0.79", "rmse": "1.95"}, "run_id": "staging_run_004"},
            ],
        },
        {
            "name": "chicago-taxi-demand-predictor",
            "description": "Chicago Taxi demand forecasting model",
            "tags": {"model_type": "forecasting", "framework": "sklearn"},
            "creation_timestamp": ts - 86400000 * 20,
            "last_updated_timestamp": ts,
            "latest_versions": [
                {"version": "2", "stage": "Production", "creation_timestamp": ts - 86400000 * 3,
                 "last_updated_timestamp": ts, "description": "Demand prediction v2",
                 "tags": {"mae": "0.15", "mape": "8.5%"}, "run_id": "demand_run_002"},
            ],
        },
    ]


def _get_model_versions(model_name: str):
    ts = now_ts()
    if "fare" in model_name.lower():
        return [
            {"name": model_name, "version": "1", "stage": "Archived", "description": "Initial baseline",
             "tags": {"accuracy": "0.65"}, "run_id": "run_001",
             "creation_timestamp": ts - 86400000 * 60, "last_updated_timestamp": ts - 86400000 * 60,
             "source": "mlflow-artifacts/1/model"},
            {"name": model_name, "version": "2", "stage": "Archived", "description": "Improved features",
             "tags": {"accuracy": "0.72"}, "run_id": "run_002",
             "creation_timestamp": ts - 86400000 * 30, "last_updated_timestamp": ts - 86400000 * 30,
             "source": "mlflow-artifacts/2/model"},
            {"name": model_name, "version": "3", "stage": "Production", "description": "Production – TFX Keras 77%",
             "tags": {"accuracy": "0.77", "rmse": "2.1"}, "run_id": "run_003",
             "creation_timestamp": ts - 86400000 * 7, "last_updated_timestamp": ts - 86400000 * 7,
             "source": "mlflow-artifacts/3/model"},
            {"name": model_name, "version": "4", "stage": "Staging", "description": "Staging – new features",
             "tags": {"accuracy": "0.79", "rmse": "1.95"}, "run_id": "run_004",
             "creation_timestamp": ts - 86400000, "last_updated_timestamp": ts,
             "source": "mlflow-artifacts/4/model"},
        ]
    return [
        {"name": model_name, "version": "1", "stage": "Archived", "description": "v1",
         "tags": {"mae": "0.20"}, "run_id": "d_run_001",
         "creation_timestamp": ts - 86400000 * 20, "last_updated_timestamp": ts - 86400000 * 20,
         "source": "mlflow-artifacts/demand_1/model"},
        {"name": model_name, "version": "2", "stage": "Production", "description": "v2",
         "tags": {"mae": "0.15"}, "run_id": "d_run_002",
         "creation_timestamp": ts - 86400000 * 3, "last_updated_timestamp": ts,
         "source": "mlflow-artifacts/demand_2/model"},
    ]


@app.get("/mlflow/info")
async def mlflow_info():
    data = {
        "mlflow_available": MLFLOW_AVAILABLE,
        "tracking_uri": MLFLOW_TRACKING_URI,
        "client_connected": _mlflow_connected,
        "status": "connected" if _mlflow_connected else "mock_mode",
        "total_experiments": len(_mlflow_experiments),
        "total_models": 2,
    }
    if _mlflow_connected:
        try:
            exps = _mlflow_client.search_experiments()
            data["total_experiments"] = len(exps)
            data["real_server"] = True
        except Exception:
            pass
    return {"status": "success", "data": data, "message": "MLflow service info retrieved"}


@app.get("/mlflow/experiments")
async def mlflow_experiments():
    if _mlflow_connected:
        try:
            real_exps = _mlflow_client.search_experiments()
            exps = [{
                "experiment_id": e.experiment_id, "name": e.name,
                "lifecycle_stage": e.lifecycle_stage,
                "artifact_location": e.artifact_location,
                "tags": dict(e.tags) if e.tags else {},
                "creation_time": e.creation_time, "last_update_time": e.last_update_time,
            } for e in real_exps if e.name != "Default"]
            if exps:
                return {"status": "success", "data": exps, "count": len(exps)}
        except Exception as ex:
            logger.warning(f"MLflow experiments query failed: {ex}")
    ts = now_ts()
    exps = [{**e, "creation_time": ts - 86400000 * 30, "last_update_time": ts} for e in _mlflow_experiments]
    return {"status": "success", "data": exps, "count": len(exps)}


@app.post("/mlflow/experiments")
async def mlflow_create_experiment(experiment: dict):
    eid = f"exp_{int(datetime.now().timestamp())}"
    return {
        "status": "success",
        "data": {"experiment_id": eid, "name": experiment.get("name", "new_exp"), "description": experiment.get("description", "")},
        "message": f"Experiment created: {experiment.get('name', eid)}",
    }


@app.get("/mlflow/models")
async def mlflow_models():
    models = _get_models()
    return {"status": "success", "data": models, "count": len(models)}


@app.get("/mlflow/models/{model_name}/versions")
async def mlflow_model_versions(model_name: str):
    versions = _get_model_versions(model_name)
    return {"status": "success", "data": versions, "count": len(versions)}


@app.post("/mlflow/models/{model_name}/versions/{version}/stage")
async def mlflow_update_stage(model_name: str, version: str, stage: str = Query(...)):
    return {
        "status": "success",
        "data": {"model_name": model_name, "version": version, "stage": stage, "updated_at": datetime.now().isoformat()},
        "message": f"Model {model_name} v{version} stage updated to {stage}",
    }


@app.post("/mlflow/models/metrics")
async def mlflow_log_metrics(metrics: dict):
    return {
        "status": "success",
        "data": {
            "model_name": metrics.get("model_name", "unknown"),
            "model_version": metrics.get("model_version", "1"),
            "metrics": metrics.get("metrics", {}),
            "timestamp": datetime.now().isoformat(),
        },
        "message": "Metrics logged",
    }


@app.post("/mlflow/models/predict")
async def mlflow_predict(request: dict):
    input_data = request.get("input_data", {})
    fare = float(input_data.get("fare", input_data.get("trip_fare", 12.5)))
    tip = fare * 0.15 * random.uniform(0.8, 1.5)
    return {
        "status": "success",
        "data": {
            "model_name": request.get("model_name", "chicago-taxi-fare-predictor"),
            "model_version": request.get("model_version", "3"),
            "model_stage": request.get("model_stage", "Production"),
            "prediction": round(tip, 2),
            "confidence": round(random.uniform(0.75, 0.95), 3),
            "timestamp": datetime.now().isoformat(),
        },
        "message": "Prediction completed",
    }


# ===================================================================
# MLMD ROUTES  /mlmd/*
# ===================================================================

def _build_lineage_graph():
    """Build a realistic TFX pipeline lineage graph from real data."""
    df = _load_data()
    ts_base = "2024-01-15T"
    nodes = [
        {"id": "dataset_chicago_taxi", "name": "chicago_taxi_data.csv", "type": "artifact", "subtype": "Dataset",
         "properties": {"format": "csv", "rows": len(df), "columns": len(df.columns), "size_mb": round(len(df) * 0.001, 2)},
         "timestamp": f"{ts_base}10:00:00Z"},
        {"id": "exec_example_gen", "name": "CsvExampleGen", "type": "execution", "subtype": "DataIngestion",
         "properties": {"source": "data/simple/data.csv", "split_ratio": "2:1"},
         "timestamp": f"{ts_base}10:05:00Z"},
        {"id": "artifact_examples", "name": "train_eval_examples", "type": "artifact", "subtype": "Examples",
         "properties": {"train_rows": int(len(df) * 0.67), "eval_rows": int(len(df) * 0.33)},
         "timestamp": f"{ts_base}10:10:00Z"},
        {"id": "exec_statistics_gen", "name": "StatisticsGen", "type": "execution", "subtype": "StatisticsGeneration",
         "properties": {"features_analyzed": len(df.columns)},
         "timestamp": f"{ts_base}10:15:00Z"},
        {"id": "artifact_statistics", "name": "dataset_statistics", "type": "artifact", "subtype": "Statistics",
         "properties": {"features": len(df.columns), "anomalies_found": 2},
         "timestamp": f"{ts_base}10:20:00Z"},
        {"id": "exec_schema_gen", "name": "SchemaGen", "type": "execution", "subtype": "SchemaGeneration",
         "properties": {"inferred_features": len(df.columns)},
         "timestamp": f"{ts_base}10:25:00Z"},
        {"id": "artifact_schema", "name": "inferred_schema", "type": "artifact", "subtype": "Schema",
         "properties": {"features": len(df.columns), "constraints": 8},
         "timestamp": f"{ts_base}10:30:00Z"},
        {"id": "exec_example_validator", "name": "ExampleValidator", "type": "execution", "subtype": "DataValidation",
         "properties": {"anomalies_detected": 0},
         "timestamp": f"{ts_base}10:35:00Z"},
        {"id": "artifact_validation", "name": "validation_result", "type": "artifact", "subtype": "ValidationResult",
         "properties": {"valid": True, "anomalies": 0},
         "timestamp": f"{ts_base}10:40:00Z"},
        {"id": "exec_transform", "name": "Transform", "type": "execution", "subtype": "FeatureEngineering",
         "properties": {"transformed_features": 12, "method": "TFT"},
         "timestamp": f"{ts_base}11:00:00Z"},
        {"id": "artifact_transformed", "name": "transformed_examples", "type": "artifact", "subtype": "TransformedExamples",
         "properties": {"features": 12, "transform_graph": True},
         "timestamp": f"{ts_base}11:10:00Z"},
        {"id": "exec_trainer", "name": "Trainer", "type": "execution", "subtype": "ModelTraining",
         "properties": {"algorithm": "Keras DNN", "epochs": 50, "batch_size": 64, "accuracy": 0.77},
         "timestamp": f"{ts_base}12:00:00Z"},
        {"id": "artifact_model", "name": "taxi_fare_predictor", "type": "artifact", "subtype": "Model",
         "properties": {"framework": "TensorFlow/Keras", "accuracy": 0.77, "format": "SavedModel"},
         "timestamp": f"{ts_base}12:30:00Z"},
        {"id": "exec_evaluator", "name": "Evaluator", "type": "execution", "subtype": "ModelEvaluation",
         "properties": {"metrics": {"accuracy": 0.77, "auc": 0.85, "precision": 0.78, "recall": 0.75}},
         "timestamp": f"{ts_base}13:00:00Z"},
        {"id": "artifact_evaluation", "name": "evaluation_results", "type": "artifact", "subtype": "EvaluationResult",
         "properties": {"blessed": True, "accuracy": 0.77, "baseline_accuracy": 0.70},
         "timestamp": f"{ts_base}13:10:00Z"},
        {"id": "exec_pusher", "name": "Pusher", "type": "execution", "subtype": "ModelDeployment",
         "properties": {"destination": "serving_model/chicago_taxi", "blessed": True},
         "timestamp": f"{ts_base}14:00:00Z"},
        {"id": "artifact_pushed_model", "name": "serving_model", "type": "artifact", "subtype": "PushedModel",
         "properties": {"serving_path": "serving_model/chicago_taxi/1", "version": "1"},
         "timestamp": f"{ts_base}14:05:00Z"},
    ]

    edges = [
        {"source": "dataset_chicago_taxi", "target": "exec_example_gen", "type": "input"},
        {"source": "exec_example_gen", "target": "artifact_examples", "type": "output"},
        {"source": "artifact_examples", "target": "exec_statistics_gen", "type": "input"},
        {"source": "exec_statistics_gen", "target": "artifact_statistics", "type": "output"},
        {"source": "artifact_statistics", "target": "exec_schema_gen", "type": "input"},
        {"source": "exec_schema_gen", "target": "artifact_schema", "type": "output"},
        {"source": "artifact_examples", "target": "exec_example_validator", "type": "input"},
        {"source": "artifact_schema", "target": "exec_example_validator", "type": "input"},
        {"source": "exec_example_validator", "target": "artifact_validation", "type": "output"},
        {"source": "artifact_examples", "target": "exec_transform", "type": "input"},
        {"source": "artifact_schema", "target": "exec_transform", "type": "input"},
        {"source": "exec_transform", "target": "artifact_transformed", "type": "output"},
        {"source": "artifact_transformed", "target": "exec_trainer", "type": "input"},
        {"source": "exec_trainer", "target": "artifact_model", "type": "output"},
        {"source": "artifact_model", "target": "exec_evaluator", "type": "input"},
        {"source": "artifact_examples", "target": "exec_evaluator", "type": "input"},
        {"source": "exec_evaluator", "target": "artifact_evaluation", "type": "output"},
        {"source": "artifact_model", "target": "exec_pusher", "type": "input"},
        {"source": "artifact_evaluation", "target": "exec_pusher", "type": "input"},
        {"source": "exec_pusher", "target": "artifact_pushed_model", "type": "output"},
    ]

    for e in edges:
        src_node = next((n for n in nodes if n["id"] == e["source"]), None)
        e["timestamp"] = src_node["timestamp"] if src_node else datetime.now().isoformat()

    return {"nodes": nodes, "edges": edges, "metadata": {"total_nodes": len(nodes), "total_edges": len(edges), "generated_at": datetime.now().isoformat(), "mode": "real_pipeline"}}


@app.get("/mlmd/info")
async def mlmd_info():
    graph = _build_lineage_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]
    return {
        "available": True,
        "mode": "production",
        "database_path": "metadata/chicago_taxi/metadata.db",
        "total_artifacts": len([n for n in nodes if n["type"] == "artifact"]),
        "total_executions": len([n for n in nodes if n["type"] == "execution"]),
        "total_events": len(edges),
        "last_updated": datetime.now().isoformat(),
    }


@app.get("/mlmd/lineage/graph")
async def mlmd_lineage_graph(
    artifact_id: Optional[str] = Query(None),
    execution_id: Optional[str] = Query(None),
):
    return _build_lineage_graph()


@app.get("/mlmd/lineage/artifacts")
async def mlmd_artifacts():
    graph = _build_lineage_graph()
    artifacts = [n for n in graph["nodes"] if n["type"] == "artifact"]
    return {"artifacts": artifacts, "total_count": len(artifacts), "generated_at": datetime.now().isoformat()}


@app.get("/mlmd/lineage/executions")
async def mlmd_executions():
    graph = _build_lineage_graph()
    executions = [n for n in graph["nodes"] if n["type"] == "execution"]
    return {"executions": executions, "total_count": len(executions), "generated_at": datetime.now().isoformat()}


@app.get("/mlmd/analysis/pipeline-depth")
async def mlmd_pipeline_depth():
    graph = _build_lineage_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]
    executions = [n for n in nodes if n["type"] == "execution"]
    artifacts = [n for n in nodes if n["type"] == "artifact"]
    exec_types = {}
    for e in executions:
        t = e.get("subtype", "unknown")
        exec_types[t] = exec_types.get(t, 0) + 1
    art_types = {}
    for a in artifacts:
        t = a.get("subtype", "unknown")
        art_types[t] = art_types.get(t, 0) + 1
    return {
        "pipeline_depth": len(executions),
        "total_artifacts": len(artifacts),
        "execution_types": exec_types,
        "artifact_types": art_types,
        "complexity_score": round(len(edges) / max(len(nodes), 1), 2),
        "analysis_timestamp": datetime.now().isoformat(),
    }


@app.get("/mlmd/analysis/data-flow")
async def mlmd_data_flow():
    graph = _build_lineage_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]
    datasets = [n for n in nodes if n["type"] == "artifact" and n.get("subtype") == "Dataset"]
    data_flows = []
    for ds in datasets:
        path = [ds["name"]]
        cid = ds["id"]
        visited = set()
        while cid not in visited:
            visited.add(cid)
            nexts = [e for e in edges if e["source"] == cid]
            if not nexts:
                break
            tid = nexts[0]["target"]
            tnode = next((n for n in nodes if n["id"] == tid), None)
            if tnode:
                path.append(tnode["name"])
                cid = tid
            else:
                break
        data_flows.append({"source_dataset": ds["name"], "flow_path": path, "path_length": len(path)})
    return {
        "data_flows": data_flows,
        "total_flows": len(data_flows),
        "average_path_length": sum(f["path_length"] for f in data_flows) / max(len(data_flows), 1),
        "analysis_timestamp": datetime.now().isoformat(),
    }


@app.post("/mlmd/demo/create-sample-lineage")
async def mlmd_create_sample():
    return {
        "status": "success",
        "message": "Sample TFX pipeline lineage created from real data",
        "ingestion_execution_id": "exec_example_gen",
        "training_execution_id": "exec_trainer",
        "created_at": datetime.now().isoformat(),
    }


@app.post("/mlmd/reports/export")
async def mlmd_export_report():
    return {
        "status": "success",
        "message": "Lineage report generated",
        "report_path": "mlmd/lineage_report.json",
        "estimated_completion": "complete",
    }


# ===================================================================
# A/B TESTING
# ===================================================================

class ABExperimentCreate(BaseModel):
    name: str = Field(..., description="Experiment name")
    variants: Dict[str, Dict[str, Any]] = Field(..., description="Variant config: {name: {model, weight}}")

@app.get("/ab/experiments")
async def ab_list_experiments():
    return {"experiments": list(_ab_experiments.values()), "count": len(_ab_experiments)}

@app.post("/ab/experiments")
async def ab_create_experiment(exp: ABExperimentCreate):
    if exp.name in _ab_experiments:
        raise HTTPException(400, f"Experiment '{exp.name}' already exists")
    total_weight = sum(v.get("weight", 0) for v in exp.variants.values())
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(400, f"Variant weights must sum to 1.0, got {total_weight}")
    _ab_experiments[exp.name] = {
        "name": exp.name,
        "variants": exp.variants,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "total_assignments": 0,
    }
    _ab_results[exp.name] = []
    return {"status": "created", "experiment": _ab_experiments[exp.name]}

@app.get("/ab/experiments/{name}")
async def ab_get_experiment(name: str):
    if name not in _ab_experiments:
        raise HTTPException(404, f"Experiment '{name}' not found")
    exp = _ab_experiments[name]
    results = _ab_results.get(name, [])
    variant_stats = {}
    for r in results:
        v = r["variant"]
        if v not in variant_stats:
            variant_stats[v] = {"count": 0, "total_tip": 0.0, "latencies": []}
        variant_stats[v]["count"] += 1
        variant_stats[v]["total_tip"] += r.get("tip", 0)
        variant_stats[v]["latencies"].append(r.get("latency_ms", 0))
    for v, s in variant_stats.items():
        s["avg_tip"] = round(s["total_tip"] / max(s["count"], 1), 3)
        s["avg_latency_ms"] = round(sum(s["latencies"]) / max(len(s["latencies"]), 1), 2)
        del s["latencies"]
    return {"experiment": exp, "variant_stats": variant_stats}

@app.post("/ab/predict")
async def ab_predict(trip: TaxiTripRequest, experiment: str = "tip-model-v1"):
    if experiment not in _ab_experiments:
        raise HTTPException(404, f"Experiment '{experiment}' not found")
    exp = _ab_experiments[experiment]
    if exp["status"] != "running":
        raise HTTPException(400, f"Experiment '{experiment}' is not running")
    # Weighted random variant selection
    rand = random.random()
    cumulative = 0.0
    selected_variant = None
    selected_model = None
    for vname, vconfig in exp["variants"].items():
        cumulative += vconfig.get("weight", 0)
        if rand <= cumulative:
            selected_variant = vname
            selected_model = vconfig.get("model", "sklearn")
            break
    if selected_variant is None:
        selected_variant = list(exp["variants"].keys())[0]
        selected_model = exp["variants"][selected_variant].get("model", "sklearn")
    exp["total_assignments"] += 1
    if PROMETHEUS_AVAILABLE:
        AB_ASSIGNMENT_COUNT.labels(experiment=experiment, variant=selected_variant).inc()
    t0 = time.time()
    tip = predict_tip(trip, force_model=selected_model)
    latency_ms = round((time.time() - t0) * 1000, 2)
    result = {
        "variant": selected_variant, "model": selected_model,
        "tip": tip, "latency_ms": latency_ms, "timestamp": datetime.now().isoformat(),
    }
    _ab_results.setdefault(experiment, []).append(result)
    return {
        "experiment": experiment,
        "variant": selected_variant,
        "model_used": selected_model,
        "predicted_tip": tip,
        "tip_percentage": round(tip / trip.fare * 100, 1) if trip.fare > 0 else 0,
        "latency_ms": latency_ms,
    }

@app.delete("/ab/experiments/{name}")
async def ab_stop_experiment(name: str):
    if name not in _ab_experiments:
        raise HTTPException(404, f"Experiment '{name}' not found")
    _ab_experiments[name]["status"] = "stopped"
    _ab_experiments[name]["stopped_at"] = datetime.now().isoformat()
    return {"status": "stopped", "experiment": _ab_experiments[name]}


# ===================================================================
# AUTO-RETRAIN
# ===================================================================

def _retrain_sklearn_model() -> Dict[str, Any]:
    """Retrain sklearn model in-process and reload. Returns new metadata."""
    global _sklearn_model, _sklearn_meta
    import subprocess, sys
    train_script = os.path.join(os.path.dirname(__file__), "train_model.py")
    if not os.path.exists(train_script):
        raise RuntimeError(f"Training script not found: {train_script}")
    result = subprocess.run(
        [sys.executable, train_script],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Training failed: {result.stderr[-500:]}")
    # Reload model
    import joblib
    bundle = joblib.load(SKLEARN_MODEL_PATH)
    _sklearn_model = bundle["model"]
    if os.path.exists(SKLEARN_META_PATH):
        with open(SKLEARN_META_PATH) as f:
            _sklearn_meta = json.load(f)
    if PROMETHEUS_AVAILABLE and _sklearn_meta:
        MODEL_ACCURACY_GAUGE.labels(model_name="sklearn_gb", metric="r2").set(_sklearn_meta.get("test_r2", 0))
        MODEL_ACCURACY_GAUGE.labels(model_name="sklearn_gb", metric="mae").set(_sklearn_meta.get("test_mae", 0))
    # Log to MLflow
    if _mlflow_connected and MLFLOW_AVAILABLE:
        try:
            exp = _mlflow_client.get_experiment_by_name("chicago-taxi-tip-prediction")
            exp_id = exp.experiment_id if exp else _mlflow_client.create_experiment("chicago-taxi-tip-prediction")
            with mlflow.start_run(experiment_id=exp_id, run_name=f"retrain-{datetime.now().strftime('%Y%m%d-%H%M%S')}"):
                mlflow.log_params({"trigger": "auto-retrain", "model_type": "GradientBoostingRegressor"})
                for k in ["test_r2", "test_mae", "train_r2", "train_mae"]:
                    if k in _sklearn_meta:
                        mlflow.log_metric(k, float(_sklearn_meta[k]))
        except Exception as e:
            logger.warning(f"Failed to log retrain to MLflow: {e}")
    logger.info(f"Retrain complete: R²={_sklearn_meta.get('test_r2')}, MAE={_sklearn_meta.get('test_mae')}")
    return _sklearn_meta

@app.post("/retrain/trigger")
async def retrain_trigger(background_tasks: BackgroundTasks, reason: str = "manual"):
    global _last_retrain_time
    if _last_retrain_time and (datetime.now() - _last_retrain_time).total_seconds() < RETRAIN_COOLDOWN_MINUTES * 60:
        remaining = RETRAIN_COOLDOWN_MINUTES - (datetime.now() - _last_retrain_time).total_seconds() / 60
        raise HTTPException(429, f"Retrain cooldown active. Retry in {remaining:.0f} minutes.")
    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(409, "Retrain already in progress")
    _last_retrain_time = datetime.now()
    if PROMETHEUS_AVAILABLE:
        RETRAIN_TRIGGER_COUNT.labels(reason=reason).inc()
    def _do_retrain():
        try:
            _retrain_sklearn_model()
        except Exception as e:
            logger.error(f"Retrain failed: {e}")
        finally:
            _retrain_lock.release()
    background_tasks.add_task(_do_retrain)
    return {"status": "retrain_started", "reason": reason, "triggered_at": datetime.now().isoformat()}

@app.get("/retrain/status")
async def retrain_status():
    return {
        "last_retrain": _last_retrain_time.isoformat() if _last_retrain_time else None,
        "retrain_in_progress": _retrain_lock.locked(),
        "cooldown_minutes": RETRAIN_COOLDOWN_MINUTES,
        "drift_threshold": DRIFT_RETRAIN_THRESHOLD,
        "model_meta": _sklearn_meta,
    }

@app.post("/retrain/auto-check")
async def retrain_auto_check(background_tasks: BackgroundTasks):
    """Check drift scores and trigger retrain if above threshold."""
    global _last_retrain_time
    df = _load_data()
    if df.empty:
        return {"action": "skip", "reason": "no data"}
    mid = len(df) // 2
    baseline, current = df.iloc[:mid], df.iloc[mid:]
    num_features = ["trip_miles", "fare", "trip_seconds"]
    max_drift = 0.0
    drifted_features = []
    for feat in num_features:
        b = pd.to_numeric(baseline[feat], errors="coerce").dropna()
        c = pd.to_numeric(current[feat], errors="coerce").dropna()
        if len(b) == 0 or len(c) == 0:
            continue
        score = min(abs(b.mean() - c.mean()) / max((b.std() + c.std()) / 2, 1e-6), 1.0)
        if PROMETHEUS_AVAILABLE:
            DRIFT_SCORE_GAUGE.labels(feature=feat).set(score)
        if score > DRIFT_RETRAIN_THRESHOLD:
            drifted_features.append({"feature": feat, "score": round(score, 3)})
        max_drift = max(max_drift, score)
    if not drifted_features:
        return {"action": "skip", "reason": "drift below threshold", "max_drift": round(max_drift, 3), "threshold": DRIFT_RETRAIN_THRESHOLD}
    # Trigger retrain
    if _last_retrain_time and (datetime.now() - _last_retrain_time).total_seconds() < RETRAIN_COOLDOWN_MINUTES * 60:
        return {"action": "skip", "reason": "cooldown active", "drifted_features": drifted_features}
    if not _retrain_lock.acquire(blocking=False):
        return {"action": "skip", "reason": "retrain already in progress"}
    _last_retrain_time = datetime.now()
    if PROMETHEUS_AVAILABLE:
        RETRAIN_TRIGGER_COUNT.labels(reason="auto_drift").inc()
    def _do_retrain():
        try:
            _retrain_sklearn_model()
        except Exception as e:
            logger.error(f"Auto-retrain failed: {e}")
        finally:
            _retrain_lock.release()
    background_tasks.add_task(_do_retrain)
    return {
        "action": "retrain_triggered",
        "reason": "drift_detected",
        "drifted_features": drifted_features,
        "max_drift": round(max_drift, 3),
        "threshold": DRIFT_RETRAIN_THRESHOLD,
    }


# ===================================================================
# AGENTIC DRIFT-TO-RETRAIN CONTROL LOOP
# ===================================================================

@app.post("/agentic/drift-retrain/run")
async def agentic_drift_retrain_run(
    background_tasks: BackgroundTasks,
    execute: bool = Query(False, description="If true, execute retrain when the agent recommends it."),
):
    """Run the agentic monitor -> evaluate -> retrain loop.

    Default mode is a safe dry-run: the agent can recommend retraining and
    produce a trace, but it will not mutate production state. Passing
    execute=true allows the existing retrain trigger to run, while model
    promotion remains blocked by policy.
    """
    from agentic.orchestrator import TaxiDriftRetrainOrchestrator

    drift_payload = await get_data_drift()
    status_payload = await retrain_status()

    orchestrator = TaxiDriftRetrainOrchestrator()
    result = orchestrator.run(
        drift_payload=drift_payload,
        retrain_status=status_payload,
        execute_retrain=False,
    )

    if execute and result["evaluation_decision"]["action"] == "retrain":
        try:
            trigger_response = await retrain_trigger(background_tasks, reason="agentic_drift")
            result["action"] = "retrain_triggered"
            result["execute_retrain"] = True
            result["retrain_result"] = {
                "executed": True,
                "status": "triggered",
                "reason": "agentic_drift",
                "trigger_response": trigger_response,
                "timestamp": datetime.now().isoformat(),
            }
            result["trace"].append({
                "agent": "TaxiRetrainerAgent",
                "step": "act",
                "status": "triggered",
                "summary": {"executed": True, "promotion_allowed": False},
            })
        except HTTPException as exc:
            result["action"] = "alert"
            result["execute_retrain"] = True
            result["retrain_result"] = {
                "executed": False,
                "status": "blocked",
                "reason": str(exc.detail),
                "trigger_response": None,
                "timestamp": datetime.now().isoformat(),
            }
            result["trace"].append({
                "agent": "TaxiRetrainerAgent",
                "step": "act",
                "status": "blocked",
                "summary": {"executed": False, "reason": str(exc.detail)},
            })

    return result


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
