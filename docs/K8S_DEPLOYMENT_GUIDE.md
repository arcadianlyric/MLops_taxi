# Kubernetes MLOps Platform Deployment Guide

## Overview
This guide provides step-by-step instructions for deploying the complete MLOps platform on Kubernetes using minikube, including specific fixes to ensure reproducibility on ARM64 Mac environments.

## Prerequisites
- Docker Desktop installed and running
- minikube installed (`brew install minikube`)
- kubectl installed
- At least 8GB RAM available for minikube

## Architecture
The platform consists of the following services:
- **Kafka + Zookeeper**: Stream processing
- **Redis**: Feast online feature store
- **MySQL**: MLMD metadata storage
- **MLflow**: Model lifecycle management
- **Feast**: Feature store service
- **MLMD**: ML Metadata and lineage tracking
- **FastAPI**: ML prediction API
- **Streamlit**: Web UI for predictions

## Deployment Steps

### 1. Start minikube
Ensure minikube has sufficient resources.
```bash
/opt/homebrew/bin/minikube start --memory=8192
```

### 2. Create Image Pull Secret (for ghcr.io)
This is required to pull the ARM64-compatible MLMD image.

**a. Create a GitHub Personal Access Token (PAT)**
1.  Navigate to **[github.com/settings/tokens](https://github.com/settings/tokens)**.
2.  Click **Generate new token** and select **Generate new token (classic)**.
3.  Give the token a name (e.g., `k8s-image-pull`).
4.  Select the **`read:packages`** scope.
5.  Click **Generate token** and copy the token.

**b. Create the Kubernetes Secret**
Replace `YOUR_GITHUB_USERNAME` and `YOUR_PAT` in the command below:
```bash
/opt/homebrew/bin/minikube kubectl -- create secret docker-registry ghcr-creds \
  --namespace mlops-system \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_PAT
```

### 3. Deploy Infrastructure Services
Apply the Kubernetes manifests for all services.
```bash
# Deploy Kafka and Zookeeper
kubectl apply -f k8s/kafka-deployment.yaml

# Deploy Redis for Feast
kubectl apply -f k8s/redis-deployment.yaml

# Deploy MLflow
kubectl apply -f k8s/mlflow-deployment.yaml

# Deploy Feast
kubectl apply -f k8s/feast-deployment.yaml

# Deploy MLMD with MySQL
kubectl apply -f k8s/mlmd-deployment.yaml

# Deploy Applications (FastAPI and Streamlit)
kubectl apply -f k8s/app-deployment.yaml
```

### 4. Verify Deployment
Check that all pods are in the `Running` state. Note that MLMD may initially show `ErrImagePull` before the secret is applied.
```bash
kubectl get pods -n mlops-system
```

### 5. Set Up Port Forwarding
Use separate terminal sessions for each port-forward command.
```bash
# Streamlit UI (Port 8501)
kubectl port-forward service/streamlit-service 8501:8501 -n mlops-system

# FastAPI (Port 8000)
kubectl port-forward service/fastapi-service 8000:8000 -n mlops-system

# MLflow UI (Port 5000)
kubectl port-forward service/mlflow-service 5000:5000 -n mlops-system
```

## Troubleshooting and Advanced Configuration

### MLMD on ARM64: The Fix
The official MLMD images are not ARM64-compatible. We use a pre-built image from the `deployKF` project.

**`k8s/mlmd-deployment.yaml`:**
```yaml
spec:
  containers:
  - name: mlmd
    image: ghcr.io/deploykf/ml-metadata/ml_metadata_store_server:1.14.0-deploykf.2
    # ... args
```
To use this image, the `ghcr-creds` secret must be referenced in the deployment:
```yaml
spec:
  template:
    spec:
      imagePullSecrets:
      - name: ghcr-creds
      containers:
      # ...
```

### Real-time UI Service Monitoring
By default, the Kubernetes UI shows "simulated" service statuses. To enable real-time health checks:

1.  **Update FastAPI**: The `health` endpoint in `k8s/app-deployment.yaml` was modified to actively check connections to Kafka, MLflow, Feast, etc.
2.  **Update Streamlit UI**: The UI code in `k8s/app-deployment.yaml` was updated to parse the new health data and display colored status indicators.
3.  **Restart Pods**: After applying changes to `app-deployment.yaml`, you must force a restart of the `fastapi` and `streamlit` pods for the changes to take effect:
    ```bash
    kubectl delete pod -l app=fastapi -n mlops-system
    kubectl delete pod -l app=streamlit -n mlops-system
    ```

### Pod `ImagePullBackOff` Error
This error means Kubernetes cannot download the container image. For `ghcr.io`, this is an authentication issue. Ensure the `ghcr-creds` secret was created correctly and is referenced in the pod's `imagePullSecrets`.

## Access URLs
- **Streamlit UI**: http://localhost:8501
- **FastAPI Docs**: http://localhost:8000/docs
- **MLflow UI**: http://localhost:5000

## Cleanup
```bash
# Delete all resources
kubectl delete namespace mlops-system

# Stop minikube
minikube stop
```
