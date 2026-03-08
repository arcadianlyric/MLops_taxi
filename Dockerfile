# Unified Dockerfile for Taxi App (API + UI + ML Model + MLflow)
FROM python:3.9-slim

WORKDIR /app

# Install all dependencies (no TF in container – sklearn serves predictions,
# TF model training runs natively; see api/train_tf_model.py)
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    numpy==1.26.0 \
    streamlit==1.28.0 \
    requests==2.31.0 \
    plotly==5.17.0 \
    pandas==2.1.1 \
    scikit-learn==1.3.2 \
    joblib==1.3.2 \
    mlflow==2.9.2 \
    prometheus-fastapi-instrumentator==6.1.0 \
    prometheus-client==0.19.0

# Copy source code
COPY api/ /app/api/
COPY ui/ /app/ui/
COPY tfx_pipeline/data/simple/data.csv /app/tfx_pipeline/data/simple/data.csv

# Train sklearn model inside container (ensures version compatibility)
RUN python3 /app/api/train_model.py

EXPOSE 8000 8501 5000
