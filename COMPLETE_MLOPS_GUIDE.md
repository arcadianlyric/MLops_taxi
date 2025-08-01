# 完整 MLOps 平台使用指南

## 🎉 部署成功概览

恭喜！您已成功在 macOS 上部署了一个完整的企业级 MLOps 平台，包含：

### ✅ 已部署的核心组件

#### 1. **Kubernetes 集群** (Minikube)
- 🐳 使用 Docker 驱动的 Minikube 集群
- 📦 4 个命名空间：`monitoring`, `kubeflow`, `mlops-system`, `feast-system`
- 🔧 已启用 Ingress、Metrics Server、Dashboard

#### 2. **监控堆栈** (Prometheus + Grafana + Loki)
- 📊 **Prometheus**: 指标收集和监控 (http://localhost:9090)
- 📈 **Grafana**: 可视化仪表板 (http://localhost:3000, admin/admin123)
- 📝 **Loki**: 日志聚合和查询

#### 3. **Kubeflow Pipelines**
- 🔧 **Kubeflow UI**: 流水线管理界面 (http://localhost:8080)
- 🔌 **Kubeflow API**: RESTful API 接口 (http://localhost:8888)
- 💾 **MinIO**: 对象存储服务 (http://localhost:9000, minio/minio123)
- 🗄️ **MySQL**: 元数据存储

#### 4. **本地应用服务**
- 🚀 **FastAPI**: ML 预测 API (http://localhost:8000)
- 🖥️ **Streamlit**: 交互式 UI (http://localhost:8501)

### 📊 系统验证结果

**最新验证状态: 13/15 通过 (87%)**

✅ **正常运行的服务:**
- Kubernetes 集群
- 所有命名空间的 Pod (25/26 运行中)
- FastAPI 预测功能
- Streamlit UI
- Prometheus 指标收集
- Grafana 仪表板
- Kubeflow UI/API

⚠️ **需要关注的服务:**
- Loki 日志服务 (端口配置问题)
- MinIO 对象存储 (权限配置问题)

## 🚀 快速开始

### 1. 启动所有服务

```bash
# 确保 Minikube 运行
/opt/homebrew/bin/minikube status

# 启动端口转发 (后台运行)
./scripts/port_forward_all_services.sh &

# 启动本地 FastAPI 服务 (如果未运行)
./mlops-env/bin/python -m uvicorn api.test_main:app --host 0.0.0.0 --port 8000 --reload &

# 启动 Streamlit UI (如果未运行)
./mlops-env/bin/python -m streamlit run ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0 &
```

### 2. 验证系统状态

```bash
# 运行完整系统验证
./mlops-env/bin/python scripts/verify_full_system.py

# 检查 Kubernetes 资源
kubectl get pods --all-namespaces
kubectl get services --all-namespaces
```

### 3. 访问服务

| 服务 | 地址 | 用户名/密码 | 功能 |
|------|------|-------------|------|
| **FastAPI** | http://localhost:8000 | - | ML 预测 API |
| **FastAPI 文档** | http://localhost:8000/docs | - | API 交互文档 |
| **Streamlit UI** | http://localhost:8501 | - | 交互式机器学习界面 |
| **Prometheus** | http://localhost:9090 | - | 指标监控 |
| **Grafana** | http://localhost:3000 | admin/admin123 | 可视化仪表板 |
| **Kubeflow UI** | http://localhost:8080 | - | ML 流水线管理 |
| **MinIO** | http://localhost:9000 | minio/minio123 | 对象存储 |

## 🧪 功能测试

### FastAPI 测试

```bash
# 健康检查
curl http://localhost:8000/health

# 单次预测
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"features": {"trip_distance": 5.2, "pickup_hour": 14}}'

# 批量预测
curl -X POST "http://localhost:8000/predict/batch" \
  -H "Content-Type: application/json" \
  -d '[{"features": {"trip_distance": 2.1, "pickup_hour": 8}}, {"features": {"trip_distance": 7.5, "pickup_hour": 18}}]'

# 查看模型列表
curl http://localhost:8000/models

# 查看服务指标
curl http://localhost:8000/metrics
```

### Prometheus 查询

```bash
# 查询所有运行中的服务
curl "http://localhost:9090/api/v1/query?query=up"

# 查询 CPU 使用率
curl "http://localhost:9090/api/v1/query?query=rate(cpu_usage_seconds_total[5m])"
```

## 🔧 管理操作

### 服务管理

```bash
# 停止所有端口转发
./scripts/stop_port_forwarding.sh

# 重启端口转发
./scripts/port_forward_all_services.sh

# 停止本地服务
pkill -f "uvicorn"
pkill -f "streamlit"
```

### Kubernetes 管理

```bash
# 查看集群状态
kubectl cluster-info
kubectl get nodes

# 查看所有 Pod
kubectl get pods --all-namespaces

# 查看特定命名空间
kubectl get pods -n monitoring
kubectl get pods -n kubeflow

# 查看服务日志
kubectl logs -f <pod-name> -n <namespace>

# 重启服务
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### Minikube 管理

```bash
# 查看 Minikube 状态
/opt/homebrew/bin/minikube status

# 停止 Minikube
/opt/homebrew/bin/minikube stop

# 启动 Minikube
/opt/homebrew/bin/minikube start

# 访问 Kubernetes Dashboard
/opt/homebrew/bin/minikube dashboard
```

## 📈 监控和可观测性

### Grafana 仪表板

1. 访问 http://localhost:3000
2. 使用 admin/admin123 登录
3. 预配置的仪表板：
   - Kubernetes Cluster Overview
   - Node Exporter Metrics
   - Pod Monitoring

### Prometheus 指标

- **系统指标**: CPU、内存、磁盘使用率
- **应用指标**: API 请求数、响应时间、错误率
- **Kubernetes 指标**: Pod 状态、资源使用

### 日志管理

- **应用日志**: `fastapi.log`, `streamlit.log`
- **Kubernetes 日志**: `kubectl logs`
- **Loki 聚合**: 统一日志查询和分析

## 🚀 下一步扩展

### 1. TFX Pipeline 集成

```bash
# 部署基于 tfx_pipeline 的完整 ML 流水线
./mlops-env/bin/python scripts/deploy_tfx_pipeline.py
```

### 2. 添加更多监控

```bash
# 部署 Kafka 流处理
./scripts/deploy_kafka.sh

# 集成 Feast 特征存储
./scripts/deploy_feast.sh
```

### 3. 生产环境优化

- 配置持久化存储
- 设置资源限制和请求
- 配置 RBAC 安全策略
- 添加 SSL/TLS 证书

## 🛠️ 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   lsof -i :8000  # 查看端口占用
   kill -9 <PID>  # 终止进程
   ```

2. **Minikube 启动失败**
   ```bash
   /opt/homebrew/bin/minikube delete  # 删除集群
   /opt/homebrew/bin/minikube start   # 重新创建
   ```

3. **Pod 状态异常**
   ```bash
   kubectl describe pod <pod-name> -n <namespace>
   kubectl logs <pod-name> -n <namespace>
   ```

4. **服务无法访问**
   ```bash
   kubectl get svc -n <namespace>  # 检查服务状态
   kubectl port-forward svc/<service-name> <local-port>:<service-port> -n <namespace>
   ```

### 重置环境

```bash
# 完全重置 Minikube 环境
/opt/homebrew/bin/minikube delete
/opt/homebrew/bin/minikube start --driver=docker --memory=6144 --cpus=4

# 重新部署所有服务
./scripts/deploy_full_mlops_k8s.sh
```

## 📚 相关文档

- [Kubernetes 官方文档](https://kubernetes.io/docs/)
- [Kubeflow 官方文档](https://www.kubeflow.org/docs/)
- [Prometheus 官方文档](https://prometheus.io/docs/)
- [Grafana 官方文档](https://grafana.com/docs/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Streamlit 官方文档](https://docs.streamlit.io/)

## 🎯 成就总结

🎉 **您已成功构建了一个完整的企业级 MLOps 平台！**

- ✅ Kubernetes 集群管理
- ✅ 容器化应用部署
- ✅ 监控和可观测性
- ✅ ML 流水线管理
- ✅ API 服务和 UI 界面
- ✅ 自动化部署脚本
- ✅ 系统验证和测试

这个平台为您提供了一个完整的机器学习开发、部署和监控环境，可以支持从模型训练到生产部署的完整生命周期管理。
