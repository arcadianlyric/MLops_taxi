# 🚕 Chicago Taxi Tip Prediction

[![TFX](https://img.shields.io/badge/TFX-0.21.4-orange)](https://www.tensorflow.org/tfx)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)

A complete MLOps system for predicting taxi tips using TensorFlow Extended (TFX), FastAPI, and Streamlit.

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Project Architecture](#-project-architecture)
- [TFX Model Training](#-tfx-model-training)
- [Usage Guide](#-usage-guide)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Start

### Prerequisites

- Docker installed
- Ports 8000 and 8501 available

### Deploy with Docker Compose

```bash
# 1. Clone the repository
git clone https://github.com/your-username/MLops_taxi.git
cd MLops_taxi

# 2. Build and start all services
docker-compose up -d --build

# 3. Wait for services to start (~30 seconds)
# Check status
docker-compose ps

# 4. Access the services
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# UI: http://localhost:8501
```

### Verify Deployment

```bash
# Check API health
curl http://localhost:8000/health

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 🏗️ Project Architecture

### System Overview

```
┌─────────────────────────────────────────────────────┐
│                   Browser                            │
│  http://localhost:8501  │  http://localhost:8000   │
└────────────┬────────────┴──────────────┬────────────┘
             │                           │
             ▼                           ▼
┌─────────────────────┐      ┌─────────────────────┐
│   Streamlit UI      │      │    FastAPI          │
│   (taxi-ui)         │─────▶│    (taxi-api)       │
│   Port: 8501        │      │    Port: 8000       │
│                     │      │                     │
│   - Interactive UI  │      │   - Prediction API  │
│   - Visualization   │      │   - Health Check    │
│   - Batch Predict   │      │   - API Docs        │
└─────────────────────┘      └─────────────────────┘
```

### Directory Structure

```
MLops_taxi/
├── api/
│   ├── taxi_simple_api.py        # Rule-based prediction API
│   └── taxi_tfx_api.py           # TFX model API (optional)
├── ui/
│   └── streamlit_app.py          # Streamlit web interface
├── tfx_pipeline/
│   ├── taxi_pipeline_simple.py   # TFX training pipeline
│   ├── taxi_utils.py             # Data processing & model
│   └── data/simple/data.csv      # Training data
├── Dockerfile.api                # API container definition
├── Dockerfile.ui                 # UI container definition
├── docker-compose.yml            # Docker Compose configuration
└── README.md                     # This file
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|----------|
| **API** | FastAPI + Python | Prediction service with rule-based algorithm |
| **UI** | Streamlit | Interactive web interface for predictions |
| **Training** | TFX + TensorFlow | Optional: Train ML models (77% accuracy) |
| **Deployment** | Docker Compose | Container orchestration |

### Docker Images

| Image | Base | Size | Startup Time |
|-------|------|------|-------------|
| `taxi-api` | python:3.9-slim | ~200 MB | ~5 seconds |
| `taxi-ui` | python:3.9-slim | ~500 MB | ~10 seconds |

---

## 🤖 TFX Model Training

### Why TFX?

The default API uses a **rule-based algorithm** for tip prediction. You can optionally train a **deep learning model** using TFX to achieve **77% accuracy**.

### Training Pipeline

```
Data Import → Statistics → Schema → Transform → Training
(ExampleGen)  (StatisticsGen) (SchemaGen) (Transform) (Trainer)
```

### Train a Model

```bash
# Use official TFX Docker image to train
docker run --rm --entrypoint="" \
  -v "$(pwd):/app" \
  tensorflow/tfx:0.21.4 \
  python3 /app/tfx_pipeline/taxi_pipeline_simple.py
```

**Training Time**: ~2-5 minutes  
**Output Location**: `tfx_pipeline/pipelines/chicago_taxi_simple/Trainer/model/`

### Training Results

- ✅ Training Accuracy: 75.02%
- ✅ Validation Accuracy: 77.10%
- ✅ Model Type: Wide & Deep Neural Network
- ✅ Features: 16 input features

### Using the Trained Model

After training, you can switch to the TFX model API:

```bash
# Note: Requires Dockerfile.tfx-api (not included in default setup)
# The TFX API requires more memory (~2GB) and longer startup time (~30s)
```

### Apache Beam Integration

TFX uses **Apache Beam** internally for data processing:

- **ExampleGen**: Reads CSV data using Beam
- **StatisticsGen**: Computes statistics in parallel
- **Transform**: Performs data transformations
- **Trainer**: Processes training data in batches

**Beam Runner**: DirectRunner (local) by default

---

## 📖 Usage Guide

### Access Services

| Service | URL | Description |
|---------|-----|-------------|
| **Streamlit UI** | http://localhost:8501 | Interactive prediction interface |
| **FastAPI** | http://localhost:8000 | Prediction API endpoint |
| **API Docs** | http://localhost:8000/docs | Swagger UI documentation |
| **Health Check** | http://localhost:8000/health | API status |

### Make Predictions via UI

1. Open http://localhost:8501 in your browser
2. Fill in the prediction form:
   - Trip Distance: 5.2 miles
   - Fare: $15.50
   - Payment Type: Credit Card
   - Use default values for other fields
3. Click "Predict Tip" button
4. View the prediction results

### Make Predictions via API

#### Health Check

```bash
curl http://localhost:8000/health
```

#### Prediction Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "trip_miles": 5.2,
    "trip_seconds": 900,
    "fare": 15.50,
    "pickup_latitude": 41.8781,
    "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881,
    "dropoff_longitude": -87.6198,
    "pickup_hour": 14,
    "pickup_day_of_week": 2,
    "trip_start_day": 15,
    "trip_start_month": 6,
    "pickup_community_area": 32,
    "dropoff_community_area": 33,
    "pickup_census_tract": 0,
    "dropoff_census_tract": 0,
    "payment_type": "Credit Card",
    "company": "Taxi Affiliation Services"
  }'
```

#### Expected Response

```json
{
  "fare_amount": 15.5,
  "predicted_tip": 3.4,
  "tip_rate": 21.94,
  "total_cost": 18.9,
  "payment_type": "Credit Card",
  "trip_miles": 5.2,
  "pickup_hour": 14
}
```

---

## 💻 Development

### View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f ui
```

### Modify Code

#### Update API Code

```bash
# 1. Edit api/taxi_simple_api.py
# 2. Restart the container
docker-compose restart api
```

#### Update UI Code

```bash
# 1. Edit ui/streamlit_app.py
# 2. Restart the container
docker-compose restart ui
```

### Debug Containers

```bash
# Enter API container
docker exec -it taxi-api bash

# Enter UI container
docker exec -it taxi-ui bash

# Test API connection from UI container
docker exec -it taxi-ui curl http://taxi-api:8000/health
```

### Rebuild Images

```bash
# Rebuild all images
docker-compose build --no-cache

# Rebuild and restart
docker-compose up -d --build
```

### Monitor Resources

```bash
# View resource usage
docker stats taxi-api taxi-ui

# View container details
docker inspect taxi-api
```


---

## 🐛 Troubleshooting

### Issue 1: Port Already in Use

**Symptom**: `port is already allocated`

**Solution**:
```bash
# Find process using the port
lsof -i :8000
lsof -i :8501

# Stop old containers
docker-compose down
```

### Issue 2: UI Cannot Connect to API

**Symptom**: `Connection refused`

**Diagnosis**:
```bash
# 1. Check if API container is running
docker ps | grep taxi-api

# 2. Check API health
curl http://localhost:8000/health

# 3. Check network connection from UI container
docker exec taxi-ui curl http://taxi-api:8000/health

# 4. Check environment variables
docker exec taxi-ui printenv | grep API_BASE_URL
```

**Solution**:
```bash
# Recreate containers with correct network configuration
docker-compose down
docker-compose up -d
```

### Issue 3: Container Fails to Start

**Check logs**:
```bash
docker-compose logs api
docker-compose logs ui
```

**Common causes**:
- Dependency installation failure
- Code syntax errors
- Port conflicts

### Issue 4: Out of Disk Space

**Symptom**: `No space left on device`

**Solution**:
```bash
# Clean up unused containers, images, networks
docker system prune -f

# Clean up unused volumes
docker volume prune -f

# Check disk usage
docker system df
```

### Issue 5: Slow Image Build

**Solution**: Use a faster mirror for pip packages

```dockerfile
# In Dockerfile, add:
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir ...
```

---

## 🔧 Advanced Configuration

### Custom Ports

Edit `docker-compose.yml`:
```yaml
services:
  api:
    ports:
      - "8080:8000"  # Use 8080 instead of 8000
  ui:
    ports:
      - "8502:8501"  # Use 8502 instead of 8501
```

### Environment Variables

Edit `docker-compose.yml`:
```yaml
services:
  api:
    environment:
      - LOG_LEVEL=DEBUG
      - MAX_WORKERS=4
```

### Persistent Data

Edit `docker-compose.yml`:
```yaml
services:
  api:
    volumes:
      - ./data:/app/data
      - ./models:/app/models
```

---

## 📝 License

MIT License

---

## 🙏 Acknowledgments

- [TensorFlow Extended (TFX)](https://www.tensorflow.org/tfx)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Streamlit](https://streamlit.io/)
- [Docker](https://www.docker.com/)

---

**Last Updated**: 2025-10-14  
**Version**: 2.0.0  
**Status**: ✅ Production Ready
