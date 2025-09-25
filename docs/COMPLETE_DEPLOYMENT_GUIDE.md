# Chicago Taxi MLOps 平台完整部署指南

## 概述

本指南提供了 Chicago Taxi MLOps 平台的完整部署和测试流程，包括最新的 Feast 集成最佳实践、MLflow 模型注册中心和 Kafka 流处理集成。

## 架构亮点

### ✅ 已实现的核心功能

1. **Feast 特征存储集成 (最佳实践)**
   - ✅ 独立的 Feast 集成管道 (`feast_integration_pipeline.py`)
   - ✅ 外部调度系统 (`schedule_feast_integration.py`)
   - ✅ 配置驱动的特征管理 (`integration_config.yaml`)
   - ✅ Redis 在线存储 + Parquet 离线存储
   - ✅ 完整的监控和日志记录

2. **MLflow 模型注册中心**
   - ✅ 完整的 MLflow 服务部署
   - ✅ FastAPI 集成路由
   - ✅ Streamlit UI 集成
   - ✅ 实验管理和模型版本控制

3. **Kafka 流处理**
   - ✅ Kafka FastAPI 路由集成
   - ✅ Streamlit UI 集成组件
   - ✅ 消息发送和主题管理

4. **统一的用户界面**
   - ✅ Streamlit 多标签页设计
   - ✅ 集成 Feast、Kafka、MLflow 功能
   - ✅ 数据漂移监控可视化

## 快速开始

### 1. 环境准备

```bash
# 1. 创建虚拟环境
./scripts/setup_environment.sh

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 验证安装
python -c "import feast, mlflow, kafka; print('所有依赖已安装')"
```

### 2. 服务部署

```bash
# 1. 部署 MLflow 模型注册中心
./scripts/deploy_mlflow.sh

# 2. 启动 MLflow 服务
cd mlflow && ./start_mlflow.sh

# 3. 启动 FastAPI 服务
cd api && python main.py

# 4. 启动 Streamlit UI
cd ui && streamlit run streamlit_app.py
```

### 3. Feast 集成测试

```bash
# 1. 测试 Feast 集成管道
cd feast && python feast_integration_pipeline.py

# 2. 启动 Feast 调度器 (可选)
cd scripts && python schedule_feast_integration.py --daemon

# 3. 验证特征数据生成
ls feast/data/  # 应该看到 *.parquet 文件
```

### 4. 完整系统测试

```bash
# 运行完整集成测试
python scripts/test_complete_integration.py
```

## 服务端点

| 服务 | 端口 | URL | 描述 |
|------|------|-----|------|
| FastAPI | 8000 | http://localhost:8000 | API 服务和文档 |
| Streamlit | 8501 | http://localhost:8501 | 用户界面 |
| MLflow | 5000 | http://localhost:5000 | 模型注册中心 |
| Redis | 6379 | localhost:6379 | 特征在线存储 |
| Kafka | 9092 | localhost:9092 | 流处理消息队列 |

## Feast 集成最佳实践

### 架构设计

我们采用了业界推荐的最佳实践，将 Feast 集成从 TFX Pipeline 中解耦：

```
传统方式 (不推荐):
TFX Pipeline → FeastPusher Component → Feast

新架构 (最佳实践):
TFX Pipeline → Transform Output
                    ↓
Independent Pipeline → Feast Integration → Feature Store
```

### 核心优势

1. **解耦设计**: Feast 集成独立运行，不影响 TFX Pipeline
2. **灵活调度**: 支持不同的特征刷新频率
3. **易于维护**: 专注特征逻辑，代码更清晰
4. **生产就绪**: 符合企业级 MLOps 标准

### 配置文件

`feast/integration_config.yaml` 提供了完整的配置管理：

```yaml
feast:
  repo_path: "feast/"
  online_store:
    type: "redis"
    connection_string: "redis://localhost:6379"
  offline_store:
    type: "file"
    path: "feast/data/"

features:
  trip_features:
    - trip_distance
    - passenger_count
    - pickup_hour
  # ... 更多特征配置

scheduling:
  refresh_interval: 3600  # 1小时
  materialization_interval: 1800  # 30分钟
```

## MLflow 集成

### 功能特性

1. **实验管理**: 完整的实验追踪和比较
2. **模型注册**: 版本控制和阶段管理
3. **指标记录**: 自动化指标收集
4. **模型预测**: 集成预测接口

### API 端点

```bash
# 获取 MLflow 服务信息
GET /mlflow/info

# 列出所有实验
GET /mlflow/experiments

# 获取注册模型
GET /mlflow/models

# 记录模型指标
POST /mlflow/models/metrics
```

### UI 集成

Streamlit UI 提供了完整的 MLflow 管理界面：

- 📊 服务概览
- 🧪 实验管理
- 📦 模型注册
- 🔄 版本管理
- 📈 指标管理
- 🎯 模型预测

## Kafka 流处理

### 主题设计

