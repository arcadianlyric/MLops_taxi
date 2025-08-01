#!/bin/bash
set -e

# 监控堆栈部署脚本
# 部署 Prometheus、Grafana、Loki

echo "🚀 开始部署监控堆栈 (Prometheus/Grafana/Loki)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查 Kubernetes 集群
check_cluster() {
    echo -e "${BLUE}🔍 检查 Kubernetes 集群...${NC}"
    
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ 无法连接到 Kubernetes 集群${NC}"
        echo "请先运行: ./scripts/setup_kubernetes.sh"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Kubernetes 集群连接正常${NC}"
}

# 添加 Helm 仓库
add_helm_repos() {
    echo -e "${BLUE}📦 添加 Helm 仓库...${NC}"
    
    # Prometheus 社区仓库
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    
    # Grafana 仓库
    helm repo add grafana https://grafana.github.io/helm-charts
    
    # 更新仓库
    helm repo update
    
    echo -e "${GREEN}✅ Helm 仓库添加完成${NC}"
}

# 部署 Prometheus
deploy_prometheus() {
    echo -e "${BLUE}📊 部署 Prometheus...${NC}"
    
    # 创建 Prometheus 配置
    cat > /tmp/prometheus-values.yaml << EOF
server:
  persistentVolume:
    enabled: true
    size: 10Gi
  service:
    type: ClusterIP
    servicePort: 9090
  
alertmanager:
  enabled: true
  persistentVolume:
    enabled: true
    size: 2Gi

nodeExporter:
  enabled: true

pushgateway:
  enabled: true

serverFiles:
  prometheus.yml:
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    scrape_configs:
      - job_name: 'prometheus'
        static_configs:
          - targets: ['localhost:9090']
      
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: \$1:\$2
            target_label: __address__
EOF

    # 部署 Prometheus
    helm upgrade --install prometheus prometheus-community/prometheus \
        --namespace monitoring \
        --values /tmp/prometheus-values.yaml \
        --wait
    
    echo -e "${GREEN}✅ Prometheus 部署完成${NC}"
}

# 部署 Grafana
deploy_grafana() {
    echo -e "${BLUE}📈 部署 Grafana...${NC}"
    
    # 创建 Grafana 配置
    cat > /tmp/grafana-values.yaml << EOF
persistence:
  enabled: true
  size: 10Gi

adminPassword: admin123

service:
  type: ClusterIP
  port: 3000

datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        url: http://prometheus-server:9090
        access: proxy
        isDefault: true
      - name: Loki
        type: loki
        url: http://loki:3100
        access: proxy

dashboardProviders:
  dashboardproviders.yaml:
    apiVersion: 1
    providers:
      - name: 'default'
        orgId: 1
        folder: ''
        type: file
        disableDeletion: false
        editable: true
        options:
          path: /var/lib/grafana/dashboards/default

dashboards:
  default:
    kubernetes-cluster:
      gnetId: 7249
      revision: 1
      datasource: Prometheus
    kubernetes-pods:
      gnetId: 6417
      revision: 1
      datasource: Prometheus
    node-exporter:
      gnetId: 1860
      revision: 27
      datasource: Prometheus

env:
  GF_SECURITY_ADMIN_PASSWORD: admin123
  GF_USERS_ALLOW_SIGN_UP: false
EOF

    # 部署 Grafana
    helm upgrade --install grafana grafana/grafana \
        --namespace monitoring \
        --values /tmp/grafana-values.yaml \
        --wait
    
    echo -e "${GREEN}✅ Grafana 部署完成${NC}"
    echo -e "${YELLOW}📝 Grafana 管理员密码: admin123${NC}"
}

# 部署 Loki
deploy_loki() {
    echo -e "${BLUE}📝 部署 Loki...${NC}"
    
    # 创建 Loki 配置
    cat > /tmp/loki-values.yaml << EOF
loki:
  auth_enabled: false
  server:
    http_listen_port: 3100
  
  ingester:
    lifecycler:
      address: 127.0.0.1
      ring:
        kvstore:
          store: inmemory
        replication_factor: 1
      final_sleep: 0s
    chunk_idle_period: 5m
    chunk_retain_period: 30s
    max_transfer_retries: 0

  schema_config:
    configs:
      - from: 2020-10-24
        store: boltdb
        object_store: filesystem
        schema: v11
        index:
          prefix: index_
          period: 168h

  storage_config:
    boltdb:
      directory: /tmp/loki/index
    filesystem:
      directory: /tmp/loki/chunks

  limits_config:
    enforce_metric_name: false
    reject_old_samples: true
    reject_old_samples_max_age: 168h

persistence:
  enabled: true
  size: 10Gi

service:
  type: ClusterIP
  port: 3100
EOF

    # 部署 Loki
    helm upgrade --install loki grafana/loki-stack \
        --namespace monitoring \
        --values /tmp/loki-values.yaml \
        --wait
    
    echo -e "${GREEN}✅ Loki 部署完成${NC}"
}

