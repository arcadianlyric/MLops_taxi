#!/bin/bash
set -e

# 完整 MLOps 平台部署脚本 (Kubernetes 版本)
# 包含 Kubernetes、Kubeflow、监控堆栈的完整部署

echo "🚀 开始部署完整 MLOps 平台 (Kubernetes + Kubeflow + 监控)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 日志文件
LOG_FILE="deployment_$(date +%Y%m%d_%H%M%S).log"

# 记录日志函数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# 错误处理
handle_error() {
    echo -e "${RED}❌ 部署失败: $1${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}📝 查看详细日志: $LOG_FILE${NC}"
    exit 1
}

# 检查先决条件
check_prerequisites() {
    log "检查先决条件..."
    
    # 检查必要命令
    local commands=("kubectl" "docker" "python3")
    for cmd in "${commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            handle_error "$cmd 未安装"
        fi
        log "✅ $cmd 已安装"
    done
    
    # 检查 Python 虚拟环境
    if [ ! -d "mlops-env" ]; then
        handle_error "Python 虚拟环境未找到，请先运行 setup_environment.sh"
    fi
    log "✅ Python 虚拟环境已就绪"
}

# 阶段 1: 设置 Kubernetes 环境
setup_kubernetes() {
    log "阶段 1: 设置 Kubernetes 环境"
    
    if ./scripts/setup_kubernetes.sh >> "$LOG_FILE" 2>&1; then
        log "✅ Kubernetes 环境设置完成"
    else
        handle_error "Kubernetes 环境设置失败"
    fi
}

# 阶段 2: 部署监控堆栈
deploy_monitoring() {
    log "阶段 2: 部署监控堆栈"
    
    if ./scripts/deploy_monitoring.sh >> "$LOG_FILE" 2>&1; then
        log "✅ 监控堆栈部署完成"
    else
        handle_error "监控堆栈部署失败"
    fi
}

# 阶段 3: 部署 Kubeflow
deploy_kubeflow() {
    log "阶段 3: 部署 Kubeflow"
    
    if ./scripts/deploy_kubeflow.sh >> "$LOG_FILE" 2>&1; then
        log "✅ Kubeflow 部署完成"
    else
        handle_error "Kubeflow 部署失败"
    fi
}

# 阶段 4: 启动本地服务
start_local_services() {
    log "阶段 4: 启动本地服务"
    
    # 停止可能运行的服务
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "streamlit" 2>/dev/null || true
    
    # 启动 FastAPI
    log "启动 FastAPI 服务..."
    nohup ./mlops-env/bin/python -m uvicorn api.test_main:app --host 0.0.0.0 --port 8000 --reload > fastapi.log 2>&1 &
    FASTAPI_PID=$!
    sleep 3
    
    # 检查 FastAPI 是否启动成功
    if curl -s http://localhost:8000/health > /dev/null; then
        log "✅ FastAPI 服务启动成功 (PID: $FASTAPI_PID)"
        echo "$FASTAPI_PID" > fastapi.pid
    else
        handle_error "FastAPI 服务启动失败"
    fi
    
    # 启动 Streamlit
    log "启动 Streamlit UI..."
    nohup ./mlops-env/bin/python -m streamlit run ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
    STREAMLIT_PID=$!
    sleep 5
    
    # 检查 Streamlit 是否启动成功
    if curl -s http://localhost:8501 > /dev/null; then
        log "✅ Streamlit UI 启动成功 (PID: $STREAMLIT_PID)"
        echo "$STREAMLIT_PID" > streamlit.pid
    else
        log "⚠️  Streamlit UI 启动可能有问题，请检查日志"
    fi
}

# 阶段 5: 启动端口转发
start_port_forwarding() {
    log "阶段 5: 启动端口转发"
    
    # 启动监控服务端口转发
    if [ -f "scripts/port_forward_monitoring.sh" ]; then
        log "启动监控服务端口转发..."
        nohup ./scripts/port_forward_monitoring.sh > port_forward_monitoring.log 2>&1 &
        MONITORING_PF_PID=$!
        echo "$MONITORING_PF_PID" > monitoring_pf.pid
        log "✅ 监控服务端口转发启动 (PID: $MONITORING_PF_PID)"
    fi
    
    # 启动 Kubeflow 端口转发
    if [ -f "scripts/port_forward_kubeflow.sh" ]; then
        log "启动 Kubeflow 端口转发..."
        nohup ./scripts/port_forward_kubeflow.sh > port_forward_kubeflow.log 2>&1 &
        KUBEFLOW_PF_PID=$!
        echo "$KUBEFLOW_PF_PID" > kubeflow_pf.pid
        log "✅ Kubeflow 端口转发启动 (PID: $KUBEFLOW_PF_PID)"
    fi
}

