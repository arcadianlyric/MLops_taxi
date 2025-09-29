#!/bin/bash

# Taxi Tip Prediction App 部署脚本
set -e

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

# 检查前置条件
check_prerequisites() {
    print_status "检查前置条件..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker未运行"
        exit 1
    fi
    print_success "Docker运行正常"
    
    # 检查kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl未安装"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到Kubernetes集群"
        exit 1
    fi
    print_success "Kubernetes集群连接正常"
}

# 构建Docker镜像
build_image() {
    print_status "构建Docker镜像..."
    
    cd "$(dirname "$0")/.."
    
    # 检查必要文件
    if [[ ! -f "api/taxi_simple_api.py" ]]; then
        print_error "api/taxi_simple_api.py 不存在"
        exit 1
    fi
    
    if [[ ! -f "ui/streamlit_app.py" ]]; then
        print_error "ui/streamlit_app.py 不存在"
        exit 1
    fi
    
    # 构建镜像
    print_status "使用 Dockerfile.app 构建镜像..."
    if docker build -f Dockerfile.app -t taxi-app:latest .; then
        print_success "Docker镜像构建成功"
    else
        print_error "Docker镜像构建失败"
        exit 1
    fi
    
    # 显示镜像信息
    docker images | grep taxi-app
}

# 部署到Kubernetes
deploy_to_k8s() {
    print_status "部署到Kubernetes..."
    
    cd "$(dirname "$0")/.."
    
    # 检查配置文件
    if [[ ! -f "k8s/taxi-app-simple.yaml" ]]; then
        print_error "k8s/taxi-app-simple.yaml 不存在"
        exit 1
    fi
    
    # 清理旧部署
    print_status "清理旧部署..."
    kubectl delete namespace taxi-app --ignore-not-found=true
    sleep 5
    
    # 应用新配置
    print_status "应用Kubernetes配置..."
    kubectl apply -f k8s/taxi-app-simple.yaml
    
    print_success "部署完成"
}

# 等待Pod就绪
wait_for_pods() {
    print_status "等待Pod就绪..."
    
    # 等待FastAPI Pod
    print_status "等待FastAPI Pod..."
    kubectl wait --for=condition=ready pod -l app=fastapi -n taxi-app --timeout=120s || {
        print_error "FastAPI Pod启动超时"
        kubectl get pods -n taxi-app
        kubectl describe pod -l app=fastapi -n taxi-app
        exit 1
    }
    
    # 等待Streamlit Pod
    print_status "等待Streamlit Pod..."
    kubectl wait --for=condition=ready pod -l app=streamlit -n taxi-app --timeout=120s || {
        print_error "Streamlit Pod启动超时"
        kubectl get pods -n taxi-app
        kubectl describe pod -l app=streamlit -n taxi-app
        exit 1
    }
    
    print_success "所有Pod已就绪"
}

# 显示部署状态
show_status() {
    print_status "部署状态:"
    echo "===================="
    
    kubectl get all -n taxi-app
    
    echo ""
    print_status "服务访问信息:"
    echo "===================="
    
    # 获取NodePort
    FASTAPI_PORT=$(kubectl get svc fastapi-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')
    STREAMLIT_PORT=$(kubectl get svc streamlit-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')
    
    echo -e "${GREEN}FastAPI服务:${NC} http://localhost:${FASTAPI_PORT}"
    echo -e "${GREEN}FastAPI文档:${NC} http://localhost:${FASTAPI_PORT}/docs"
    echo -e "${GREEN}Streamlit UI:${NC} http://localhost:${STREAMLIT_PORT}"
    
    echo ""
    print_status "测试API健康状态..."
    sleep 3
    
    if curl -s http://localhost:${FASTAPI_PORT}/health > /dev/null; then
        print_success "FastAPI服务健康检查通过"
        curl -s http://localhost:${FASTAPI_PORT}/health | python3 -m json.tool
    else
        print_warning "FastAPI服务尚未就绪，请稍后再试"
    fi
}

# 测试预测功能
test_prediction() {
    print_status "测试Tip预测功能..."
    
    FASTAPI_PORT=$(kubectl get svc fastapi-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')
    
    # 测试数据
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
    RESPONSE=$(curl -s -X POST http://localhost:${FASTAPI_PORT}/predict \
        -H "Content-Type: application/json" \
        -d "$TEST_DATA")
    
    if [[ $? -eq 0 ]]; then
        print_success "预测成功！"
        echo "$RESPONSE" | python3 -m json.tool
    else
        print_error "预测失败"
        exit 1
    fi
}

# 查看日志
show_logs() {
    print_status "查看应用日志..."
    
    echo ""
    print_status "FastAPI日志 (最近20行):"
    kubectl logs -l app=fastapi -n taxi-app --tail=20
    
    echo ""
    print_status "Streamlit日志 (最近20行):"
    kubectl logs -l app=streamlit -n taxi-app --tail=20
}

# 主函数
main() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}Taxi Tip Prediction App 部署${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    
    # 步骤1: 检查前置条件
    check_prerequisites
    echo ""
    
    # 步骤2: 构建镜像
    build_image
    echo ""
    
    # 步骤3: 部署到K8s
    deploy_to_k8s
    echo ""
    
    # 步骤4: 等待Pod就绪
    wait_for_pods
    echo ""
    
    # 步骤5: 显示状态
    show_status
    echo ""
    
    # 步骤6: 测试预测
    test_prediction
    echo ""
    
    # 步骤7: 显示日志
    show_logs
    echo ""
    
    # 完成
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}部署完成！${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    
    STREAMLIT_PORT=$(kubectl get svc streamlit-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')
    echo -e "${YELLOW}🚀 打开浏览器访问:${NC}"
    echo -e "${GREEN}   http://localhost:${STREAMLIT_PORT}${NC}"
    echo ""
    echo -e "${YELLOW}📝 监控命令:${NC}"
    echo "   kubectl get pods -n taxi-app -w"
    echo "   kubectl logs -f -l app=fastapi -n taxi-app"
    echo "   kubectl logs -f -l app=streamlit -n taxi-app"
}

# 运行主函数
main "$@"
