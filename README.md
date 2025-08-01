# 基于 TFX Pipeline 的企业级 MLOps 平台 (macOS)

基于现有 `tfx_pipeline` 代码实现的完整 MLOps 平台，集成 Kubeflow、Feast、KFServing、监控和流处理功能。

## 🏗️ 架构概览

- **核心数据集**: Chicago Taxi (基于 tfx_pipeline/taxi_pipeline_native_keras.py)
- **编排层**: Kubeflow Pipelines
- **ML框架**: TensorFlow Extended (TFX)
- **特征存储**: Feast
- **模型服务**: KFServing
- **流处理**: Kafka Kraft
- **监控**: Loki + Grafana + Prometheus
- **前端**: Streamlit
- **API**: FastAPI

## 🚀 一键部署

### 前置要求

1. **macOS 10.15+** (推荐 16GB+ RAM)
2. **Docker Desktop** (启用 Kubernetes)
3. **Python 3.8+**
4. **kubectl** 已配置

### 快速开始

```bash
# 1. 一键部署完整平台
./scripts/deploy_complete_mlops.sh

# 2. 等待部署完成后访问
# Streamlit UI: http://localhost:8501
# FastAPI 文档: http://localhost:8000/docs
```

### 手动部署步骤

1. **创建虚拟环境并安装依赖**
   ```bash
   ./setup_environment.sh
   ```

2. **部署 Kubernetes 基础设施**
   ```bash
   ./scripts/deploy_kfserving.sh
   ```

3. **启动应用服务**
   ```bash
   # 激活环境
   source mlops-env/bin/activate
   
   # 启动 FastAPI
   uvicorn api.main:app --reload &
   
   # 启动 Streamlit
   streamlit run ui/streamlit_app.py &
   ```

## 📁 项目结构

```
├── tfx_pipeline/           # 基础 TFX 代码 (Taxi 数据集)
│   ├── taxi_pipeline_native_keras.py
│   ├── taxi_utils_native_keras.py
│   └── data/
├── pipelines/              # Kubeflow 集成的 TFX pipelines
│   └── taxi_kubeflow_pipeline.py
├── components/             # 自定义 TFX 组件
│   ├── feast_feature_pusher.py
│   ├── kfserving_deployer.py
│   └── model_monitoring.py
├── api/                    # FastAPI 后端
│   ├── main.py
│   └── inference_client.py
├── ui/                     # Streamlit 前端
│   └── streamlit_app.py
├── streaming/              # Kafka 流处理
│   └── kafka_processor.py
├── feast/                  # Feast 特征存储
├── k8s/                    # Kubernetes 配置
├── scripts/                # 部署脚本
│   ├── deploy_complete_mlops.sh
│   ├── deploy_kfserving.sh
│   ├── test_inference.py
│   └── stop_mlops.sh
└── requirements.txt        # Python 依赖
```

## 🔧 核心组件

### 基于 TFX Pipeline 的 ML 工作流
- **数据源**: Chicago Taxi 数据集 (tfx_pipeline/data)
- **数据验证**: 基于 taxi_utils_native_keras.py 的数据处理
- **特征工程**: 集成 Feast 特征存储
- **模型训练**: Native Keras 模型训练
- **模型评估**: TensorFlow Model Analysis
- **模型部署**: KFServing 在线推理

### 企业级扩展组件
- **Feast 特征推送**: 自动将 TFX 特征推送到 Feast
- **KFServing 部署**: 自动模型部署和版本管理
- **模型监控**: Prometheus + Grafana + Loki 集成
- **流处理**: Kafka 实时数据处理

### 用户界面
- **Streamlit UI**: 交互式模型推理和监控面板
- **FastAPI**: RESTful API 服务
- **在线推理**: 支持单次、批量、异步推理

## 🎯 使用方法

### 1. 访问服务
- **Streamlit UI**: http://localhost:8501
- **FastAPI 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

### 2. 监控面板
```bash
# 访问 Grafana (admin/admin123)
kubectl port-forward -n monitoring svc/grafana 3000:3000

# 访问 Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

### 3. 测试推理
```bash
# 运行推理测试
python scripts/test_inference.py

# 或通过 API
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": [1,2,3], "movie_ids": [101,102,103]}'
```

### 4. 管理命令
```bash
# 停止所有服务
./scripts/stop_mlops.sh

# 查看日志
tail -f *.log

# 检查 Kubernetes 状态
kubectl get pods --all-namespaces
```

## 📊 监控和告警

平台包含完整的监控体系:
- **Pipeline 执行指标**: TFX 组件运行状态
- **模型性能监控**: 准确率、延迟、吞吐量
- **数据漂移检测**: 特征分布变化监控
- **基础设施监控**: CPU、内存、网络使用率
- **业务指标**: 自定义业务 KPI

## 🔧 故障排除

### 常见问题
1. **Kubernetes 集群不可用**
   ```bash
   # 检查 Docker Desktop Kubernetes
   kubectl cluster-info
   ```

2. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8000  # FastAPI
   lsof -i :8501  # Streamlit
   ```

3. **依赖安装失败**
   ```bash
   # 重新创建环境
   rm -rf mlops-env
   ./setup_environment.sh
   ```

### 日志查看
```bash
# 应用日志
tail -f fastapi.log
tail -f streamlit.log
tail -f kafka.log

# Kubernetes 日志
kubectl logs -n mlops-system deployment/kafka
kubectl logs -n monitoring deployment/prometheus
```
