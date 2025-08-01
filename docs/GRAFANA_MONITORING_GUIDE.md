# Grafana 监控界面使用指南

## 🚀 快速访问

**Grafana 地址**: http://localhost:3000
**登录信息**: admin / admin123

## 📊 界面导航

### 1. 主要菜单结构

```
🏠 Home (首页)
├── 📊 Dashboards (仪表板)
├── 🔍 Explore (数据探索)
├── 🚨 Alerting (告警)
├── 🔧 Configuration (配置)
└── 👤 Admin (管理)
```

### 2. 核心功能区域

#### 📊 Dashboards (仪表板)
- **Browse**: 浏览所有仪表板
- **Manage**: 管理仪表板文件夹
- **Playlists**: 仪表板播放列表
- **Snapshots**: 仪表板快照

#### 🔍 Explore (数据探索)
- 实时查询 Prometheus 指标
- 查看 Loki 日志
- 创建临时图表

#### 🚨 Alerting (告警)
- **Alert Rules**: 告警规则
- **Contact Points**: 联系点
- **Notification Policies**: 通知策略

## 📈 预配置的监控仪表板

### 1. Kubernetes 集群监控

**路径**: Dashboards → Browse → Kubernetes

#### 🖥️ **Node Exporter Full**
- **用途**: 监控 Kubernetes 节点资源
- **关键指标**:
  - CPU 使用率
  - 内存使用率
  - 磁盘 I/O
  - 网络流量
  - 系统负载

#### 📦 **Kubernetes Cluster Monitoring**
- **用途**: 集群整体状态监控
- **关键指标**:
  - Pod 状态统计
  - Node 健康状态
  - 资源配额使用
  - 集群事件

### 2. 应用监控

#### 🚀 **MLOps API 监控**
- **用途**: FastAPI 应用性能监控
- **关键指标**:
  - 请求数量 (QPS)
  - 响应时间
  - 错误率
  - 预测成功率

#### 🔧 **Kubeflow Pipelines 监控**
- **用途**: ML 流水线执行监控
- **关键指标**:
  - Pipeline 执行状态
  - 任务完成时间
  - 资源使用情况

## 🔍 如何使用 Explore 功能

### 1. 访问 Explore
1. 点击左侧菜单的 **🔍 Explore**
2. 选择数据源 (Prometheus 或 Loki)

### 2. Prometheus 指标查询

#### 基础查询示例:

```promql
# 查看所有运行中的服务
up

# CPU 使用率
rate(cpu_usage_seconds_total[5m])

# 内存使用率
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes

# API 请求率
rate(http_requests_total[5m])

# Pod 重启次数
increase(kube_pod_container_status_restarts_total[1h])
```

#### 高级查询示例:

```promql
# 按命名空间分组的 Pod 数量
count by (namespace) (kube_pod_info)

# 95% 响应时间
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 错误率
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

### 3. Loki 日志查询

#### 基础日志查询:

```logql
# 查看所有日志
{job="kubernetes-pods"}

# 查看特定命名空间的日志
{namespace="monitoring"}

# 查看错误日志
{job="kubernetes-pods"} |= "error"

# 查看 FastAPI 应用日志
{namespace="mlops-system", app="mlops-api"}
```

## 📊 创建自定义仪表板

### 1. 创建新仪表板

1. 点击 **+ 图标** → **Dashboard**
2. 点击 **Add new panel**
3. 配置查询和可视化

### 2. 面板配置

#### 📈 **时间序列图表**
- **用途**: 显示指标随时间变化
- **适用于**: CPU、内存、请求率等

#### 📊 **统计面板**
- **用途**: 显示单个数值
- **适用于**: 当前 Pod 数量、错误计数等

#### 📋 **表格面板**
- **用途**: 显示结构化数据
- **适用于**: Pod 列表、服务状态等

#### 🗺️ **热力图**
- **用途**: 显示数据分布
- **适用于**: 响应时间分布、负载分布等

### 3. MLOps 专用仪表板模板

#### 🤖 **ML 模型监控仪表板**

```json
{
  "panels": [
    {
      "title": "预测请求数",
      "type": "stat",
      "query": "rate(prediction_requests_total[5m])"
    },
    {
      "title": "模型准确率",
      "type": "gauge",
      "query": "model_accuracy"
    },
    {
      "title": "预测延迟",
      "type": "timeseries",
      "query": "histogram_quantile(0.95, prediction_duration_seconds_bucket)"
    },
    {
      "title": "数据漂移检测",
      "type": "timeseries",
      "query": "data_drift_score"
    }
  ]
}
```

## 🚨 设置告警

### 1. 创建告警规则

1. 进入 **Alerting** → **Alert Rules**
2. 点击 **New rule**
3. 配置查询条件和阈值

### 2. 常用告警规则

#### 🔴 **高 CPU 使用率**
```yaml
条件: avg(cpu_usage_percent) > 80
持续时间: 5m
严重程度: warning
```

#### 🔴 **Pod 重启频繁**
```yaml
条件: increase(kube_pod_container_status_restarts_total[10m]) > 3
持续时间: 1m
严重程度: critical
```

#### 🔴 **API 错误率过高**
```yaml
条件: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
持续时间: 2m
严重程度: warning
```

## 📱 移动端访问

Grafana 支持响应式设计，可以在手机或平板上访问：
- 使用相同的 URL: http://localhost:3000
- 自动适配移动端界面
- 支持触摸操作和缩放

## 🔧 高级配置

### 1. 数据源配置

#### Prometheus 数据源
```yaml
URL: http://prometheus-server:80
Access: Server (default)
Scrape interval: 15s
```

#### Loki 数据源
```yaml
URL: http://loki:3100
Access: Server (default)
```

### 2. 用户权限管理

1. 进入 **Configuration** → **Users**
2. 创建不同角色用户:
   - **Admin**: 完全访问权限
   - **Editor**: 编辑仪表板权限
   - **Viewer**: 只读权限

### 3. 组织管理

1. 进入 **Configuration** → **Organizations**
2. 为不同团队创建独立组织
3. 分配用户到对应组织

## 💡 最佳实践

### 1. 仪表板设计
- 使用有意义的标题和描述
- 合理安排面板布局
- 设置适当的时间范围
- 使用变量提高复用性

### 2. 查询优化
- 避免过于复杂的查询
- 使用适当的时间窗口
- 利用标签过滤减少数据量
- 定期清理无用的查询

### 3. 告警策略
- 设置合理的阈值
- 避免告警风暴
- 配置告警分组
- 定期审查告警规则

## 🎯 MLOps 特定监控指标

### 模型性能指标
- 预测准确率
- 预测延迟
- 吞吐量 (QPS)
- 数据漂移分数

### 基础设施指标
- Pod 资源使用率
- 存储使用情况
- 网络流量
- 服务可用性

### 业务指标
- 用户请求数
- 功能使用率
- 错误分布
- 用户满意度

## 📚 快速参考

### 常用快捷键
- `Ctrl/Cmd + S`: 保存仪表板
- `d + v`: 切换到查看模式
- `d + e`: 切换到编辑模式
- `d + s`: 打开仪表板设置
- `?`: 显示帮助

### 时间范围快捷选择
- `Last 5 minutes`: 最近 5 分钟
- `Last 15 minutes`: 最近 15 分钟
- `Last 1 hour`: 最近 1 小时
- `Last 24 hours`: 最近 24 小时
- `Last 7 days`: 最近 7 天

现在您可以充分利用 Grafana 来监控您的 MLOps 平台了！🚀
