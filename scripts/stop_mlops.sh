#!/bin/bash
# MLOps 平台停止脚本

set -e

echo "🛑 停止 MLOps 平台服务..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 停止应用服务
stop_applications() {
    echo -e "${YELLOW}🖥️ 停止应用服务...${NC}"
    
    # 停止 FastAPI
    if [ -f ".fastapi.pid" ]; then
        FASTAPI_PID=$(cat .fastapi.pid)
        if kill -0 $FASTAPI_PID 2>/dev/null; then
            kill $FASTAPI_PID
            echo "✅ FastAPI 服务已停止"
        fi
        rm -f .fastapi.pid
    fi
    
    # 停止 Streamlit
    if [ -f ".streamlit.pid" ]; then
        STREAMLIT_PID=$(cat .streamlit.pid)
        if kill -0 $STREAMLIT_PID 2>/dev/null; then
            kill $STREAMLIT_PID
            echo "✅ Streamlit UI 已停止"
        fi
        rm -f .streamlit.pid
    fi
    
    # 停止 Kafka 处理器
    if [ -f ".kafka.pid" ]; then
        KAFKA_PID=$(cat .kafka.pid)
        if kill -0 $KAFKA_PID 2>/dev/null; then
            kill $KAFKA_PID
            echo "✅ Kafka 处理器已停止"
        fi
        rm -f .kafka.pid
    fi
    
    # 清理其他可能的进程
    pkill -f "uvicorn api.main:app" 2>/dev/null || true
    pkill -f "streamlit run ui/streamlit_app.py" 2>/dev/null || true
    pkill -f "kafka_processor.py" 2>/dev/null || true
}

# 停止 Kubernetes 服务 (可选)
stop_k8s_services() {
    echo -e "${YELLOW}☸️ 停止 Kubernetes 服务...${NC}"
    
    # 删除部署
    kubectl delete deployment --all -n mlops-system --ignore-not-found=true
    kubectl delete deployment --all -n monitoring --ignore-not-found=true
    kubectl delete deployment --all -n feast-system --ignore-not-found=true
    
    echo "✅ Kubernetes 服务已停止"
}

# 主函数
main() {
    echo -e "${RED}🛑 停止 MLOps 平台${NC}"
    
    stop_applications
    
    # 询问是否停止 Kubernetes 服务
    read -p "是否同时停止 Kubernetes 服务? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        stop_k8s_services
    fi
    
    echo -e "${GREEN}✅ MLOps 平台已停止${NC}"
}

main "$@"
