#!/bin/bash

# Grafana 数据源和仪表板配置脚本

echo "🔧 配置 Grafana 数据源和仪表板..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Grafana 配置
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASS="admin123"

# 等待 Grafana 就绪
wait_for_grafana() {
    echo -e "${BLUE}⏳ 等待 Grafana 服务就绪...${NC}"
    for i in {1..30}; do
        if curl -s "$GRAFANA_URL/api/health" > /dev/null; then
            echo -e "${GREEN}✅ Grafana 服务已就绪${NC}"
            return 0
        fi
        echo "等待中... ($i/30)"
        sleep 2
    done
    echo -e "${RED}❌ Grafana 服务未就绪${NC}"
    return 1
}

# 配置 Prometheus 数据源
configure_prometheus_datasource() {
    echo -e "${BLUE}📊 配置 Prometheus 数据源...${NC}"
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d '{
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus-server.monitoring.svc.cluster.local",
            "access": "proxy",
            "isDefault": true,
            "basicAuth": false
        }' \
        "$GRAFANA_URL/api/datasources"
    
    echo -e "${GREEN}✅ Prometheus 数据源配置完成${NC}"
}

# 配置 Loki 数据源
configure_loki_datasource() {
    echo -e "${BLUE}📝 配置 Loki 数据源...${NC}"
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d '{
            "name": "Loki",
            "type": "loki",
            "url": "http://loki.monitoring.svc.cluster.local:3100",
            "access": "proxy",
            "basicAuth": false
        }' \
        "$GRAFANA_URL/api/datasources"
    
    echo -e "${GREEN}✅ Loki 数据源配置完成${NC}"
}

# 创建 Kubernetes 集群监控仪表板
create_kubernetes_dashboard() {
    echo -e "${BLUE}📊 创建 Kubernetes 集群监控仪表板...${NC}"
    
    cat > /tmp/kubernetes-dashboard.json << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "Kubernetes 集群监控",
    "tags": ["kubernetes", "monitoring"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "集群节点状态",
        "type": "stat",
        "targets": [
          {
            "expr": "kube_node_info",
            "legendFormat": "节点数量"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "运行中的 Pod",
        "type": "stat",
        "targets": [
          {
            "expr": "count(kube_pod_info{phase=\"Running\"})",
            "legendFormat": "运行中 Pod"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
      },
      {
        "id": 3,
        "title": "CPU 使用率",
        "type": "timeseries",
        "targets": [
          {
            "expr": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "CPU 使用率 %"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 4,
        "title": "内存使用率",
        "type": "timeseries",
        "targets": [
          {
            "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "legendFormat": "内存使用率 %"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 5,
        "title": "网络流量",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(node_network_receive_bytes_total[5m])",
            "legendFormat": "接收 {{device}}"
          },
          {
            "expr": "rate(node_network_transmit_bytes_total[5m])",
            "legendFormat": "发送 {{device}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "5s"
  }
}
EOF

    curl -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d @/tmp/kubernetes-dashboard.json \
        "$GRAFANA_URL/api/dashboards/db"
    
    echo -e "${GREEN}✅ Kubernetes 集群监控仪表板创建完成${NC}"
}

# 创建 MLOps 应用监控仪表板
create_mlops_dashboard() {
    echo -e "${BLUE}🤖 创建 MLOps 应用监控仪表板...${NC}"
    
    cat > /tmp/mlops-dashboard.json << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "MLOps 应用监控",
    "tags": ["mlops", "fastapi", "predictions"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "API 请求数",
        "type": "stat",
        "targets": [
          {
            "expr": "increase(prometheus_http_requests_total[5m])",
            "legendFormat": "总请求数"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "服务状态",
        "type": "stat",
        "targets": [
          {
            "expr": "up",
            "legendFormat": "{{job}}"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
      },
      {
        "id": 3,
        "title": "HTTP 请求率",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(prometheus_http_requests_total[5m])",
            "legendFormat": "请求/秒"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 4,
        "title": "Pod 资源使用",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(container_cpu_usage_seconds_total{pod=~\".*mlops.*\"}[5m])",
            "legendFormat": "CPU {{pod}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 5,
        "title": "内存使用情况",
        "type": "timeseries",
        "targets": [
          {
            "expr": "container_memory_usage_bytes{pod=~\".*mlops.*\"}",
            "legendFormat": "内存 {{pod}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "5s"
  }
}
EOF

    curl -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d @/tmp/mlops-dashboard.json \
        "$GRAFANA_URL/api/dashboards/db"
    
    echo -e "${GREEN}✅ MLOps 应用监控仪表板创建完成${NC}"
}

# 主函数
main() {
    echo "=" * 50
    echo -e "${BLUE}🎯 Grafana 配置脚本${NC}"
    echo "=" * 50
    
    wait_for_grafana
    configure_prometheus_datasource
    configure_loki_datasource
    create_kubernetes_dashboard
    create_mlops_dashboard
    
    echo ""
    echo -e "${GREEN}🎉 Grafana 配置完成！${NC}"
    echo ""
    echo -e "${BLUE}📋 访问信息:${NC}"
    echo "  🌐 Grafana URL: http://localhost:3000"
    echo "  👤 用户名: admin"
    echo "  🔑 密码: admin123"
    echo ""
    echo -e "${BLUE}📊 可用仪表板:${NC}"
    echo "  • Kubernetes 集群监控"
    echo "  • MLOps 应用监控"
    echo ""
    echo -e "${YELLOW}💡 提示: 登录后点击左侧菜单的 'Dashboards' 查看所有仪表板${NC}"
}

# 运行主函数
main "$@"