# 验证部署
verify_deployment() {
    log "验证完整部署..."
    
    # 验证 Kubernetes 集群
    if kubectl cluster-info > /dev/null 2>&1; then
        log "✅ Kubernetes 集群连接正常"
    else
        log "❌ Kubernetes 集群连接失败"
    fi
    
    # 验证监控服务
    local monitoring_services=("prometheus-server" "grafana" "loki")
    for service in "${monitoring_services[@]}"; do
        if kubectl get svc "$service" -n monitoring > /dev/null 2>&1; then
            log "✅ 监控服务 $service 部署成功"
        else
            log "❌ 监控服务 $service 部署失败"
        fi
    done
    
    # 验证 Kubeflow 服务
    if kubectl get pods -n kubeflow | grep -q "ml-pipeline"; then
        log "✅ Kubeflow Pipelines 部署成功"
    else
        log "❌ Kubeflow Pipelines 部署失败"
    fi
    
    # 验证本地服务
    if curl -s http://localhost:8000/health > /dev/null; then
        log "✅ FastAPI 服务运行正常"
    else
        log "❌ FastAPI 服务访问失败"
    fi
    
    if curl -s http://localhost:8501 > /dev/null; then
        log "✅ Streamlit UI 运行正常"
    else
        log "❌ Streamlit UI 访问失败"
    fi
}

# 生成访问信息
generate_access_info() {
    log "生成访问信息..."
    
    cat > access_info.txt << EOF
🎉 MLOps 平台部署完成！

📊 服务访问地址:
===================

本地服务:
- FastAPI API: http://localhost:8000
- FastAPI 文档: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501

Kubernetes 服务 (需要端口转发):
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin123)
- Loki: http://localhost:3100
- Kubeflow Pipelines UI: http://localhost:8080
- Kubeflow Pipelines API: http://localhost:8888

🔧 管理命令:
=============

查看集群状态:
kubectl get pods --all-namespaces

查看监控服务:
kubectl get pods -n monitoring

查看 Kubeflow 服务:
kubectl get pods -n kubeflow

停止所有服务:
./scripts/stop_mlops.sh

重启端口转发:
./scripts/port_forward_monitoring.sh
./scripts/port_forward_kubeflow.sh

📝 日志文件:
=============
- 部署日志: $LOG_FILE
- FastAPI 日志: fastapi.log
- Streamlit 日志: streamlit.log
- 监控端口转发: port_forward_monitoring.log
- Kubeflow 端口转发: port_forward_kubeflow.log

🧪 测试命令:
=============
# 系统验证测试
./mlops-env/bin/python scripts/test_system.py

# API 测试
curl http://localhost:8000/health
curl -X POST "http://localhost:8000/predict" -H "Content-Type: application/json" -d '{"features": {"trip_distance": 5.2, "pickup_hour": 14}}'

# Kubernetes 资源查看
kubectl get all -n monitoring
kubectl get all -n kubeflow
kubectl get all -n mlops-system
EOF

    log "✅ 访问信息已保存到 access_info.txt"
    cat access_info.txt
}

# 主函数
main() {
    echo "=" * 80
    echo -e "${BLUE}🎯 完整 MLOps 平台部署 (Kubernetes + Kubeflow + 监控)${NC}"
    echo "=" * 80
    
    log "开始完整 MLOps 平台部署"
    
    check_prerequisites
    setup_kubernetes
    deploy_monitoring
    deploy_kubeflow
    start_local_services
    start_port_forwarding
    
    # 等待服务启动
    log "等待所有服务启动..."
    sleep 10
    
    verify_deployment
    generate_access_info
    
    echo -e "${GREEN}🎉 完整 MLOps 平台部署完成！${NC}"
    echo -e "${BLUE}📋 查看访问信息: cat access_info.txt${NC}"
    echo -e "${BLUE}📝 查看部署日志: cat $LOG_FILE${NC}"
}

# 运行主函数
main "$@"
