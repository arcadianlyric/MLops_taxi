#!/bin/bash

# 完整 MLOps 平台端口转发脚本
# 启动所有服务的端口转发

echo "🚀 启动完整 MLOps 平台端口转发..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查 Kubernetes 集群
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ 无法连接到 Kubernetes 集群${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Kubernetes 集群连接正常${NC}"

# 等待所有服务就绪
echo -e "${BLUE}⏳ 等待所有服务就绪...${NC}"

# 等待监控服务
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n monitoring --timeout=60s 2>/dev/null || echo -e "${YELLOW}⚠️  Prometheus 可能还未完全就绪${NC}"
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana -n monitoring --timeout=60s 2>/dev/null || echo -e "${YELLOW}⚠️  Grafana 可能还未完全就绪${NC}"

# 等待 Kubeflow 服务
kubectl wait --for=condition=ready pod -l app=ml-pipeline-ui -n kubeflow --timeout=60s 2>/dev/null || echo -e "${YELLOW}⚠️  Kubeflow UI 可能还未完全就绪${NC}"
kubectl wait --for=condition=ready pod -l app=ml-pipeline -n kubeflow --timeout=60s 2>/dev/null || echo -e "${YELLOW}⚠️  Kubeflow API 可能还未完全就绪${NC}"

echo -e "${GREEN}✅ 开始启动端口转发...${NC}"

# 创建 PID 文件目录
mkdir -p .pids

# 监控服务端口转发
echo -e "${BLUE}📊 启动监控服务端口转发...${NC}"

# Prometheus
kubectl port-forward -n monitoring svc/prometheus-server 9090:80 > /dev/null 2>&1 &
PROMETHEUS_PID=$!
echo $PROMETHEUS_PID > .pids/prometheus.pid
echo -e "${GREEN}✅ Prometheus: http://localhost:9090 (PID: $PROMETHEUS_PID)${NC}"

# Grafana
kubectl port-forward -n monitoring svc/grafana 3000:80 > /dev/null 2>&1 &
GRAFANA_PID=$!
echo $GRAFANA_PID > .pids/grafana.pid
echo -e "${GREEN}✅ Grafana: http://localhost:3000 (admin/admin123) (PID: $GRAFANA_PID)${NC}"

# Loki
kubectl port-forward -n monitoring svc/loki 3100:3100 > /dev/null 2>&1 &
LOKI_PID=$!
echo $LOKI_PID > .pids/loki.pid
echo -e "${GREEN}✅ Loki: http://localhost:3100 (PID: $LOKI_PID)${NC}"

# Kubeflow 服务端口转发
echo -e "${BLUE}🔧 启动 Kubeflow 服务端口转发...${NC}"

# Kubeflow Pipelines UI
kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80 > /dev/null 2>&1 &
KFP_UI_PID=$!
echo $KFP_UI_PID > .pids/kfp_ui.pid
echo -e "${GREEN}✅ Kubeflow Pipelines UI: http://localhost:8080 (PID: $KFP_UI_PID)${NC}"

# Kubeflow Pipelines API
kubectl port-forward -n kubeflow svc/ml-pipeline 8888:8888 > /dev/null 2>&1 &
KFP_API_PID=$!
echo $KFP_API_PID > .pids/kfp_api.pid
echo -e "${GREEN}✅ Kubeflow Pipelines API: http://localhost:8888 (PID: $KFP_API_PID)${NC}"

# MinIO (对象存储)
kubectl port-forward -n kubeflow svc/minio-service 9000:9000 > /dev/null 2>&1 &
MINIO_PID=$!
echo $MINIO_PID > .pids/minio.pid
echo -e "${GREEN}✅ MinIO: http://localhost:9000 (minio/minio123) (PID: $MINIO_PID)${NC}"

# 等待一下确保端口转发启动
sleep 3

echo ""
echo -e "${BLUE}🎉 所有服务端口转发已启动！${NC}"
echo ""
echo -e "${YELLOW}📋 服务访问地址:${NC}"
echo "=================================="
echo -e "${BLUE}监控服务:${NC}"
echo "  📊 Prometheus:  http://localhost:9090"
echo "  📈 Grafana:     http://localhost:3000 (admin/admin123)"
echo "  📝 Loki:        http://localhost:3100"
echo ""
echo -e "${BLUE}MLOps 平台:${NC}"
echo "  🔧 Kubeflow UI: http://localhost:8080"
echo "  🔌 Kubeflow API: http://localhost:8888"
echo "  💾 MinIO:       http://localhost:9000 (minio/minio123)"
echo ""
echo -e "${BLUE}本地服务:${NC}"
echo "  🚀 FastAPI:     http://localhost:8000"
echo "  🖥️  Streamlit:   http://localhost:8501"
echo ""
echo -e "${YELLOW}🛠️  管理命令:${NC}"
echo "  停止端口转发: ./scripts/stop_port_forwarding.sh"
echo "  查看服务状态: kubectl get pods --all-namespaces"
echo "  查看日志: kubectl logs -f <pod-name> -n <namespace>"
echo ""
echo -e "${GREEN}按 Ctrl+C 停止所有端口转发${NC}"

# 创建停止脚本
cat > scripts/stop_port_forwarding.sh << 'EOF'
#!/bin/bash
echo "🛑 停止所有端口转发..."

if [ -d ".pids" ]; then
    for pidfile in .pids/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "✅ 停止进程 $pid"
            fi
            rm "$pidfile"
        fi
    done
    rmdir .pids 2>/dev/null
fi

echo "🎉 所有端口转发已停止"
EOF

chmod +x scripts/stop_port_forwarding.sh

# 等待中断信号
trap 'echo -e "\n${YELLOW}🛑 停止所有端口转发...${NC}"; kill $PROMETHEUS_PID $GRAFANA_PID $LOKI_PID $KFP_UI_PID $KFP_API_PID $MINIO_PID 2>/dev/null; rm -rf .pids; exit' INT

# 保持脚本运行
wait
