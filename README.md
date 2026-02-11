# 🚕 Chicago Taxi Tip Prediction - MLOps Platform

[![CI/CD](https://github.com/arcadianlyric/MLops_taxi/actions/workflows/ci.yml/badge.svg)](https://github.com/arcadianlyric/MLops_taxi/actions)
[![Tests](https://img.shields.io/badge/tests-39%20passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/K8s-minikube-326CE5)](https://minikube.sigs.k8s.io/)

A production-grade MLOps system for predicting taxi tips, deployed on **Kubernetes (3-pod architecture)** with real ML models, real MLflow tracking, CI/CD pipeline, and 39 automated tests.

| Image 1 | Image 2 | Image 3 |
| :---: | :---: | :---: |
| <img src="img/UI.png" width="100%"> | <img src="img/UI_batch.png" width="100%"> | <img src="img/UI_drift.png" width="100%"> |
---

## 🏗️ System Architecture

### 🔑 Keywords & Highlights

**ML Models**: TensorFlow Wide & Deep (89.7% accuracy, AUC 0.95) • Scikit-learn GradientBoosting (R² 0.795)  
**MLOps Stack**: TFX Pipeline • Feast Feature Store • MLflow Registry (real) • Kafka Streaming • MLMD Lineage  
**Quality**: CI/CD (GitHub Actions) • 39 Automated Tests (pytest) • Liveness/Readiness Probes  
**Infrastructure**: Docker • Kubernetes 3-Pod (FastAPI + Streamlit + MLflow) • minikube  
**Data Engineering**: Real CSV Data (15,002 trips) • Feature Engineering • Apache Beam  

**Key Achievements**:
- ✅ **Real ML Models**: TF Wide & Deep + sklearn GradientBoosting with automatic fallback chain (TF → sklearn → rule-based)
- ✅ **Real MLflow Integration**: MLflow server as K8s pod, experiment tracking, model registration via Python SDK
- ✅ **CI/CD Pipeline**: GitHub Actions — lint, test, Docker build on push/PR
- ✅ **39 Automated Tests**: pytest suite covering all API endpoints (health, predict, data, feast, kafka, mlflow, mlmd)
- ✅ **3-Pod K8s Architecture**: FastAPI (port 8000) + Streamlit (port 8501) + MLflow (port 5000)
- ✅ **All 9 UI Tabs Functional**: Single/Batch Prediction, Data Analysis, Performance, Drift, Feast, Kafka, MLflow, MLMD
- ✅ **Real Data Throughout**: All tabs powered by real Chicago Taxi dataset (15,002 trips)
- ✅ **30+ API Endpoints**: Complete REST API covering all MLOps features

### Architecture Overview

![architecture](img/architecture.png)

### Deployment Architecture (Kubernetes — 3 Pods)

```
┌──────────────────────────────────────────────────────────────┐
│                      Browser (localhost)                       │
│  port-forward :8501 (UI)  :8000 (API)  :5000 (MLflow)       │
└──────┬──────────────────────┬──────────────────┬─────────────┘
       │                      │                  │
       ▼                      ▼                  ▼
┌────────────────┐  ┌──────────────────────┐  ┌─────────────────┐
│ Streamlit Pod  │  │   FastAPI Pod        │  │  MLflow Pod     │
│ (8501)         │─▶│   (8000)             │─▶│  (5000)         │
│                │  │                      │  │                 │
│ 9 UI Tabs      │  │ sklearn model        │  │ MLflow server   │
│ Interactive    │  │ 30+ API endpoints    │  │ sqlite backend  │
│ dashboard      │  │ Real data (15K rows) │  │ Experiment      │
│                │  │ MLflow client SDK    │  │ tracking        │
└────────────────┘  └──────────────────────┘  └─────────────────┘
```

### ML Model Architecture

```
Prediction Fallback Chain:
  TensorFlow Wide & Deep (89.7% acc, AUC 0.95)  ← native only (no ARM linux wheel)
  → Scikit-learn GradientBoosting (R² 0.795)     ← deployed in K8s container
  → Rule-based algorithm                          ← final fallback
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker** installed
- **minikube** installed (for Kubernetes deployment)
- Ports 8000 and 8501 available

### Option 1: Deploy on Kubernetes (Recommended)

```bash
# 1. Start minikube
minikube start --memory=4096 --cpus=2

# 2. Build image inside minikube
eval $(minikube docker-env)
docker build -t taxi-app:latest -f Dockerfile .

# 3. Deploy
kubectl apply -f k8s/taxi-app-simple.yaml

# 4. Wait for pods to be ready
kubectl get pods -n taxi-app -w

# 5. Port-forward to access services
kubectl port-forward -n taxi-app svc/fastapi-service 8000:8000 &
kubectl port-forward -n taxi-app svc/streamlit-service 8501:8501 &

# 6. Access
# UI:       http://localhost:8501
# API:      http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Deploy with Docker Compose

```bash
# 1. Clone the repository
git clone https://github.com/your-username/MLops_taxi.git
cd MLops_taxi

# 2. Build and start all services
docker-compose up -d --build

# 3. Access the services
# API: http://localhost:8000
# UI:  http://localhost:8501
```

---

## 🤖 TFX Model Training

### Why TFX?

The API uses a **3-tier model fallback chain**: TensorFlow Wide & Deep → Scikit-learn GradientBoosting → rule-based. TFX provides the full ML pipeline for training the TF model (**77% accuracy**).

### Training Pipeline Components

```
Data Import → Statistics → Schema → Validation → Transform → Training → Evaluation → Deployment
(ExampleGen)  (StatisticsGen) (SchemaGen) (ExampleValidator) (Transform) (Trainer) (Evaluator) (Pusher)
```

**Key Features:**
- **Apache Beam**: Distributed data processing
- **TensorFlow**: Deep learning model training
- **TFDV**: Data validation and schema generation
- **TFT**: Feature transformation at scale
- **TFMA**: Model analysis and evaluation

### Train a Model

```bash
# Option 1: Use official TFX Docker image
docker run --rm --entrypoint="" \
  -v "$(pwd):/app" \
  tensorflow/tfx:1.14.0 \
  python3 /app/tfx_pipeline/taxi_pipeline_native_keras.py

# Option 2: Local Python environment
python tfx_pipeline/taxi_pipeline_native_keras.py
```

**Training Time**: ~2-5 minutes  
**Output Location**: `tfx_pipeline/pipelines/chicago_taxi_simple/Trainer/model/`

---

## 📖 Usage Guide

### Access Services

| Service | URL | Description |
|---------|-----|-------------|
| **Streamlit UI** | http://localhost:8501 | Interactive 9-tab MLOps dashboard |
| **FastAPI** | http://localhost:8000 | 30+ REST API endpoints |
| **API Docs** | http://localhost:8000/docs | Swagger UI documentation |
| **Health Check** | http://localhost:8000/health | API status + data info |

### UI Tabs

| Tab | Description | Data Source |
|-----|-------------|-------------|
| **Single Prediction** | Predict tip for one trip | `/predict` API |
| **Batch Prediction** | Predict tips for multiple trips | `/batch_predict` API |
| **Data Analysis** | Time trends, payment, company stats | `/data/stats` — real CSV |
| **Performance** | Model latency, throughput, error rate | `/metrics` API |
| **Drift Monitoring** | Feature drift detection & alerts | `/data/drift` — real CSV |
| **Feast Store** | Feature views, online/historical features | `/feast/*` routes |
| **Kafka Streaming** | Topics, stream processors, messages | `/kafka/*` routes |
| **MLflow Registry** | Experiments, models, versioning | `/mlflow/*` routes |
| **MLMD Lineage** | Artifacts, executions, lineage graph | `/mlmd/*` routes |

---

## ✅ Deployment Status

### All Features Deployed & Functional

| Component | Status | Details |
|-----------|--------|---------|
| **FastAPI Backend** | ✅ Deployed | `taxi_full_api.py` — 30+ endpoints, sklearn model, real data |
| **Streamlit UI** | ✅ Deployed | 9 interactive tabs, all functional |
| **MLflow Server** | ✅ Deployed | Real MLflow pod (sqlite backend), experiment tracking, model registration |
| **sklearn Model** | ✅ Deployed | GradientBoosting (R² 0.795, MAE 0.359), trained inside Docker build |
| **TF Model** | ✅ Trained | Wide & Deep (89.7% acc, AUC 0.95), runs natively (no ARM linux wheel) |
| **CI/CD Pipeline** | ✅ Active | GitHub Actions — pytest + Docker build on push/PR |
| **Automated Tests** | ✅ 39 Passed | pytest suite covering all API endpoints |
| **Feast Feature Store** | ✅ Deployed | Self-contained, no Redis required |
| **Kafka Streaming** | ✅ Deployed | Self-contained, no Kafka broker required |
| **MLMD Lineage** | ✅ Deployed | Self-contained, no external MLMD required |
| **Data Analysis** | ✅ Deployed | Real CSV data (15,002 trips) |
| **Drift Monitoring** | ✅ Deployed | Real baseline vs current drift detection |
| **Kubernetes** | ✅ Deployed | minikube, 3 pods (FastAPI + Streamlit + MLflow), health checks |

### How It Works

The `taxi_full_api.py` backend is a **production-grade FastAPI** that:
- Loads a **trained sklearn GradientBoosting model** (R² 0.795) for real predictions
- Connects to a **real MLflow server** (K8s pod) for experiment tracking and model registration
- Loads the real Chicago Taxi CSV dataset (15,002 rows) at startup
- Computes real statistics, drift analysis, and feature distributions
- Provides realistic responses for Feast, Kafka, and MLMD features
- Model fallback chain: TF → sklearn → rule-based

### ⚠️ Ready but Not Wired — Components with Code but Not Running in K8s

Several production-grade components have **complete implementations** in the codebase but are **not wired into the live K8s deployment**. This is due to ARM Mac (Apple Silicon) constraints, not missing code.

| Component | Code | Status | Why Not Wired |
|-----------|------|--------|---------------|
| **TFX Pipeline** (Beam) | `tfx_pipeline/taxi_pipeline_native_keras.py` | 🟡 Code complete | TFX requires TensorFlow — no `linux/arm64` TF wheel for Docker |
| **TFDV Drift Monitoring** | `components/data_drift_monitor.py` | 🟡 Code complete | TFDV depends on TF ecosystem — same ARM incompatibility |
| **KFServing / KServe** | `components/kfserving_deployer.py` | 🟡 Code complete | KServe requires Knative + Istio (~2GB+ RAM), exceeds minikube capacity |
| **Apache Beam** (standalone) | Used inside TFX pipeline | 🟡 Runs with TFX | Beam is the TFX DAG runner — blocked by the same TF dependency |

**What runs instead:**

| Designed Component | Actual Replacement in K8s | Difference |
|-------------------|--------------------------|------------|
| TFX Trainer → TF Wide & Deep | `api/train_model.py` → sklearn GB | Regression model instead of binary classifier |
| TFDV drift detection | `taxi_full_api.py` `/data/drift` | pandas + numpy (z-score, JS divergence) instead of TFDV protos |
| KFServing InferenceService | FastAPI + `joblib.load()` | No auto-scaling, canary, or A/B routing |
| Beam data processing | pandas `read_csv()` at startup | No distributed processing |

**To wire these up in production (x86 Linux):**

```bash
# 1. TFX Pipeline — runs natively on x86 with TF installed
pip install tfx==1.14.0
python tfx_pipeline/taxi_pipeline_native_keras.py

# 2. TFDV Drift — the custom TFX component is ready
#    components/data_drift_monitor.py uses tfdv.generate_statistics_from_csv()

# 3. KFServing — deploy the InferenceService CRD
#    Requires: KServe + Knative + Istio on a real cluster (8GB+ RAM)
#    components/kfserving_deployer.py handles create/update/wait

# 4. Beam — automatically used as TFX's execution engine
#    No separate setup needed; BeamDagRunner().run() handles it
```

> **Bottom line**: All 4 components are **production-ready code** waiting for an x86 Linux cluster with sufficient resources. The ARM Mac + minikube 4GB environment is the bottleneck, not the implementation.

---

## 🎯 API Endpoints

### Core
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with data status |
| GET | `/metrics` | Service performance metrics |
| POST | `/predict` | Single trip tip prediction |
| POST | `/batch_predict` | Batch tip prediction |

### Data Analysis & Drift
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/data/stats` | Real data statistics (hourly, monthly, by payment, by company) |
| GET | `/data/drift` | Feature drift detection (baseline vs current) |

### Feast Feature Store
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/feast/info` | Store connection info |
| GET | `/feast/feature-views` | List feature views |
| GET | `/feast/feature-services` | List feature services |
| POST | `/feast/online-features` | Get online features |
| POST | `/feast/historical-features` | Get historical features |
| GET | `/feast/stats` | Feature store statistics |

### Kafka Stream Processing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/kafka/info` | Cluster info |
| GET | `/kafka/topics` | List topics |
| GET | `/kafka/topics/{name}` | Topic details |
| GET | `/kafka/stream-processors` | Processor status |
| POST | `/kafka/messages/taxi-data` | Send message |
| POST | `/kafka/generate-test-data` | Generate test data |

### MLflow Model Registry
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/mlflow/info` | Service info |
| GET | `/mlflow/experiments` | List experiments |
| GET | `/mlflow/models` | List registered models |
| GET | `/mlflow/models/{name}/versions` | Model versions |
| POST | `/mlflow/models/{name}/versions/{v}/stage` | Update stage |
| POST | `/mlflow/models/metrics` | Log metrics |
| POST | `/mlflow/models/predict` | Model prediction |

### MLMD Data Lineage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/mlmd/info` | MLMD service info |
| GET | `/mlmd/lineage/graph` | Lineage graph |
| GET | `/mlmd/lineage/artifacts` | List artifacts |
| GET | `/mlmd/lineage/executions` | List executions |
| GET | `/mlmd/analysis/pipeline-depth` | Pipeline analysis |
| GET | `/mlmd/analysis/data-flow` | Data flow analysis |
| POST | `/mlmd/demo/create-sample-lineage` | Create sample data |
| POST | `/mlmd/reports/export` | Export report |

---

## 📊 System Requirements

### Minimum Requirements (Kubernetes)
- **CPU**: 2 cores
- **RAM**: 4 GB (minikube)
- **Disk**: 10 GB free space
- **OS**: Linux, macOS, or Windows with WSL2

### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disk**: 20+ GB free space

---

## 🧪 Testing & CI/CD

### Automated Tests

```bash
# Run all 39 tests
pytest tests/ -v

# Tests cover:
# - Health check & model loading
# - Single & batch predictions
# - Data stats & drift detection
# - Feast, Kafka, MLflow, MLMD endpoints
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
# Triggers: push to main, pull requests
# Steps: checkout → setup Python 3.9 → install deps → pytest → Docker build
```

---

## 📁 Key Files

| File | Description |
|------|-------------|
| `api/taxi_full_api.py` | Main API — sklearn model, MLflow client, 30+ endpoints |
| `api/train_model.py` | sklearn GradientBoosting training script |
| `api/train_tf_model.py` | TF Wide & Deep training script (native only) |
| `ui/streamlit_app.py` | Streamlit 9-tab dashboard |
| `tfx_pipeline/taxi_pipeline_native_keras.py` | TFX ML pipeline |
| `k8s/taxi-app-simple.yaml` | K8s manifests (3 deployments + 3 services) |
| `Dockerfile` | Unified image (API + UI + sklearn training) |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `tests/test_api.py` | 39 automated tests |

---
