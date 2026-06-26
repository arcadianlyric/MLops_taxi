# Chicago Taxi 小费预测 -- MLOps 平台

[![CI/CD](https://github.com/arcadianlyric/MLops_taxi/actions/workflows/ci.yml/badge.svg)](https://github.com/arcadianlyric/MLops_taxi/actions)
[![Tests](https://img.shields.io/badge/tests-54%20passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/K8s-5%20pods-326CE5)](https://minikube.sigs.k8s.io/)

| UI | 批量预测 | 漂移监控 |
| :---: | :---: | :---: |
| <img src="img/UI.png" width="100%"> | <img src="img/UI_batch.png" width="100%"> | <img src="img/UI_drift.png" width="100%"> |

---

## 1. 成果与影响

### 概述

基于 Chicago 出租车数据的端到端 MLOps 平台。Kubernetes 默认 6 Pod（5 类服务）部署，62 项自动化测试，Prometheus/Grafana 可观测性，A/B 测试框架，漂移触发自动重训练，Agentic drift-to-retrain 控制面，Helm Chart 参数化部署。

### 量化指标

| 指标 | 数值 |
|------|------|
| **sklearn GradientBoosting R2** | 0.795 |
| **sklearn MAE** | $0.359 |
| **TF Wide & Deep 准确率** | 89.7% |
| **TF Wide & Deep AUC** | 0.95 |
| **自动化测试** | 62 项通过（5 个测试模块） |
| **API 端点** | 40+ |
| **K8s Pod 数** | 默认 6（2 个 FastAPI + Streamlit, MLflow, Prometheus, Grafana） |
| **数据量** | 15,002 条 Chicago 出租车行程 |

### 核心能力

- **模型服务**：三级降级链 TensorFlow Wide & Deep -> sklearn GradientBoosting -> 规则引擎
- **Prometheus + Grafana 监控**：预测延迟直方图、吞吐量计数器、模型精度仪表、漂移分数仪表、告警规则
- **A/B 测试框架**：加权流量分配，按变体统计延迟和预测结果
- **自动重训练**：漂移检测超阈值后台触发 sklearn 重训练，冷却机制，结果记录到 MLflow
- **Agentic drift-to-retrain 闭环**：Monitor -> policy guardrails -> evaluator -> optional retrain，输出 trace，且不自动 promotion 生产模型
- **MLflow 实验追踪**：独立 MLflow Pod，实验管理，模型注册，指标记录
- **可扩展 Serving**：有界并行 `/batch_predict`、可配置 batch 限制、进程内历史上限、2 个 FastAPI 副本、HPA 2-6 副本配置
- **Helm Chart**：参数化部署全部 5 个服务，可配置资源、监控开关、环境变量
- **DVC 集成**：训练数据版本控制
- **CI/CD**：GitHub Actions（lint, pytest, Docker build），push/PR 触发
- **9 页 Streamlit 仪表板**：预测、数据分析、漂移监控、Feast、Kafka、MLflow、MLMD

### MLOps 成熟度

按 Google MLOps 成熟度模型评估：
- **Level 0**（手动）：已超越。自动化训练、服务和测试已就绪。
- **Level 1**（ML Pipeline 自动化）：已达成。TFX Pipeline 代码完整，sklearn 流水线在 Docker 中端到端自动化。
- **Level 2**（CI/CD for ML）：部分达成。代码层面有 CI/CD；漂移触发自动重训练提供持续训练。模型制品的完整 CT/CD 流水线是剩余缺口。

---

## 2. 方法与实现

### 2.1 数据

- **来源**: [Chicago Data Portal -- Taxi Trips](https://data.cityofchicago.org/Transportation/Taxi-Trips/wrvz-psew)
- **规模**: 15,002 行，23 个特征
- **目标变量**: `tips`（sklearn 回归），`big_tipper`（TF 二分类，小费 > 车费 20%）
- **关键特征**: `trip_miles`, `trip_seconds`, `fare`, `payment_type`, `company`, `pickup_community_area`, `dropoff_community_area`, 时间特征（小时、星期、月份）
- **版本管理**: DVC 追踪 `tfx_pipeline/data/simple/data.csv`，包含元数据（行数、特征数、来源 URL）

### 2.2 模型

#### TensorFlow Wide & Deep（二分类）

架构参考 [Cheng et al., 2016](https://arxiv.org/abs/1606.07792)。Wide 部分捕获特征交叉的记忆性；Deep 部分通过 Embedding 提供泛化能力。

- **训练**: `tfx_pipeline/taxi_pipeline_native_keras.py`，通过 TFX + BeamDagRunner
- **组件**: CsvExampleGen, StatisticsGen, SchemaGen, ExampleValidator, Transform, Trainer, Evaluator, Pusher
- **独立训练**: `api/train_tf_model.py`（不依赖 TFX）
- **限制**: Docker 部署需要 x86 Linux（无 `linux/arm64` TensorFlow wheel）

#### Scikit-learn GradientBoosting（回归）

- **训练**: `api/train_model.py`，在 `docker build` 阶段执行
- **算法**: `GradientBoostingRegressor(n_estimators=200, max_depth=5, learning_rate=0.1)`
- **特征**: 8 个数值 + 2 个类别（Label Encoding）
- **选型理由**: 表格型回归的强基线；无 GPU 需求；推理速度快（<5ms）；输出确定性。对比方案：LinearRegression（R2=0.42），RandomForest（R2=0.77），XGBoost（R2=0.80，边际提升不值得增加依赖）

#### 规则引擎降级

基于支付方式、时间段、行程距离和车费的启发式规则。在无 ML 模型可用时提供优雅降级。

### 2.3 基础设施

#### Kubernetes 架构（5 Pod）

```
浏览器 (localhost)
  :8501 (UI)   :8000 (API)   :5000 (MLflow)   :9090 (Prometheus)   :3000 (Grafana)
     |              |              |                   |                    |
     v              v              v                   v                    v
 Streamlit      FastAPI        MLflow            Prometheus             Grafana
  Pod            Pod            Pod                Pod                   Pod
 (256Mi)       (512Mi)        (256Mi)            (128Mi)              (128Mi)
```

所有 Pod 运行在 minikube 的 `taxi-app` 命名空间。

**清单文件**：
- `k8s/taxi-app-simple.yaml` -- FastAPI, Streamlit, MLflow 部署和服务
- `k8s/monitoring.yaml` -- Prometheus（含告警规则）+ Grafana（含预配置数据源和仪表板）

**Helm Chart** (`helm/taxi-app/`)：参数化全部 5 个服务。`values.yaml` 关键配置：
- `fastapi.replicas`, `fastapi.resources`, `fastapi.env`（MLFLOW_TRACKING_URI, RETRAIN_COOLDOWN_MINUTES, DRIFT_RETRAIN_THRESHOLD）
- `monitoring.enabled`, `monitoring.prometheus.enabled`, `monitoring.grafana.enabled`

#### Docker

单一 `Dockerfile` 构建统一镜像：安装 Python 依赖（FastAPI, scikit-learn, mlflow, prometheus-client, prometheus-fastapi-instrumentator），复制源码，构建时训练 sklearn 模型。

#### CI/CD

GitHub Actions（`.github/workflows/ci.yml`）：checkout -> Python 3.9 -> pip install -> pytest -> Docker build。push 和 PR 触发。

### 2.4 监控与可观测性

#### Prometheus 指标

通过 `prometheus_fastapi_instrumentator` 暴露于 `/metrics/prometheus`：

| 指标 | 类型 | 标签 | 说明 |
|------|------|------|------|
| `model_prediction_latency_seconds` | Histogram | `model_type` | 预测延迟（含 P50/P95/P99 桶） |
| `model_prediction_total` | Counter | `model_type`, `status` | 按模型和成功/失败统计预测总数 |
| `data_drift_score` | Gauge | `feature` | 各特征当前漂移分数 |
| `model_accuracy` | Gauge | `model_name`, `metric` | 模型 R2, MAE, accuracy, AUC |
| `ab_test_assignment_total` | Counter | `experiment`, `variant` | A/B 测试流量分配计数 |
| `retrain_trigger_total` | Counter | `reason` | 按原因统计自动重训练触发次数 |

#### 告警规则（Prometheus）

- `ModelHighLatency`: P95 延迟 > 1s 持续 5 分钟
- `ModelAccuracyDrop`: R2 < 0.6 持续 10 分钟
- `DataDriftDetected`: 漂移分数 > 0.5 持续 15 分钟
- `HighErrorRate`: 错误率 > 5% 持续 5 分钟

#### Grafana 仪表板

预配置 8 个面板：预测 QPS、P95 延迟、模型 R2 分数、漂移分数、延迟时序图（P50/P95/P99）、按模型类型的预测分布、A/B 测试分配、重训练触发次数。

### 2.5 A/B 测试

`/ab/*` 端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/ab/experiments` | 列出所有实验 |
| POST | `/ab/experiments` | 创建实验（名称、变体含模型和权重） |
| GET | `/ab/experiments/{name}` | 实验详情和各变体统计 |
| POST | `/ab/predict` | 加权随机变体分配预测 |
| DELETE | `/ab/experiments/{name}` | 停止实验 |

启动时初始化默认实验 `tip-model-v1`：80% 对照组（sklearn）/ 20% 实验组（规则引擎）。变体选择采用加权随机采样。每次预测记录变体、模型、小费和延迟供后续分析。

### 2.6 自动重训练

`/retrain/*` 端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/retrain/trigger` | 手动触发重训练（含原因标签） |
| GET | `/retrain/status` | 当前重训练状态、冷却时间、模型元数据 |
| POST | `/retrain/auto-check` | 检测漂移，超阈值时触发重训练 |
| POST | `/agentic/drift-retrain/run` | Agentic 控制面：默认 dry-run，`execute=true` 时可触发重训练，但禁止自动模型 promotion |

**机制**: `/retrain/auto-check` 对 `trip_miles`, `fare`, `trip_seconds` 计算标准化均值差。若任一特征超过 `DRIFT_RETRAIN_THRESHOLD`（默认 0.3）且冷却期已过（`RETRAIN_COOLDOWN_MINUTES`，默认 30），后台任务：

1. 以子进程运行 `api/train_model.py`
2. 热加载新模型到运行中的进程
3. 更新 Prometheus 精度仪表
4. 将参数和指标记录到 MLflow

### 2.7 漂移检测

`/data/drift` 在数据集前半部分（基线）和后半部分（当前）之间计算漂移：
- **数值特征**: 标准化均值差（|mean_diff| / pooled_std），上限 1.0
- **类别特征**: Jensen-Shannon 散度
- **阈值**: 0.1 判定为漂移，分级为 无/低/中/高

### 2.8 测试

62 项测试，分 5 个模块：

| 模块 | 测试数 | 覆盖范围 |
|------|--------|----------|
| `test_api_core.py` | 10 | 健康检查、预测、批量、指标 |
| `test_api_data.py` | 7 | 数据统计、漂移检测 |
| `test_api_advanced.py` | 21 | Feast、Kafka、MLflow、MLMD |
| `test_api_phase2.py` | 16 | A/B 测试、自动重训练、Prometheus |
| `test_agentic_drift_retrain.py` | 5 | Agentic 漂移监控、策略、重训练建议、API dry-run |

```bash
pytest tests/ -v
```

---

## 3. 讨论与未来工作

### 当前优势

- 模型降级链保证韧性：即使 TF 和 sklearn 都失败，API 仍能通过规则引擎返回预测。
- Prometheus 指标无需外部依赖即可提供模型行为的实时可视性。
- A/B 测试轻量化（内存状态），无需基础设施变更即可运行实验。
- 自动重训练闭合了从漂移检测到模型更新的反馈循环。

### 已知限制

- **TFX/TFDV/KServe/Beam**: `components/` 和 `tfx_pipeline/` 中有完整实现，但无法在 ARM Mac Docker 上运行。需要 x86 Linux 集群。详见 `components/data_drift_monitor.py`, `components/kfserving_deployer.py`, `tfx_pipeline/taxi_pipeline_native_keras.py`。
- **A/B 状态在内存中**: Pod 重启后实验结果丢失。生产环境需要 Redis 或数据库后端。
- **单副本**: 当前每个服务部署 1 个副本，未配置水平扩展。
- **无模型制品版本管理**: 自动重训练原地覆盖模型文件。生产系统应在 MLflow Model Registry 或对象存储中管理版本。
- **Grafana 仪表板**: 通过 ConfigMap 预配置。生产环境应使用持久化存储和 Grafana API 管理。

### 未来工作

- **完整 CT/CD 流水线**: 自动化模型制品从 staging 到 production 的升级，含门控评估。
- **KServe 集成**: 在 x86 集群上部署 Knative + Istio，实现金丝雀发布和自动扩缩。
- **Feature Store**: 将自包含 Feast mock 替换为 Redis 支持的真实 Feast 部署。
- **Horizontal Pod Autoscaler**: 基于 Prometheus 预测 QPS 指标扩缩 FastAPI 副本。
- **持久化 A/B 状态**: 将实验结果存入 PostgreSQL 或 Redis。
- **多模型服务**: 通过 KServe InferenceService 同时服务 TF 和 sklearn 模型，实现真正的模型对比。

---

## 快速开始

### 前置条件

- Docker 已安装
- minikube 已安装
- 端口 8000, 8501 可用

### Kubernetes 部署

```bash
# 启动 minikube
minikube start --memory=4096 --cpus=2

# 在 minikube 内构建镜像
eval $(minikube docker-env)
docker build -t taxi-app:latest -f Dockerfile .

# 部署应用 + 监控
kubectl apply -f k8s/taxi-app-simple.yaml
kubectl apply -f k8s/monitoring.yaml

# 等待全部 5 个 Pod 就绪
kubectl get pods -n taxi-app

# 端口转发
kubectl port-forward -n taxi-app svc/fastapi-service 8000:8000 &
kubectl port-forward -n taxi-app svc/streamlit-service 8501:8501 &
kubectl port-forward -n taxi-app svc/prometheus-service 9090:9090 &
kubectl port-forward -n taxi-app svc/grafana-service 3000:3000 &
```

### Helm 部署

```bash
helm install taxi-app helm/taxi-app/ -n taxi-app --create-namespace
```

### 访问服务

| 服务 | 地址 |
|------|------|
| Streamlit UI | http://localhost:8501 |
| FastAPI / Swagger | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000（admin/admin） |
| MLflow | http://localhost:5000 |

---

## 关键文件

| 文件 | 说明 |
|------|------|
| `api/taxi_full_api.py` | FastAPI 后端：40+ 端点，sklearn 模型，Prometheus 指标，A/B 测试，自动重训练 |
| `agentic/` | Agentic drift-to-retrain 闭环：monitor、policy guardrails、evaluator、retrainer、orchestrator |
| `api/train_model.py` | sklearn GradientBoosting 训练脚本 |
| `api/train_tf_model.py` | TF Wide & Deep 独立训练 |
| `ui/streamlit_app.py` | Streamlit 9 页仪表板 |
| `tfx_pipeline/taxi_pipeline_native_keras.py` | TFX ML Pipeline（仅 x86） |
| `k8s/taxi-app-simple.yaml` | K8s 清单：FastAPI, Streamlit, MLflow |
| `k8s/monitoring.yaml` | K8s 清单：Prometheus, Grafana |
| `helm/taxi-app/` | Helm Chart 参数化部署 |
| `Dockerfile` | 统一镜像（API + UI + sklearn 训练 + Prometheus） |
| `.github/workflows/ci.yml` | CI/CD 流水线 |
| `tests/` | 62 项自动化测试（5 个模块） |
| `.dvc/` | DVC 数据版本管理配置 |
| `components/` | TFX 自定义组件（漂移监控、KServe 部署器、告警管理、模型监控） |
| `docs/PROJECT_ANALYSIS.md` | 项目成熟度分析 |

---
