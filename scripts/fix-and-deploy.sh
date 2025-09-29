#!/bin/bash

# 完整的K8s诊断、修复和部署脚本
set +e  # 允许命令失败以便诊断

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Taxi Tip预测应用 - K8s部署${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================
# 第1步: 诊断和修复K8s连接
# ============================================
print_status "第1步: 诊断Kubernetes环境..."
echo ""

# 检查Docker
print_status "检查Docker..."
if ! command -v docker &> /dev/null; then
    print_error "Docker未安装"
    echo "请安装Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    print_error "Docker未运行"
    echo "请启动Docker Desktop应用"
    exit 1
fi
print_success "Docker运行正常"

# 检查kubectl
print_status "检查kubectl..."
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl未安装"
    echo "安装kubectl: brew install kubectl"
    exit 1
fi
print_success "kubectl已安装"

# 检查K8s连接
print_status "检查Kubernetes集群连接..."
if kubectl cluster-info &> /dev/null; then
    print_success "Kubernetes集群连接正常"
else
    print_warning "无法连接到Kubernetes集群，尝试修复..."
    
    # 显示可用contexts
    print_status "可用的kubectl contexts:"
    kubectl config get-contexts
    
    # 尝试切换到docker-desktop
    print_status "切换到docker-desktop context..."
    kubectl config use-context docker-desktop 2>/dev/null
    
    sleep 3
    
    # 再次检查
    if kubectl cluster-info &> /dev/null; then
        print_success "成功连接到Kubernetes集群"
    else
        print_error "仍然无法连接到Kubernetes集群"
        echo ""
        echo "请按以下步骤启用Kubernetes:"
        echo "  1. 打开Docker Desktop"
        echo "  2. 点击右上角设置图标"
        echo "  3. 选择 'Kubernetes' 标签"
        echo "  4. 勾选 'Enable Kubernetes'"
        echo "  5. 点击 'Apply & Restart'"
        echo "  6. 等待Kubernetes启动（可能需要几分钟）"
        echo ""
        read -p "完成后按Enter继续，或按Ctrl+C退出..." 
        
        # 等待用户操作后再次检查
        if kubectl cluster-info &> /dev/null; then
            print_success "Kubernetes集群现在可用"
        else
            print_error "仍然无法连接，请检查Docker Desktop Kubernetes设置"
            exit 1
        fi
    fi
fi

echo ""
kubectl cluster-info
echo ""

# ============================================
# 第2步: 构建Docker镜像
# ============================================
print_status "第2步: 构建Docker镜像..."
echo ""

cd "$(dirname "$0")/.."

# 检查必要文件
if [[ ! -f "api/taxi_simple_api.py" ]]; then
    print_error "api/taxi_simple_api.py 不存在"
    exit 1
fi

if [[ ! -f "Dockerfile.app" ]]; then
    print_error "Dockerfile.app 不存在"
    exit 1
fi

# 构建镜像
print_status "构建taxi-app镜像..."
docker build -f Dockerfile.app -t taxi-app:latest . || {
    print_error "Docker镜像构建失败"
    exit 1
}

print_success "Docker镜像构建成功"
docker images | grep taxi-app

echo ""

# ============================================
# 第3步: 部署到Kubernetes
# ============================================
print_status "第3步: 部署到Kubernetes..."
echo ""

# 清理旧部署
print_status "清理旧部署..."
kubectl delete namespace taxi-app --ignore-not-found=true
sleep 5

# 部署新应用
print_status "应用Kubernetes配置..."
kubectl apply -f k8s/taxi-app-simple.yaml || {
    print_error "部署失败"
    exit 1
}

print_success "Kubernetes配置已应用"

echo ""

# ============================================
# 第4步: 等待Pod就绪
# ============================================
print_status "第4步: 等待Pod启动..."
echo ""

# 等待namespace创建
sleep 3

# 显示Pod状态
print_status "当前Pod状态:"
kubectl get pods -n taxi-app

echo ""
print_status "等待FastAPI Pod就绪..."
kubectl wait --for=condition=ready pod -l app=fastapi -n taxi-app --timeout=180s || {
    print_error "FastAPI Pod启动超时"
    echo ""
    print_status "Pod详情:"
    kubectl describe pod -l app=fastapi -n taxi-app
    echo ""
    print_status "Pod日志:"
    kubectl logs -l app=fastapi -n taxi-app --tail=50
    exit 1
}

print_status "等待Streamlit Pod就绪..."
kubectl wait --for=condition=ready pod -l app=streamlit -n taxi-app --timeout=180s || {
    print_error "Streamlit Pod启动超时"
    echo ""
    print_status "Pod详情:"
    kubectl describe pod -l app=streamlit -n taxi-app
    echo ""
    print_status "Pod日志:"
    kubectl logs -l app=streamlit -n taxi-app --tail=50
    exit 1
}

print_success "所有Pod已就绪"

echo ""

# ============================================
# 第5步: 验证服务
# ============================================
print_status "第5步: 验证服务..."
echo ""

# 获取服务端口
FASTAPI_PORT=$(kubectl get svc fastapi-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')
STREAMLIT_PORT=$(kubectl get svc streamlit-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')

print_status "服务端口:"
echo "  FastAPI: $FASTAPI_PORT"
echo "  Streamlit: $STREAMLIT_PORT"

echo ""
print_status "等待服务就绪..."
sleep 5

# 测试API健康
print_status "测试API健康状态..."
for i in {1..10}; do
    if curl -s http://localhost:${FASTAPI_PORT}/health > /dev/null; then
        print_success "FastAPI服务健康检查通过"
        curl -s http://localhost:${FASTAPI_PORT}/health | python3 -m json.tool || echo ""
        break
    else
        if [ $i -eq 10 ]; then
            print_error "FastAPI服务健康检查失败"
        else
            echo "等待服务启动... ($i/10)"
            sleep 3
        fi
    fi
done

echo ""

# ============================================
# 第6步: 测试Tip预测
# ============================================
print_status "第6步: 测试Tip预测功能..."
echo ""

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

print_status "发送测试预测请求..."
RESPONSE=$(curl -s -X POST http://localhost:${FASTAPI_PORT}/predict \
    -H "Content-Type: application/json" \
    -d "$TEST_DATA")

if [[ $? -eq 0 && -n "$RESPONSE" ]]; then
    print_success "✅ Tip预测成功！"
    echo ""
    echo "$RESPONSE" | python3 -m json.tool
    echo ""
    
    # 提取预测值
    PREDICTED_TIP=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['predicted_tip'])" 2>/dev/null)
    if [[ -n "$PREDICTED_TIP" ]]; then
        echo -e "${GREEN}💰 预测的Tip金额: \$${PREDICTED_TIP}${NC}"
    fi
else
    print_error "预测请求失败"
    echo "响应: $RESPONSE"
fi

echo ""

# ============================================
# 第7步: 显示访问信息
# ============================================
print_status "第7步: 部署完成信息"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 部署成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${YELLOW}📊 服务状态:${NC}"
kubectl get all -n taxi-app

echo ""
echo -e "${YELLOW}🌐 访问地址:${NC}"
echo -e "${GREEN}  Streamlit UI:  http://localhost:${STREAMLIT_PORT}${NC}"
echo -e "${GREEN}  FastAPI服务:   http://localhost:${FASTAPI_PORT}${NC}"
echo -e "${GREEN}  API文档:       http://localhost:${FASTAPI_PORT}/docs${NC}"

echo ""
echo -e "${YELLOW}🚀 使用说明:${NC}"
echo "  1. 在浏览器中打开: http://localhost:${STREAMLIT_PORT}"
echo "  2. 在UI中输入行程信息"
echo "  3. 点击 '🚕 Predict Tip' 按钮"
echo "  4. 查看预测的tip金额"

echo ""
echo -e "${YELLOW}📝 监控命令:${NC}"
echo "  查看Pod状态:     kubectl get pods -n taxi-app"
echo "  查看FastAPI日志: kubectl logs -f -l app=fastapi -n taxi-app"
echo "  查看Streamlit日志: kubectl logs -f -l app=streamlit -n taxi-app"
echo "  查看服务:        kubectl get svc -n taxi-app"

echo ""
echo -e "${YELLOW}🧹 清理命令:${NC}"
echo "  kubectl delete namespace taxi-app"

echo ""
echo -e "${GREEN}✨ 现在可以打开浏览器访问 http://localhost:${STREAMLIT_PORT} 使用UI了！${NC}"
