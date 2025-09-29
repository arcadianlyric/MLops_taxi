#!/bin/bash

# 快速部署测试脚本 - 不包含TFX训练
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

MINIKUBE=/opt/homebrew/bin/minikube

print_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

cd "$(dirname "$0")/.."

print_header "🚀 快速部署测试"

# 1. 检查minikube
print_status "检查minikube..."
if ! $MINIKUBE status &> /dev/null; then
    print_status "启动minikube..."
    $MINIKUBE start --driver=docker --memory=4096 --cpus=2
fi
print_success "Minikube运行中"

kubectl config use-context minikube

# 2. 配置Docker环境
print_status "配置Docker环境..."
eval $($MINIKUBE docker-env)
print_success "Docker环境配置完成"

# 3. 构建镜像
print_status "构建Docker镜像..."
docker build -f Dockerfile.app -t taxi-app:latest .
print_success "镜像构建完成"

# 4. 部署
print_status "部署到Kubernetes..."
kubectl delete namespace taxi-app --ignore-not-found=true
sleep 5
kubectl apply -f k8s/taxi-app-simple.yaml
print_success "部署完成"

# 5. 等待Pod就绪
print_status "等待Pod启动..."
sleep 10
kubectl wait --for=condition=ready pod -l app=fastapi -n taxi-app --timeout=180s
kubectl wait --for=condition=ready pod -l app=streamlit -n taxi-app --timeout=180s
print_success "所有Pod就绪"

# 6. 获取URL
print_status "获取服务URL..."
FASTAPI_URL=$($MINIKUBE service fastapi-service -n taxi-app --url)
STREAMLIT_URL=$($MINIKUBE service streamlit-service -n taxi-app --url)

echo ""
print_success "FastAPI: $FASTAPI_URL"
print_success "Streamlit: $STREAMLIT_URL"

# 7. 测试API
sleep 5
print_status "测试API..."
RESPONSE=$(curl -s ${FASTAPI_URL}/health)
if echo "$RESPONSE" | grep -q "healthy"; then
    print_success "API健康检查通过"
else
    print_error "API健康检查失败"
fi

# 8. 测试预测
print_status "测试Tip预测..."
TEST_DATA='{
    "trip_miles": 5.2, "trip_seconds": 900, "fare": 12.5,
    "pickup_latitude": 41.8781, "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881, "dropoff_longitude": -87.6198,
    "pickup_hour": 14, "pickup_day_of_week": 1,
    "trip_start_day": 15, "trip_start_month": 6,
    "pickup_community_area": 8, "dropoff_community_area": 24,
    "pickup_census_tract": 170301, "dropoff_census_tract": 170401,
    "payment_type": "Credit Card", "company": "Flash Cab", "passenger_count": 1
}'

PRED_RESPONSE=$(curl -s -X POST ${FASTAPI_URL}/predict -H "Content-Type: application/json" -d "$TEST_DATA")
if echo "$PRED_RESPONSE" | grep -q "predicted_tip"; then
    print_success "Tip预测成功"
    TIP=$(echo "$PRED_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['predicted_tip'])" 2>/dev/null)
    echo -e "${GREEN}💰 预测Tip: \$${TIP}${NC}"
else
    print_error "Tip预测失败"
fi

print_header "🎉 部署完成"
echo ""
echo -e "${GREEN}访问地址:${NC}"
echo -e "  Streamlit UI: ${STREAMLIT_URL}"
echo -e "  FastAPI:      ${FASTAPI_URL}"
echo -e "  API文档:      ${FASTAPI_URL}/docs"
echo ""
echo -e "${BLUE}在浏览器中打开 Streamlit UI 即可使用！${NC}"
