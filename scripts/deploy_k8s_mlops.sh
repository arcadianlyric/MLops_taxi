#!/bin/bash
# Kubernetes MLOps Platform Deployment Script
# Deploys real Kafka, Feast, MLflow, MLMD services

set -e

echo "🚀 部署 Kubernetes MLOps 平台..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl 未找到，请安装 kubectl"
    exit 1
fi

# Check if Docker Desktop Kubernetes is running
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Kubernetes 集群未运行，请启动 Docker Desktop 并启用 Kubernetes"
    exit 1
fi

echo "✅ Kubernetes 集群连接正常"

# Create namespace
echo "📦 创建命名空间..."
kubectl apply -f k8s/kafka-deployment.yaml

# Wait for namespace to be ready
kubectl wait --for=condition=Ready namespace/mlops-system --timeout=60s

# Deploy infrastructure services
echo "🔧 部署基础设施服务..."

# Deploy Redis (for Feast)
echo "  - 部署 Redis..."
kubectl apply -f k8s/redis-deployment.yaml

# Deploy Kafka + Zookeeper
echo "  - 部署 Kafka + Zookeeper..."
kubectl apply -f k8s/kafka-deployment.yaml

# Deploy MySQL (for MLMD)
echo "  - 部署 MySQL..."
kubectl apply -f k8s/mlmd-deployment.yaml

# Wait for infrastructure to be ready
echo "⏳ 等待基础设施服务启动..."
kubectl wait --for=condition=available --timeout=300s deployment/redis -n mlops-system
kubectl wait --for=condition=available --timeout=300s deployment/zookeeper -n mlops-system
kubectl wait --for=condition=available --timeout=300s deployment/kafka -n mlops-system
kubectl wait --for=condition=available --timeout=300s deployment/mysql -n mlops-system

echo "✅ 基础设施服务已就绪"

# Deploy MLOps services
echo "🎯 部署 MLOps 服务..."

# Deploy MLflow
echo "  - 部署 MLflow..."
kubectl apply -f k8s/mlflow-deployment.yaml

# Deploy Feast
echo "  - 部署 Feast..."
kubectl apply -f k8s/feast-deployment.yaml

# Deploy MLMD
echo "  - 部署 MLMD..."
kubectl apply -f k8s/mlmd-deployment.yaml

# Wait for MLOps services
echo "⏳ 等待 MLOps 服务启动..."
kubectl wait --for=condition=available --timeout=300s deployment/mlflow -n mlops-system
kubectl wait --for=condition=available --timeout=300s deployment/feast -n mlops-system
kubectl wait --for=condition=available --timeout=300s deployment/mlmd -n mlops-system

echo "✅ MLOps 服务已就绪"

# Create ConfigMap for application source code
echo "📁 创建应用源码 ConfigMap..."
kubectl create configmap app-source \
  --from-file=. \
  --namespace=mlops-system \
  --dry-run=client -o yaml | kubectl apply -f -

# Deploy application services
echo "🌐 部署应用服务..."
kubectl apply -f k8s/app-deployment.yaml

# Wait for application services
echo "⏳ 等待应用服务启动..."
kubectl wait --for=condition=available --timeout=300s deployment/fastapi -n mlops-system
kubectl wait --for=condition=available --timeout=300s deployment/streamlit -n mlops-system

echo "✅ 应用服务已就绪"

# Get service information
echo ""
echo "🎉 MLOps 平台部署完成！"
echo ""
echo "📊 服务访问信息:"

# Check if services are LoadBalancer or NodePort
FASTAPI_TYPE=$(kubectl get svc fastapi-service -n mlops-system -o jsonpath='{.spec.type}')
STREAMLIT_TYPE=$(kubectl get svc streamlit-service -n mlops-system -o jsonpath='{.spec.type}')

if [[ "$FASTAPI_TYPE" == "LoadBalancer" ]]; then
    echo "  - FastAPI: 等待外部 IP 分配..."
    kubectl get svc fastapi-service -n mlops-system
else
    echo "  - FastAPI: kubectl port-forward svc/fastapi-service -n mlops-system 8000:8000"
fi

if [[ "$STREAMLIT_TYPE" == "LoadBalancer" ]]; then
    echo "  - Streamlit: 等待外部 IP 分配..."
    kubectl get svc streamlit-service -n mlops-system
else
    echo "  - Streamlit: kubectl port-forward svc/streamlit-service -n mlops-system 8501:8501"
fi

echo ""
echo "🔧 其他服务端口转发命令:"
echo "  - MLflow: kubectl port-forward svc/mlflow-service -n mlops-system 5000:5000"
echo "  - Feast UI: kubectl port-forward svc/feast-service -n mlops-system 8888:8888"
echo "  - Kafka: kubectl port-forward svc/kafka-service -n mlops-system 9092:9092"
echo "  - Redis: kubectl port-forward svc/redis-service -n mlops-system 6379:6379"
echo ""
echo "📋 检查部署状态:"
echo "  kubectl get pods -n mlops-system"
echo "  kubectl get svc -n mlops-system"
echo ""
echo "🔍 查看日志:"
echo "  kubectl logs -f deployment/fastapi -n mlops-system"
echo "  kubectl logs -f deployment/streamlit -n mlops-system"
echo ""
echo "🛑 清理部署:"
echo "  kubectl delete namespace mlops-system"
echo ""

# Show current status
echo "当前 Pod 状态:"
kubectl get pods -n mlops-system

echo ""
echo "当前服务状态:"
kubectl get svc -n mlops-system

echo ""
echo "🎊 MLOps 平台已成功部署到 Kubernetes！"