# 创建 ServiceMonitor 用于 MLOps 应用监控
create_service_monitors() {
    echo -e "${BLUE}🔧 创建 ServiceMonitor...${NC}"
    
    # MLOps API ServiceMonitor
    cat > /tmp/mlops-servicemonitor.yaml << EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: mlops-api
  namespace: monitoring
  labels:
    app: mlops-api
spec:
  selector:
    matchLabels:
      app: mlops-api
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
---
apiVersion: v1
kind: Service
metadata:
  name: mlops-api
  namespace: monitoring
  labels:
    app: mlops-api
spec:
  type: ExternalName
  externalName: host.docker.internal
  ports:
  - name: http
    port: 8000
    targetPort: 8000
EOF

    kubectl apply -f /tmp/mlops-servicemonitor.yaml
    echo -e "${GREEN}✅ ServiceMonitor 创建完成${NC}"
}

# 创建端口转发脚本
create_port_forward_script() {
    echo -e "${BLUE}🔗 创建端口转发脚本...${NC}"
    
    cat > scripts/port_forward_monitoring.sh << 'EOF'
#!/bin/bash

# 监控服务端口转发脚本

echo "🚀 启动监控服务端口转发..."

# 后台启动端口转发
kubectl port-forward -n monitoring svc/prometheus-server 9090:9090 &
PROMETHEUS_PID=$!

kubectl port-forward -n monitoring svc/grafana 3000:3000 &
GRAFANA_PID=$!

kubectl port-forward -n monitoring svc/loki 3100:3100 &
LOKI_PID=$!

echo "📊 监控服务访问地址:"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin/admin123)"
echo "  Loki:       http://localhost:3100"
echo ""
echo "按 Ctrl+C 停止端口转发"

# 等待中断信号
trap 'kill $PROMETHEUS_PID $GRAFANA_PID $LOKI_PID; exit' INT
wait
EOF

    chmod +x scripts/port_forward_monitoring.sh
    echo -e "${GREEN}✅ 端口转发脚本创建完成${NC}"
}

# 验证部署
verify_deployment() {
    echo -e "${BLUE}🔍 验证监控堆栈部署...${NC}"
    
    # 检查 Pod 状态
    echo -e "${BLUE}📦 检查 Pod 状态:${NC}"
    kubectl get pods -n monitoring
    
    # 检查服务状态
    echo -e "${BLUE}🔗 检查服务状态:${NC}"
    kubectl get svc -n monitoring
    
    # 等待所有 Pod 就绪
    echo -e "${BLUE}⏳ 等待所有 Pod 就绪...${NC}"
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n monitoring --timeout=300s
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana -n monitoring --timeout=300s
    
    echo -e "${GREEN}✅ 监控堆栈部署验证完成${NC}"
}

# 主函数
main() {
    echo "=" * 60
    echo -e "${BLUE}🎯 监控堆栈部署 (Prometheus/Grafana/Loki)${NC}"
    echo "=" * 60
    
    check_cluster
    add_helm_repos
    deploy_prometheus
    deploy_grafana
    deploy_loki
    create_service_monitors
    create_port_forward_script
    verify_deployment
    
    echo -e "${GREEN}🎉 监控堆栈部署完成！${NC}"
    echo ""
    echo -e "${BLUE}📋 下一步操作:${NC}"
    echo "1. 运行端口转发: ./scripts/port_forward_monitoring.sh"
    echo "2. 访问 Grafana: http://localhost:3000 (admin/admin123)"
    echo "3. 访问 Prometheus: http://localhost:9090"
    echo "4. 部署 Kubeflow: ./scripts/deploy_kubeflow.sh"
}

# 运行主函数
main "$@"
