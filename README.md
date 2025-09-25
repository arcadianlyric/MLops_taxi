# Enterprise MLOps Platform with TFX Pipeline (macOS)

A complete MLOps platform built on existing `tfx_pipeline` code, integrating Kubeflow, Feast, KFServing, monitoring, and stream processing capabilities.

## 🏗️ Architecture Overview

- **Core Dataset**: Chicago Taxi (based on tfx_pipeline/taxi_pipeline_native_keras.py)
- **Orchestration Layer**: Kubeflow Pipelines
- **ML Framework**: TensorFlow Extended (TFX)
- **Execution Engine**: Apache Beam (supports local/Dataflow/Spark)
- **Feature Store**: Feast
- **Model Serving**: KFServing
- **Stream Processing**: Kafka Kraft
- **Monitoring**: Loki + Grafana + Prometheus
- **Frontend**: Streamlit
- **API**: FastAPI

## 🚀 quick start (local)

### requirements
- Python 3.9+
- macOS 
- 8GB+ RAM

### start
```bash
# 1. clone repo
git clone <your-repo>
cd MLops_test

# 2. start
./quick_start.sh
```

visit：
- **Streamlit UI**: http://localhost:8501
- **FastAPI**: http://localhost:8000/docs
- **health**: http://localhost:8000/health

## ⚡ Apache Beam Execution Engine

TFX Pipeline uses **Apache Beam** as the underlying distributed execution engine, supporting multiple runtime modes:

### Execution Modes
- **DirectRunner**: Local single-machine execution, suitable for development and testing
- **DataflowRunner**: Google Cloud Dataflow, suitable for production environments
- **SparkRunner**: Apache Spark cluster, suitable for existing Spark infrastructure
- **FlinkRunner**: Apache Flink cluster, suitable for stream-batch unified scenarios

### Configuration Examples
```python
# Local development
beam_pipeline_args = ['--runner=DirectRunner']

# Production environment (Google Cloud)
beam_pipeline_args = [
    '--runner=DataflowRunner',
    '--project=your-gcp-project',
    '--region=us-central1'
]

# Spark cluster
beam_pipeline_args = [
    '--runner=SparkRunner',
    '--spark-master=spark://localhost:7077'
]
```

## 🔧 manual install


### 1. create virtual environment
```bash
python3 -m venv mlops-env
source mlops-env/bin/activate
pip install --upgrade pip
```

### 2. dependencies
```bash
pip install -r requirements-local.txt
```

### 3. start service
```bash
# start FastAPI backend (terminal 1)
uvicorn api.main_with_feast:app --host 0.0.0.0 --port 8000 --reload

# start Streamlit frontend (terminal 2)
streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true
```

### 4. validation
```bash
# check API health
curl http://localhost:8000/health

# test interface
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_miles": 5.2,
    "trip_seconds": 1200,
    "pickup_latitude": 41.8781,
    "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881,
    "dropoff_longitude": -87.6198,
    "pickup_hour": 8,
    "pickup_day_of_week": 1,
    "passenger_count": 2,
    "company": "Yellow Cab"
  }'
```

## 📁 Project Structure

```
├── tfx_pipeline/           # Base TFX code (Taxi dataset)
│   ├── taxi_pipeline_native_keras.py
│   ├── taxi_utils_native_keras.py
│   └── data/
├── pipelines/              # Kubeflow integrated TFX pipelines
│   └── taxi_kubeflow_pipeline.py
├── components/             # Custom TFX components
│   ├── feast_feature_pusher.py
│   ├── kfserving_deployer.py
│   └── model_monitoring.py
├── api/                    # FastAPI backend
├── ui/                     # Streamlit frontend
│   └── streamlit_app.py
├── streaming/              # Kafka stream processing
│   └── kafka_processor.py
├── feast/                  # Feast feature store
├── k8s/                    # Kubernetes configurations
├── scripts/                # Deployment scripts
│   ├── deploy_complete_mlops.sh
│   ├── deploy_kfserving.sh
│   ├── test_inference.py
│   └── stop_mlops.sh
└── requirements.txt        # Python dependencies
```

## 🔧 Core Components

### TFX Pipeline-based ML Workflow
- **Data Source**: Chicago Taxi dataset (tfx_pipeline/data)
- **Data Validation**: Data processing based on taxi_utils_native_keras.py
- **Feature Engineering**: Integrated with Feast feature store
- **Model Training**: Native Keras model training
- **Model Evaluation**: TensorFlow Model Analysis
- **Model Deployment**: KFServing online inference

### Enterprise Extension Components
- **Feast Feature Pusher**: Automatically push TFX features to Feast
- **KFServing Deployment**: Automated model deployment and version management
- **Model Monitoring**: Prometheus + Grafana + Loki integration
- **Stream Processing**: Kafka real-time data processing

### User Interface
- **Streamlit UI**: Interactive model inference and monitoring dashboard
- **FastAPI**: RESTful API service
- **Online Inference**: Supports single, batch, and asynchronous inference

## 🎯 Usage

### 1. Access Services
- **Streamlit UI**: http://localhost:8501
- **FastAPI Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 2. Monitoring Dashboard
```bash
# Access Grafana (admin/admin123)
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Access Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

### 3. Test Inference
```bash
# Run inference test
python scripts/test_inference.py

# Or test Chicago Taxi prediction via API
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_miles": 5.2,
    "trip_seconds": 1200,
    "pickup_latitude": 41.8781,
    "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881,
    "dropoff_longitude": -87.6198,
    "pickup_hour": 8,
    "pickup_day_of_week": 1,
    "passenger_count": 2,
    "company": "Yellow Cab"
  }'
```

### 4. Management Commands
```bash
# Stop all services
./scripts/stop_mlops.sh

# View logs
tail -f *.log

# Check Kubernetes status
kubectl get pods --all-namespaces
```

## 📊 Monitoring and Alerting

The platform includes a comprehensive monitoring system:
- **Pipeline Execution Metrics**: TFX component runtime status
- **Model Performance Monitoring**: Accuracy, latency, throughput
- **Data Drift Detection**: Feature distribution change monitoring
- **Infrastructure Monitoring**: CPU, memory, network utilization
- **Business Metrics**: Custom business KPIs

## 🔧 Troubleshooting

### Log Viewing
```bash
# Application logs
tail -f fastapi.log
tail -f streamlit.log
tail -f kafka.log

# Kubernetes logs
kubectl logs -n mlops-system deployment/kafka
kubectl logs -n monitoring deployment/prometheus
```
