# Chicago Taxi Tip Prediction -- MLOps Platform

[![CI/CD](https://github.com/arcadianlyric/MLops_taxi/actions/workflows/ci.yml/badge.svg)](https://github.com/arcadianlyric/MLops_taxi/actions)
[![Tests](https://img.shields.io/badge/tests-54%20passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/K8s-5%20pods-326CE5)](https://minikube.sigs.k8s.io/)

| UI | Batch Prediction | Drift Monitoring |
| :---: | :---: | :---: |
| <img src="img/UI.png" width="100%"> | <img src="img/UI_batch.png" width="100%"> | <img src="img/UI_drift.png" width="100%"> |

---

## 1. Results and Impact

### Summary

An end-to-end MLOps platform for Chicago taxi tip prediction, running on Kubernetes with 6 pods across 5 service types, 62 automated tests, Prometheus/Grafana observability, A/B testing, drift-triggered auto-retraining, bounded parallel batch inference, HPA-ready FastAPI serving, and a Helm chart for reproducible deployment.

### Quantitative Results

| Metric | Value |
|--------|-------|
| **sklearn GradientBoosting R2** | 0.795 |
| **sklearn MAE** | $0.359 |
| **TF Wide & Deep accuracy** | 89.7% |
| **TF Wide & Deep AUC** | 0.95 |
| **Automated tests** | 62 passed (5 test modules) |
| **API endpoints** | 40+ |
| **K8s pods** | 6 by default (2 FastAPI + Streamlit, MLflow, Prometheus, Grafana) |
| **Data** | 15,002 Chicago taxi trips |

### Key Capabilities

- **Model serving** with 3-tier fallback: TensorFlow Wide & Deep -> sklearn GradientBoosting -> rule-based
- **Prometheus + Grafana** monitoring: prediction latency histograms, throughput counters, model accuracy gauges, drift score gauges, alert rules
- **A/B testing framework**: weighted traffic splitting across model variants with per-variant latency and tip statistics
- **Auto-retraining**: drift detection triggers background sklearn retraining with cooldown, result logged to MLflow
- **Agentic drift-to-retrain loop**: Monitor -> policy guardrails -> evaluator -> optional retrain, with trace output and no automatic model promotion
- **MLflow experiment tracking**: real MLflow server pod, model registration, metric logging via Python SDK
- **Scalable serving**: bounded parallel `/batch_predict`, configurable batch limits, capped in-process history, 2 FastAPI replicas, and HPA config for 2-6 replicas
- **Helm chart**: parameterized deployment of all 5 services with configurable resources, monitoring toggle, environment variables, and FastAPI autoscaling
- **DVC integration**: data version control for the training dataset
- **CI/CD**: GitHub Actions pipeline (lint, pytest, Docker build) on push and PR
- **9-tab Streamlit dashboard**: predictions, data analysis, drift monitoring, Feast, Kafka, MLflow, MLMD

### MLOps Maturity

Assessed against Google's MLOps maturity model:
- **Level 0** (Manual): Exceeded. Automated training, serving, and testing in place.
- **Level 1** (ML Pipeline Automation): Achieved. TFX pipeline code complete, sklearn pipeline automated end-to-end in Docker.
- **Level 2** (CI/CD for ML): Partially achieved. CI/CD for code; auto-retrain on drift provides continuous training. Full CT/CD pipeline for model artifacts is a remaining gap.

---

## 2. Materials and Methods

### 2.1 Data

- **Source**: [Chicago Data Portal -- Taxi Trips](https://data.cityofchicago.org/Transportation/Taxi-Trips/wrvz-psew)
- **Size**: 15,002 rows, 23 features
- **Target variable**: `tips` (regression for sklearn), `big_tipper` (binary for TF, tip > 20% of fare)
- **Key features**: `trip_miles`, `trip_seconds`, `fare`, `payment_type`, `company`, `pickup_community_area`, `dropoff_community_area`, temporal features (hour, day, month)
- **Versioning**: DVC tracks `tfx_pipeline/data/simple/data.csv` with metadata (row count, feature count, source URL)

### 2.2 Models

#### TensorFlow Wide & Deep (binary classification)

Architecture follows [Cheng et al., 2016](https://arxiv.org/abs/1606.07792). The wide component captures memorization of feature interactions; the deep component provides generalization through embeddings.

- **Training**: `tfx_pipeline/taxi_pipeline_native_keras.py` via TFX with BeamDagRunner
- **Components**: CsvExampleGen, StatisticsGen, SchemaGen, ExampleValidator, Transform, Trainer, Evaluator, Pusher
- **Standalone training**: `api/train_tf_model.py` (no TFX dependency)
- **Limitation**: Requires x86 Linux for Docker deployment (no `linux/arm64` TensorFlow wheel)

#### Scikit-learn GradientBoosting (regression)

- **Training**: `api/train_model.py`, runs during `docker build`
- **Algorithm**: `GradientBoostingRegressor(n_estimators=200, max_depth=5, learning_rate=0.1)`
- **Features**: 8 numerical + 2 categorical (label-encoded)
- **Why GradientBoosting**: Strong baseline for tabular regression; no GPU requirement; fast inference (<5ms); deterministic output. Compared alternatives: LinearRegression (R2=0.42), RandomForest (R2=0.77), XGBoost (R2=0.80, marginal gain not worth added dependency).

#### Rule-based fallback

Heuristic using payment type, time of day, trip distance, and fare amount. Provides graceful degradation when no ML model is available.

### 2.3 Infrastructure

#### Kubernetes Architecture (5 pods)

```
Browser (localhost)
      :8501 (UI)   :8000 (API)   :5000 (MLflow)   :9090 (Prometheus)   :3000 (Grafana)
     |              |              |                   |                    |
     v              v              v                   v                    v
 Streamlit     FastAPI x2      MLflow            Prometheus             Grafana
  Pod            Pods           Pod                Pod                   Pod
 (256Mi)       (512Mi)        (256Mi)            (128Mi)              (128Mi)
```

All pods run in the `taxi-app` namespace on minikube. FastAPI starts with 2 replicas and can scale to 6 replicas with the included HPA.

**Manifest files**:
- `k8s/taxi-app-simple.yaml` -- FastAPI, Streamlit, MLflow deployments and services
- `k8s/monitoring.yaml` -- Prometheus (with alert rules) + Grafana (with provisioned datasource and dashboard)

**Helm chart** (`helm/taxi-app/`): Parameterizes all 5 services. Key overrides in `values.yaml`:
- `fastapi.replicas`, `fastapi.autoscaling`, `fastapi.resources`, `fastapi.env` (MLFLOW_TRACKING_URI, RETRAIN_COOLDOWN_MINUTES, DRIFT_RETRAIN_THRESHOLD, BATCH_MAX_SIZE, BATCH_MAX_WORKERS)
- `monitoring.enabled`, `monitoring.prometheus.enabled`, `monitoring.grafana.enabled`

#### Docker

Single `Dockerfile` builds a unified image: installs Python deps (FastAPI, scikit-learn, mlflow, prometheus-client, prometheus-fastapi-instrumentator), copies source, trains sklearn model at build time.

#### CI/CD

GitHub Actions (`.github/workflows/ci.yml`): checkout -> Python 3.9 setup -> pip install -> pytest -> Docker build. Triggers on push to main and pull requests.

### 2.4 Monitoring and Observability

#### Prometheus Metrics

Exposed at `/metrics/prometheus` via `prometheus_fastapi_instrumentator`:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `model_prediction_latency_seconds` | Histogram | `model_type` | Prediction latency with P50/P95/P99 buckets |
| `model_prediction_total` | Counter | `model_type`, `status` | Total predictions by model and success/error |
| `data_drift_score` | Gauge | `feature` | Current drift score per feature |
| `model_accuracy` | Gauge | `model_name`, `metric` | Model R2, MAE, accuracy, AUC |
| `ab_test_assignment_total` | Counter | `experiment`, `variant` | A/B test traffic assignments |
| `retrain_trigger_total` | Counter | `reason` | Auto-retrain trigger count by reason |

#### Alert Rules (Prometheus)

- `ModelHighLatency`: P95 latency > 1s for 5 minutes
- `ModelAccuracyDrop`: R2 < 0.6 for 10 minutes
- `DataDriftDetected`: drift score > 0.5 for 15 minutes
- `HighErrorRate`: error rate > 5% for 5 minutes

#### Grafana Dashboard

Pre-provisioned dashboard with 8 panels: Prediction QPS, P95 Latency, Model R2 Score, Drift Scores, Latency Over Time (P50/P95/P99), Predictions by Model Type, A/B Test Assignments, Retrain Triggers.

### 2.5 A/B Testing

Endpoints under `/ab/*`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ab/experiments` | List all experiments |
| POST | `/ab/experiments` | Create experiment (name, variants with model + weight) |
| GET | `/ab/experiments/{name}` | Experiment details with per-variant statistics |
| POST | `/ab/predict` | Predict with weighted random variant assignment |
| DELETE | `/ab/experiments/{name}` | Stop experiment |

A default experiment `tip-model-v1` initializes at startup: 80% control (sklearn) / 20% treatment (rule-based). Variant selection uses weighted random sampling. Each prediction records variant, model, tip, and latency for later analysis.

### 2.6 Auto-Retraining

Endpoints under `/retrain/*`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/retrain/trigger` | Manual retrain with reason tag |
| GET | `/retrain/status` | Current retrain state, cooldown, model metadata |
| POST | `/retrain/auto-check` | Check drift, trigger retrain if threshold exceeded |

**Mechanism**: `/retrain/auto-check` computes drift scores for `trip_miles`, `fare`, `trip_seconds` using standardized mean difference. If any feature exceeds `DRIFT_RETRAIN_THRESHOLD` (default 0.3) and cooldown has elapsed (`RETRAIN_COOLDOWN_MINUTES`, default 30), a background task:

1. Runs `api/train_model.py` as subprocess
2. Hot-reloads the new model into the running process
3. Updates Prometheus accuracy gauges
4. Logs parameters and metrics to MLflow

### 2.7 Drift Detection

`/data/drift` computes drift between first-half (baseline) and second-half (current) of the dataset:
- **Numerical features**: standardized mean difference (|mean_diff| / pooled_std), capped at 1.0
- **Categorical features**: Jensen-Shannon divergence
- **Threshold**: 0.1 for drift detection, classification into No/Low/Medium/High

### 2.8 API Endpoints (40+)

**Core**: `/health`, `/predict`, `/batch_predict` (bounded parallel inference), `/metrics`, `/metrics/prometheus`

**Data**: `/data/stats`, `/data/drift`

**A/B Testing**: `/ab/experiments`, `/ab/predict`

**Retraining**: `/retrain/trigger`, `/retrain/status`, `/retrain/auto-check`

**Agentic Control Plane**: `/agentic/drift-retrain/run` (safe dry-run by default; `execute=true` can trigger retrain, but production promotion remains blocked)

**Feast**: `/feast/info`, `/feast/feature-views`, `/feast/feature-services`, `/feast/online-features`, `/feast/historical-features`, `/feast/stats`

**Kafka**: `/kafka/info`, `/kafka/topics`, `/kafka/topics/{name}`, `/kafka/stream-processors`, `/kafka/messages/taxi-data`, `/kafka/generate-test-data`

**MLflow**: `/mlflow/info`, `/mlflow/experiments`, `/mlflow/models`, `/mlflow/models/{name}/versions`, `/mlflow/models/{name}/versions/{v}/stage`, `/mlflow/models/metrics`, `/mlflow/models/predict`

**MLMD**: `/mlmd/info`, `/mlmd/lineage/graph`, `/mlmd/lineage/artifacts`, `/mlmd/lineage/executions`, `/mlmd/analysis/pipeline-depth`, `/mlmd/analysis/data-flow`, `/mlmd/demo/create-sample-lineage`, `/mlmd/reports/export`

### 2.9 Testing

54 tests across 4 modules:

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_api_core.py` | 10 | Health, predict, batch, metrics |
| `test_api_data.py` | 7 | Data stats, drift detection |
| `test_api_advanced.py` | 21 | Feast, Kafka, MLflow, MLMD |
| `test_api_phase2.py` | 16 | A/B testing, auto-retrain, Prometheus |

```bash
pytest tests/ -v
```

---

## 3. Discussion and Future Work

### What Works Well

- The model fallback chain provides resilience: even if TF and sklearn both fail, the API still returns predictions.
- Prometheus metrics give real-time visibility into model behavior without external dependencies.
- A/B testing is lightweight (in-memory state) and does not require infrastructure changes to run experiments.
- Auto-retrain completes the feedback loop from drift detection to model update.

### Known Limitations

- **TFX/TFDV/KServe/Beam**: Complete implementations exist in `components/` and `tfx_pipeline/` but cannot run on ARM Mac Docker. These require an x86 Linux cluster. See `components/data_drift_monitor.py`, `components/kfserving_deployer.py`, `tfx_pipeline/taxi_pipeline_native_keras.py`.
- **A/B state is in-memory**: Experiment results are lost on pod restart. Production usage would need Redis or a database backend.
- **A/B state is not shared across replicas**: FastAPI can scale horizontally, but A/B experiment state remains in-memory per pod. Production usage would need Redis or a database backend.
- **No model artifact versioning**: Auto-retrain overwrites the model file in place. A production system should version artifacts in MLflow Model Registry or a blob store.
- **Grafana dashboard**: Pre-provisioned via ConfigMap. In production, use persistent storage and Grafana's API for dashboard management.

### Future Work

- **Full CT/CD pipeline**: Automate model artifact promotion from staging to production with gated evaluation.
- **KServe integration**: Deploy on an x86 cluster with Knative + Istio for canary deployments and autoscaling.
- **Feature store**: Replace self-contained Feast mock with a real Feast deployment backed by Redis.
- **Latency/QPS-based autoscaling**: Extend the current CPU/memory HPA with Prometheus Adapter custom metrics for prediction QPS and P95 latency.
- **Persistent A/B state**: Store experiment results in PostgreSQL or Redis for durability.
- **Multi-model serving**: Serve TF and sklearn models simultaneously via KServe InferenceServices, enabling true model comparison.

---

## Quick Start

### Prerequisites

- Docker installed
- minikube installed
- Ports 8000, 8501 available

### Deploy (Kubernetes)

```bash
# Start minikube
minikube start --memory=4096 --cpus=2

# Build image inside minikube
eval $(minikube docker-env)
docker build -t taxi-app:latest -f Dockerfile .

# Deploy application + monitoring
kubectl apply -f k8s/taxi-app-simple.yaml
kubectl apply -f k8s/monitoring.yaml

# Wait for all 5 pods
kubectl get pods -n taxi-app

# Port-forward
kubectl port-forward -n taxi-app svc/fastapi-service 8000:8000 &
kubectl port-forward -n taxi-app svc/streamlit-service 8501:8501 &
kubectl port-forward -n taxi-app svc/prometheus-service 9090:9090 &
kubectl port-forward -n taxi-app svc/grafana-service 3000:3000 &
```

### Deploy (Helm)

```bash
helm install taxi-app helm/taxi-app/ -n taxi-app --create-namespace
```

### Access

| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI / Swagger | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |
| MLflow | http://localhost:5000 |

---

## Key Files

| File | Description |
|------|-------------|
| `api/taxi_full_api.py` | FastAPI backend: 40+ endpoints, sklearn model, Prometheus metrics, A/B testing, auto-retrain |
| `agentic/` | Agentic drift-to-retrain loop: monitor, policy guardrails, evaluator, retrainer, orchestrator |
| `api/train_model.py` | sklearn GradientBoosting training script |
| `api/train_tf_model.py` | TF Wide & Deep standalone training |
| `ui/streamlit_app.py` | Streamlit 9-tab dashboard |
| `tfx_pipeline/taxi_pipeline_native_keras.py` | TFX ML pipeline (x86 only) |
| `k8s/taxi-app-simple.yaml` | K8s manifests: FastAPI, Streamlit, MLflow |
| `k8s/monitoring.yaml` | K8s manifests: Prometheus, Grafana |
| `helm/taxi-app/` | Helm chart for parameterized deployment |
| `docs/INTERVIEW_SCALABILITY_REVIEW.md` | Interview-ready review and scalability optimization notes |
| `Dockerfile` | Unified image (API + UI + sklearn training + Prometheus) |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `tests/` | 62 automated tests (5 modules) |
| `.dvc/` | DVC configuration for data versioning |
| `components/` | TFX custom components (drift monitor, KServe deployer, alert manager, model monitoring) |
| `docs/PROJECT_ANALYSIS.md` | Project maturity analysis |

---