```yaml
topics:
  - taxi-raw-data        # 原始出租车数据
  - taxi-features        # 处理后的特征
  - taxi-predictions     # 预测结果
  - taxi-model-metrics   # 模型指标
  - taxi-alerts          # 告警事件
```

### 消息格式

```json
{
  "trip_id": "trip_001",
  "pickup_datetime": "2024-01-01T10:00:00Z",
  "dropoff_datetime": "2024-01-01T10:30:00Z",
  "pickup_latitude": 41.88,
  "pickup_longitude": -87.63,
  "dropoff_latitude": 41.89,
  "dropoff_longitude": -87.62,
  "passenger_count": 2,
  "trip_distance": 3.5,
  "fare_amount": 12.50
}
```

## 数据流架构

### 训练时数据流

```
Raw Data → TFX Pipeline → Transformed Data
                              ↓
                    Feast Integration Pipeline
                              ↓
                         Feature Store
                              ↓
                    Model Training → MLflow
```

### 推理时数据流

```
Request → FastAPI → Feature Store → Model → Response
                         ↓
                  Monitoring & Logging
```

### 实时数据流

```
Streaming Data → Kafka → Stream Processor → Feature Store
                    ↓
               Real-time Inference
```

## 监控和日志

### 系统监控

- **服务健康**: 所有服务的健康状态检查
- **性能指标**: 延迟、吞吐量、错误率
- **资源使用**: CPU、内存、存储使用情况

### 数据监控

- **数据漂移**: 自动检测特征分布变化
- **数据质量**: 缺失值、异常值检测
- **特征监控**: 特征重要性和相关性分析

### 模型监控

- **预测性能**: RMSE、MAE、R² 等指标
- **模型漂移**: 模型性能下降检测
- **A/B 测试**: 多模型对比分析

## 故障排除

### 常见问题

1. **Feast 连接失败**
   ```bash
   # 检查 Redis 服务
   redis-cli ping
   
   # 重启 Redis (如果需要)
   brew services restart redis
   ```

2. **MLflow 数据库错误**
   ```bash
   # 重新初始化数据库
   cd mlflow && mlflow db upgrade sqlite:///mlflow.db
   ```

3. **Kafka 连接超时**
   ```bash
   # 检查 Kafka 服务状态
   brew services list | grep kafka
   
   # 启动 Kafka
   brew services start kafka
   ```

### 日志位置

- FastAPI 日志: `logs/fastapi.log`
- Feast 集成日志: `logs/feast_integration.log`
- MLflow 日志: `mlflow/logs/`
- 系统测试日志: `logs/integration_test_report.json`

## 性能优化

### 特征存储优化

1. **Redis 配置优化**
   ```
   maxmemory 2gb
   maxmemory-policy allkeys-lru
   ```

2. **批量特征获取**
   ```python
   # 批量获取特征而不是单个获取
   features = feast_client.get_online_features(
       entity_rows=[{"trip_id": id} for id in trip_ids],
       features=feature_list
   )
   ```

### 模型服务优化

1. **模型缓存**: 缓存热门模型到内存
2. **批量预测**: 支持批量推理请求
3. **异步处理**: 使用异步 I/O 提高并发性能

## 扩展指南

### 添加新特征

1. 在 `feast/features/taxi_features.py` 中定义新特征
2. 更新 `feast/integration_config.yaml` 配置
3. 修改 `feast_integration_pipeline.py` 处理逻辑
4. 重新运行特征管道

### 集成新模型

1. 在 MLflow 中注册新模型
2. 更新 FastAPI 路由支持新模型
3. 在 Streamlit UI 中添加新模型选择
4. 配置模型监控指标

### 添加新数据源

1. 在 TFX Pipeline 中添加新的 ExampleGen
2. 更新 Transform 组件处理新数据
3. 修改 Feast 特征定义
4. 更新监控和告警规则

## 生产部署

### Kubernetes 部署

```yaml
# 使用 Helm Chart 部署到 Kubernetes
helm install mlops-platform ./k8s/helm-chart/
```

### Docker 容器化

```bash
# 构建所有服务的 Docker 镜像
docker-compose build

# 启动完整系统
docker-compose up -d
```

### CI/CD 集成

```yaml
# GitHub Actions 工作流示例
name: MLOps Platform CI/CD
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Integration Tests
        run: python scripts/test_complete_integration.py
```

## 总结

Chicago Taxi MLOps 平台现在具备了：

✅ **企业级 Feast 集成**: 采用最佳实践的独立特征管道  
✅ **完整的 MLflow 集成**: 模型注册、实验管理、版本控制  
✅ **Kafka 流处理**: 实时数据处理和事件驱动架构  
✅ **统一的用户界面**: 集成所有功能的 Streamlit UI  
✅ **完整的监控**: 数据、模型、系统全方位监控  
✅ **生产就绪**: 符合企业级部署标准  

这个架构为您提供了一个坚实的基础，支持从开发到生产的完整 ML 生命周期管理。
