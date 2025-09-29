#!/bin/bash

# Port Forwarding Setup Script for MLOps Platform
# Run this after successful deployment to access all services

set -e

echo "🔗 Setting up port forwarding for MLOps services..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Kill existing port forwards
print_status "Cleaning up existing port forwards..."
pkill -f "kubectl.*port-forward" || true
sleep 2

# Set up port forwarding for all services
print_status "Setting up FastAPI port forwarding (8000)..."
kubectl port-forward service/fastapi-service 8000:8000 -n mlops-system > /dev/null 2>&1 &
FASTAPI_PID=$!

print_status "Setting up Streamlit port forwarding (8501)..."
kubectl port-forward service/streamlit-service 8501:8501 -n mlops-system > /dev/null 2>&1 &
STREAMLIT_PID=$!

print_status "Setting up MLflow port forwarding (5000)..."
kubectl port-forward service/mlflow-service 5000:5000 -n mlops-system > /dev/null 2>&1 &
MLFLOW_PID=$!

print_status "Setting up Feast port forwarding (8888)..."
kubectl port-forward service/feast-service 8888:8888 -n mlops-system > /dev/null 2>&1 &
FEAST_PID=$!

# Wait a moment for port forwards to establish
sleep 3

print_success "Port forwarding setup complete!"

echo ""
echo "🌐 Access URLs:"
echo "   - FastAPI API: http://localhost:8000"
echo "   - FastAPI Docs: http://localhost:8000/docs"
echo "   - Streamlit UI: http://localhost:8501"
echo "   - MLflow UI: http://localhost:5000"
echo "   - Feast UI: http://localhost:8888"
echo ""
echo "📊 Process IDs:"
echo "   - FastAPI: $FASTAPI_PID"
echo "   - Streamlit: $STREAMLIT_PID"
echo "   - MLflow: $MLFLOW_PID"
echo "   - Feast: $FEAST_PID"
echo ""
echo "🛑 To stop all port forwarding:"
echo "   pkill -f \"kubectl.*port-forward\""
echo ""
echo "✅ Port forwarding is now active. Keep this terminal open."

# Keep script running to maintain port forwards
trap 'echo "Stopping port forwards..."; kill $FASTAPI_PID $STREAMLIT_PID $MLFLOW_PID $FEAST_PID 2>/dev/null; exit' INT TERM

wait
