#!/bin/bash

# Complete Kubernetes MLOps Platform Deployment Script
# Ensures reproducible deployment on ARM64 Mac environments

set -e

echo "🚀 Starting Complete MLOps Platform Deployment on Kubernetes..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command -v /opt/homebrew/bin/minikube &> /dev/null; then
    print_error "minikube not found. Please install with: brew install minikube"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found. Please install kubectl"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    print_error "docker not found. Please install Docker Desktop"
    exit 1
fi

print_success "All prerequisites found"

# Start minikube if not running
print_status "Checking minikube status..."
if ! /opt/homebrew/bin/minikube status &> /dev/null; then
    print_status "Starting minikube..."
    /opt/homebrew/bin/minikube start --memory=8192 --cpus=4
    print_success "minikube started"
else
    print_success "minikube is already running"
fi

# Verify cluster connection
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster"
    exit 1
fi

print_success "Kubernetes cluster connection verified"

# Create namespace
print_status "Creating mlops-system namespace..."
kubectl create namespace mlops-system --dry-run=client -o yaml | kubectl apply -f -

# Deploy services in order
print_status "Deploying Kafka and Zookeeper..."
kubectl apply -f k8s/kafka-deployment.yaml
print_success "Kafka and Zookeeper deployed"

print_status "Deploying Redis..."
kubectl apply -f k8s/redis-deployment.yaml
print_success "Redis deployed"

print_status "Deploying MLflow..."
kubectl apply -f k8s/mlflow-deployment.yaml
print_success "MLflow deployed"

print_status "Deploying Feast..."
kubectl apply -f k8s/feast-deployment.yaml
print_success "Feast deployed"

print_status "Deploying MLMD with MySQL..."
kubectl apply -f k8s/mlmd-deployment.yaml
print_success "MLMD and MySQL deployed"

print_status "Deploying FastAPI and Streamlit applications..."
kubectl apply -f k8s/app-deployment.yaml
print_success "Applications deployed"

# Wait for pods to be ready
print_status "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=kafka -n mlops-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n mlops-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=mlflow -n mlops-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=mysql -n mlops-system --timeout=300s

print_status "Waiting for applications to be ready (this may take a few minutes)..."
sleep 30

# Check deployment status
print_status "Checking deployment status..."
kubectl get pods -n mlops-system

# Get service information
print_status "Service information:"
kubectl get services -n mlops-system

print_success "🎉 MLOps Platform deployment completed!"

echo ""
echo "📋 Next Steps:"
echo "1. Set up port forwarding to access services:"
echo "   kubectl port-forward service/fastapi-service 8000:8000 -n mlops-system &"
echo "   kubectl port-forward service/streamlit-service 8501:8501 -n mlops-system &"
echo "   kubectl port-forward service/mlflow-service 5000:5000 -n mlops-system &"
echo "   kubectl port-forward service/feast-service 8888:8888 -n mlops-system &"
echo ""
echo "2. Access the services:"
echo "   - FastAPI: http://localhost:8000"
echo "   - FastAPI Docs: http://localhost:8000/docs"
echo "   - Streamlit UI: http://localhost:8501"
echo "   - MLflow UI: http://localhost:5000"
echo "   - Feast UI: http://localhost:8888"
echo ""
echo "3. Test the API:"
echo "   curl -X POST http://localhost:8000/predict \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"pickup_longitude\": -73.9857, \"pickup_latitude\": 40.7484, \"dropoff_longitude\": -73.9757, \"dropoff_latitude\": 40.7584, \"passenger_count\": 2, \"trip_miles\": 1.5, \"trip_seconds\": 420, \"pickup_hour\": 14, \"pickup_day_of_week\": 3}'"
echo ""
echo "4. Check health:"
echo "   curl http://localhost:8000/health"
echo ""
echo "📖 For detailed documentation, see: docs/K8S_DEPLOYMENT_GUIDE.md"
