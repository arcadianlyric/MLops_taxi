# 🚕 Chicago Taxi Tip Prediction - MLOps Platform

[![TFX](https://img.shields.io/badge/TFX-0.21.4-orange)](https://www.tensorflow.org/tfx)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)

完整的 MLOps 系统，使用 TensorFlow Extended (TFX) 训练模型，FastAPI 提供预测服务，Streamlit 提供交互式 UI。

---

## 📋 目录

- [快速开始](#-快速开始)
- [TFX 模型训练](#-tfx-模型训练)
- [项目架构](#-项目架构)
- [容器构建](#-容器构建)
- [运行服务](#-运行服务)
- [使用指南](#-使用指南)
- [开发指南](#-开发指南)
- [故障排除](#-故障排除)

---

## 🚀 快速开始

### 前提条件

- Docker 已安装
- Docker Compose 已安装（可选）
- 8000 和 8501 端口未被占用

### 方法 1: 使用 Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone <your-repo>
cd MLops_taxi

# 2. 构建并启动所有服务
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f

# 4. 访问服务
# API: http://localhost:8000
# UI:  http://localhost:8501
```

### 方法 2: 手动构建和运行

```bash
# 1. 构建镜像
docker build -f Dockerfile.api -t taxi-api:latest .
docker build -f Dockerfile.ui -t taxi-ui:latest .

# 2. 创建网络
docker network create taxi-network

# 3. 运行 API
docker run -d \
  --name taxi-api \
  --network taxi-network \
  -p 8000:8000 \
  taxi-api:latest

# 4. 运行 UI
docker run -d \
  --name taxi-ui \
  --network taxi-network \
  -p 8501:8501 \
  -e API_BASE_URL=http://taxi-api:8000 \
  taxi-ui:latest

# 5. 查看状态
docker ps
```

---

## 🤖 TFX 模型训练

### 为什么需要 TFX？

当前 API 使用的是**规则算法**（基于规则的小费预测），准确率有限。使用 TFX 训练的**深度学习模型**可以达到 **77% 的准确率**。

### TFX Pipeline 组件

```
数据导入 → 统计生成 → Schema 生成 → 数据转换 → 模型训练
(ExampleGen) (StatisticsGen) (SchemaGen) (Transform) (Trainer)
```

### 训练模型

#### 方法 1: 使用 TFX Docker（推荐）

```bash
# 使用官方 TFX 镜像训练模型
docker run --rm --entrypoint="" \
  -v "$(pwd):/app" \
  tensorflow/tfx:0.21.4 \
  python3 /app/tfx_pipeline/taxi_pipeline_simple.py
```

**训练时间**: ~2-5 分钟  
**输出位置**: `tfx_pipeline/pipelines/chicago_taxi_simple/Trainer/model/`

#### 方法 2: 使用 Kubeflow Pipelines

```bash
# 编译 pipeline
python3 tfx_pipeline/taxi_pipeline_kubeflow.py --compile

# 上传到 Kubeflow
python3 tfx_pipeline/taxi_pipeline_kubeflow.py --upload --host http://localhost:8080

# 运行 pipeline
python3 tfx_pipeline/taxi_pipeline_kubeflow.py --run --host http://localhost:8080
```

### 训练结果

```
✅ 训练准确率: 75.02%
✅ 验证准确率: 77.10%
✅ 模型类型: Wide & Deep Neural Network
✅ 特征数量: 16 个特征
```

### 使用训练好的模型

训练完成后，需要使用 TFX 模型版本的 API：

```bash
# 1. 构建 TFX API 镜像（包含 TensorFlow）
docker build -f Dockerfile.tfx-api -t taxi-tfx-api:latest .

# 2. 运行 TFX API
docker run -d \
  --name taxi-api \
  --network taxi-network \
  -p 8000:8000 \
  -v "$(pwd)/tfx_pipeline:/app/tfx_pipeline" \
  taxi-tfx-api:latest
```

**注意**: TFX API 需要更多内存（~2GB）和更长的启动时间（~30秒）

### Apache Beam 说明

**TFX 内部使用 Apache Beam** 进行数据处理：

- ✅ **ExampleGen**: 使用 Beam 读取 CSV 数据
- ✅ **StatisticsGen**: 使用 Beam 计算统计信息
- ✅ **Transform**: 使用 Beam 进行数据转换
- ✅ **Trainer**: 训练过程使用 Beam 处理数据批次

**Beam 运行模式**:
- 本地运行: DirectRunner（默认）
- 分布式运行: DataflowRunner（需要 GCP）

查看 Beam 日志：
```bash
# TFX pipeline 运行时会显示 Beam 的执行日志
docker run --rm --entrypoint="" \
  -v "$(pwd):/app" \
  tensorflow/tfx:0.21.4 \
  python3 /app/tfx_pipeline/taxi_pipeline_simple.py 2>&1 | grep "apache_beam"
```

### 更多信息

详细的 TFX 训练指南请参考：
- [TFX 部署指南](TFX_DEPLOYMENT_GUIDE.md)
- [README_TFX.md](README_TFX.md)

---

## 🏗️ 项目架构

### 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                   用户浏览器                         │
│                                                     │
│  http://localhost:8501  │  http://localhost:8000  │
└────────────┬────────────┴──────────────┬───────────┘
             │                           │
             ▼                           ▼
┌─────────────────────┐      ┌─────────────────────┐
│   Streamlit UI      │      │    FastAPI          │
│   (taxi-ui)         │─────▶│    (taxi-api)       │
│   Port: 8501        │      │    Port: 8000       │
│                     │      │                     │
│   - 交互式界面      │      │   - 预测 API        │
│   - 数据可视化      │      │   - 健康检查        │
│   - 批量预测        │      │   - API 文档        │
└─────────────────────┘      └─────────────────────┘
```

### 目录结构

```
MLops_taxi/
├── api/                          # FastAPI 服务
│   ├── taxi_simple_api.py        # 规则算法 API
│   └── taxi_tfx_api.py           # TFX 模型 API
├── ui/                           # Streamlit UI
│   ├── streamlit_app.py          # 主应用
│   ├── feast_ui_integration.py   # Feast 集成
│   ├── kafka_ui_integration.py   # Kafka 集成
│   ├── mlflow_ui_integration.py  # MLflow 集成
│   └── mlmd_ui_integration.py    # MLMD 集成
├── tfx_pipeline/                 # TFX Pipeline
│   ├── taxi_pipeline_simple.py   # 简化 Pipeline
│   ├── taxi_pipeline_kubeflow.py # Kubeflow 集成
│   └── taxi_utils.py             # 数据处理和模型
├── k8s/                          # Kubernetes 配置
│   └── tfx-pipeline-job.yaml     # TFX Job
├── Dockerfile.api                # API 镜像定义
├── Dockerfile.ui                 # UI 镜像定义
├── docker-compose.yml            # Docker Compose 配置
└── README.md                     # 本文档
```

---

## 🐳 容器构建

### 1. API 容器 (Dockerfile.api)

**功能**: FastAPI 预测服务

**Dockerfile 内容**:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    numpy==1.26.0
COPY api/ /app/api/
EXPOSE 8000
CMD ["python3", "api/taxi_simple_api.py"]
```

**构建命令**:
```bash
docker build -f Dockerfile.api -t taxi-api:latest .
```

**镜像大小**: ~200 MB

### 2. UI 容器 (Dockerfile.ui)

**功能**: Streamlit 交互式界面

**Dockerfile 内容**:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    streamlit==1.28.0 \
    requests==2.31.0 \
    plotly==5.17.0 \
    pandas==2.1.1 \
    numpy==1.26.0
COPY ui/ /app/
EXPOSE 8501
ENV API_BASE_URL=http://api:8000
CMD ["streamlit", "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

**构建命令**:
```bash
docker build -f Dockerfile.ui -t taxi-ui:latest .
```

**镜像大小**: ~500 MB

### 3. 一次性构建所有镜像

```bash
# 使用 Docker Compose
docker-compose build

# 或手动构建
docker build -f Dockerfile.api -t taxi-api:latest .
docker build -f Dockerfile.ui -t taxi-ui:latest .
```

---

## 🎮 运行服务

### 方法 1: Docker Compose（推荐）

#### 启动服务
```bash
# 构建并启动（首次运行）
docker-compose up -d --build

# 仅启动（镜像已存在）
docker-compose up -d

# 前台运行（查看日志）
docker-compose up
```

#### 查看状态
```bash
# 查看运行的容器
docker-compose ps

# 查看日志
docker-compose logs

# 实时日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs api
docker-compose logs ui
```

#### 停止服务
```bash
# 停止服务
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止并删除容器、网络、卷
docker-compose down -v
```

### 方法 2: 手动运行

#### 创建网络
```bash
docker network create taxi-network
```

#### 启动 API
```bash
docker run -d \
  --name taxi-api \
  --network taxi-network \
  -p 8000:8000 \
  -v "$(pwd)/api:/app/api" \
  --restart unless-stopped \
  taxi-api:latest
```

#### 启动 UI
```bash
docker run -d \
  --name taxi-ui \
  --network taxi-network \
  -p 8501:8501 \
  -v "$(pwd)/ui:/app" \
  -e API_BASE_URL=http://taxi-api:8000 \
  --restart unless-stopped \
  taxi-ui:latest
```

#### 查看状态
```bash
docker ps
docker logs taxi-api
docker logs taxi-ui
```

#### 停止服务
```bash
docker stop taxi-api taxi-ui
docker rm taxi-api taxi-ui
```

---

## 📖 使用指南

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| **Streamlit UI** | http://localhost:8501 | 交互式预测界面 |
| **FastAPI** | http://localhost:8000 | 预测 API |
| **API 文档** | http://localhost:8000/docs | Swagger UI |
| **健康检查** | http://localhost:8000/health | API 状态 |

### 使用 UI 进行预测

1. 打开浏览器访问 http://localhost:8501
2. 在 "Tab 1: 小费预测" 中填写表单：
   - 行程距离: 5.2 英里
   - 车费: $15.50
   - 支付方式: Credit Card
   - 其他字段使用默认值
3. 点击 "预测小费" 按钮
4. 查看预测结果

### 使用 API 进行预测

#### 健康检查
```bash
curl http://localhost:8000/health
```

#### 预测请求
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "trip_miles": 5.2,
    "trip_seconds": 900,
    "fare": 15.50,
    "pickup_latitude": 41.8781,
    "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881,
    "dropoff_longitude": -87.6198,
    "pickup_hour": 14,
    "pickup_day_of_week": 2,
    "trip_start_day": 15,
    "trip_start_month": 6,
    "pickup_community_area": 32,
    "dropoff_community_area": 33,
    "pickup_census_tract": 0,
    "dropoff_census_tract": 0,
    "payment_type": "Credit Card",
    "company": "Taxi Affiliation Services"
  }'
```

#### 预期响应
```json
{
  "fare_amount": 15.5,
  "predicted_tip": 3.4,
  "tip_rate": 21.94,
  "total_cost": 18.9,
  "payment_type": "Credit Card",
  "trip_miles": 5.2,
  "pickup_hour": 14
}
```

---

## 💻 开发指南

### 本地开发

#### 修改 API 代码
```bash
# 1. 编辑 api/taxi_simple_api.py
# 2. 重启容器
docker-compose restart api
# 或
docker restart taxi-api
```

#### 修改 UI 代码
```bash
# 1. 编辑 ui/streamlit_app.py
# 2. 重启容器
docker-compose restart ui
# 或
docker restart taxi-ui
```

### 查看日志

```bash
# Docker Compose
docker-compose logs -f api
docker-compose logs -f ui

# 手动运行
docker logs -f taxi-api
docker logs -f taxi-ui
```

### 进入容器调试

```bash
# 进入 API 容器
docker exec -it taxi-api bash

# 进入 UI 容器
docker exec -it taxi-ui bash

# 测试 API 连接（在 UI 容器内）
docker exec -it taxi-ui curl http://taxi-api:8000/health
```

### 重新构建镜像

```bash
# Docker Compose
docker-compose build --no-cache

# 手动构建
docker build --no-cache -f Dockerfile.api -t taxi-api:latest .
docker build --no-cache -f Dockerfile.ui -t taxi-ui:latest .
```

---

## 🐛 故障排除

### 问题 1: 端口被占用

**症状**: `port is already allocated`

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :8000
lsof -i :8501

# 停止旧容器
docker-compose down
# 或
docker stop taxi-api taxi-ui && docker rm taxi-api taxi-ui
```

### 问题 2: UI 无法连接 API

**症状**: `Connection refused`

**检查**:
```bash
# 1. 确认 API 容器运行中
docker ps | grep taxi-api

# 2. 检查 API 健康
curl http://localhost:8000/health

# 3. 检查网络连接
docker exec taxi-ui curl http://taxi-api:8000/health

# 4. 检查环境变量
docker exec taxi-ui printenv | grep API_BASE_URL
```

**解决方案**:
```bash
# 重新创建容器，确保网络配置正确
docker-compose down
docker-compose up -d
```

### 问题 3: 容器启动失败

**检查日志**:
```bash
docker-compose logs api
docker-compose logs ui
```

**常见原因**:
- 依赖安装失败
- 代码语法错误
- 端口冲突

### 问题 4: 磁盘空间不足

**症状**: `No space left on device`

**解决方案**:
```bash
# 清理未使用的容器、镜像、网络
docker system prune -f

# 清理未使用的卷
docker volume prune -f

# 查看磁盘使用
docker system df
```

### 问题 5: 镜像构建慢

**优化方案**:
```bash
# 使用国内镜像源
# 在 Dockerfile 中添加：
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir ...
```

---

## 📊 性能监控

### 查看资源使用
```bash
# 实时监控
docker stats

# 查看特定容器
docker stats taxi-api taxi-ui
```

### 健康检查
```bash
# API 健康检查
curl http://localhost:8000/health

# 容器健康状态
docker inspect taxi-api | grep -A 10 "Health"
```

---

## 🔧 高级配置

### 自定义端口

编辑 `docker-compose.yml`:
```yaml
services:
  api:
    ports:
      - "8080:8000"  # 使用 8080 而不是 8000
  ui:
    ports:
      - "8502:8501"  # 使用 8502 而不是 8501
```

### 添加环境变量

编辑 `docker-compose.yml`:
```yaml
services:
  api:
    environment:
      - LOG_LEVEL=DEBUG
      - MAX_WORKERS=4
```

### 持久化数据

编辑 `docker-compose.yml`:
```yaml
services:
  api:
    volumes:
      - ./data:/app/data
      - ./models:/app/models
```

---

## 📚 相关文档

- [Docker 命令详解](DOCKER_COMMAND_EXPLAINED.md)
- [Docker 部署指南](DOCKER_DEPLOYMENT.md)
- [TFX 部署指南](TFX_DEPLOYMENT_GUIDE.md)
- [快速访问指南](QUICK_ACCESS.md)
- [最终总结](FINAL_SUMMARY.md)

---

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证

---

## 🙏 致谢

- [TensorFlow Extended (TFX)](https://www.tensorflow.org/tfx)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Streamlit](https://streamlit.io/)
- [Docker](https://www.docker.com/)

---

## 📞 支持

如有问题，请：
- 查看 [故障排除](#-故障排除) 部分
- 查看 [相关文档](#-相关文档)
- 提交 [GitHub Issue](https://github.com/your-repo/issues)

---

**最后更新**: 2025-09-29  
**版本**: 2.0.0  
**状态**: ✅ 生产就绪

---

Made with ❤️ using TFX, FastAPI, Streamlit, and Docker
