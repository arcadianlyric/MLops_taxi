#!/bin/bash

# 完整的TFX Pipeline + UI部署脚本
# 使用minikube实现K8s部署，训练模型并在UI中返回tip预测

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

MINIKUBE=/opt/homebrew/bin/minikube

print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

cd "$(dirname "$0")/.."

print_header "🚀 完整TFX Pipeline + UI部署"

# ============================================
# 第1步: 启动Minikube
# ============================================
print_header "第1步: 启动Minikube"

if $MINIKUBE status &> /dev/null; then
    print_success "Minikube已运行"
else
    print_status "启动minikube..."
    $MINIKUBE start --driver=docker --memory=4096 --cpus=2
    print_success "Minikube启动成功"
fi

kubectl config use-context minikube
print_success "kubectl context设置为minikube"

# ============================================
# 第2步: 检查和安装依赖
# ============================================
print_header "第2步: 检查Python依赖"

print_status "检查TFX依赖..."
if ! python3 -c "import tfx" &> /dev/null; then
    print_status "安装TFX 1.14.0及兼容依赖..."
    pip3 install -r tfx-requirements.txt || {
        print_error "依赖安装失败"
        exit 1
    }
    print_success "依赖安装完成"
else
    print_success "TFX依赖已安装"
fi

# ============================================
# 第3步: 训练TFX模型
# ============================================
print_header "第3步: 训练TFX模型"

print_status "运行TFX pipeline训练模型..."
python3 tfx_pipeline/taxi_pipeline_native_keras.py || {
    print_error "TFX pipeline运行失败"
    exit 1
}
print_success "TFX模型训练完成"

# 检查模型输出
if [ -d "tfx_pipeline/serving_model/chicago_taxi_native_keras" ]; then
    print_success "模型已保存到serving_model目录"
    ls -la tfx_pipeline/serving_model/chicago_taxi_native_keras/
else
    print_error "模型文件未找到"
    exit 1
fi

# ============================================
# 第4步: 构建Docker镜像
# ============================================
print_header "第4步: 构建Docker镜像"

print_status "配置Docker使用minikube..."
eval $($MINIKUBE docker-env)

print_status "构建包含TFX模型的应用镜像..."
docker build -f Dockerfile.app -t taxi-app:latest .
print_success "Docker镜像构建成功"

# ============================================
# 第5步: 部署到Kubernetes
# ============================================
print_header "第5步: 部署到Kubernetes"

print_status "清理旧部署..."
kubectl delete namespace taxi-app --ignore-not-found=true
sleep 5

print_status "应用Kubernetes配置..."
kubectl apply -f k8s/taxi-app-simple.yaml
print_success "Kubernetes配置应用成功"

# ============================================
# 第6步: 等待服务就绪
# ============================================
print_header "第6步: 等待服务就绪"

sleep 10

print_status "等待FastAPI Pod..."
kubectl wait --for=condition=ready pod -l app=fastapi -n taxi-app --timeout=180s
print_success "FastAPI Pod就绪"

print_status "等待Streamlit Pod..."
kubectl wait --for=condition=ready pod -l app=streamlit -n taxi-app --timeout=180s
print_success "Streamlit Pod就绪"

# ============================================
# 第7步: 获取访问地址
# ============================================
print_header "第7步: 获取访问地址"

FASTAPI_URL=$($MINIKUBE service fastapi-service -n taxi-app --url)
STREAMLIT_URL=$($MINIKUBE service streamlit-service -n taxi-app --url)

print_success "FastAPI URL: $FASTAPI_URL"
print_success "Streamlit URL: $STREAMLIT_URL"

sleep 5

# ============================================
# 第8步: 测试Tip预测
# ============================================
print_header "第8步: 测试Tip预测功能"

TEST_DATA='{
    "trip_miles": 5.2,
    "trip_seconds": 900,
    "fare": 12.5,
    "pickup_latitude": 41.8781,
    "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881,
    "dropoff_longitude": -87.6198,
    "pickup_hour": 14,
    "pickup_day_of_week": 1,
    "trip_start_day": 15,
    "trip_start_month": 6,
    "pickup_community_area": 8,
    "dropoff_community_area": 24,
    "pickup_census_tract": 170301,
    "dropoff_census_tract": 170401,
    "payment_type": "Credit Card",
    "company": "Flash Cab",
    "passenger_count": 1
}'

print_status "发送测试请求..."
RESPONSE=$(curl -s -X POST ${FASTAPI_URL}/predict \
    -H "Content-Type: application/json" \
    -d "$TEST_DATA")

if echo "$RESPONSE" | grep -q "predicted_tip"; then
    print_success "✅ Tip预测成功！"
    echo "$RESPONSE" | python3 -m json.tool
    
    PREDICTED_TIP=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['predicted_tip'])" 2>/dev/null)
    echo ""
    echo -e "${GREEN}💰 预测的Tip金额: \$${PREDICTED_TIP}${NC}"
else
    print_error "Tip预测失败"
    echo "响应: $RESPONSE"
fi

# ============================================
# 完成
# ============================================
print_header "🎉 部署完成"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}部署成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}📊 访问地址:${NC}"
echo -e "${GREEN}  Streamlit UI:  $STREAMLIT_URL${NC}"
echo -e "${GREEN}  FastAPI:       $FASTAPI_URL${NC}"
echo -e "${GREEN}  API文档:       $FASTAPI_URL/docs${NC}"
echo ""
echo -e "${YELLOW}🎯 使用说明:${NC}"
echo "  1. 打开浏览器访问: $STREAMLIT_URL"
echo "  2. 在UI中输入行程信息"
echo "  3. 点击'🚕 Predict Tip'按钮"
echo "  4. 查看基于TFX训练模型的tip预测结果"
echo ""
echo -e "${YELLOW}📝 模型信息:${NC}"
echo "  训练数据: tfx_pipeline/data/simple/data.csv"
echo "  Pipeline: taxi_pipeline_native_keras.py"
echo "  模型路径: tfx_pipeline/serving_model/"
echo ""
