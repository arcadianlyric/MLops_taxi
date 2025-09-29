#!/bin/bash
# Test script for Kubernetes MLOps services

set -e

echo "🧪 测试 Kubernetes MLOps 服务..."

# Check if services are running
echo "📊 检查服务状态..."
kubectl get pods -n mlops-system

echo ""
echo "🔍 测试各个服务连接..."

# Test Kafka
echo "  - 测试 Kafka..."
kubectl exec -n mlops-system deployment/kafka -- kafka-topics --bootstrap-server localhost:9092 --list || echo "Kafka 连接失败"

# Test Redis
echo "  - 测试 Redis..."
kubectl exec -n mlops-system deployment/redis -- redis-cli ping || echo "Redis 连接失败"

# Test MLflow
echo "  - 测试 MLflow..."
kubectl port-forward svc/mlflow-service -n mlops-system 5000:5000 &
MLFLOW_PID=$!
sleep 5
curl -s http://localhost:5000/health || curl -s http://localhost:5000 || echo "MLflow 连接失败"
kill $MLFLOW_PID 2>/dev/null || true

# Test FastAPI
echo "  - 测试 FastAPI..."
kubectl port-forward svc/fastapi-service -n mlops-system 8000:8000 &
FASTAPI_PID=$!
sleep 5
curl -s http://localhost:8000/health || echo "FastAPI 连接失败"
kill $FASTAPI_PID 2>/dev/null || true

echo ""
echo "✅ 服务测试完成"
