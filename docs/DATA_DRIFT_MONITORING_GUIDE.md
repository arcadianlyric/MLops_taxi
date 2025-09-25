# 📊 Chicago Taxi 数据漂移监控指南

## 🎯 **当前 TFDV 使用情况总结**

### ✅ **已实现的功能**

1. **基础数据验证**
   - `StatisticsGen`: 自动计算数据统计信息
   - `SchemaGen`: 基于统计信息生成数据模式
   - `ExampleValidator`: 基于模式进行异常检测

2. **推理时数据处理**
   - 在 `chicago_taxi_client.py` 中使用 TFDV 生成统计信息
   - 处理缺失值时使用统计信息填充默认值

3. **监控指标框架**
   - 在 `model_monitoring.py` 中定义了数据漂移指标
   - 配置了数据漂移告警规则

### ❌ **缺失的功能**

1. **持续数据漂移检测**
2. **自动化漂移监控 Pipeline**
3. **漂移可视化界面**
4. **实时漂移告警**

---

## 🚀 **完整数据漂移监控解决方案**

### 📦 **新增组件**

我们已经为您创建了完整的数据漂移监控组件：

1. **`components/data_drift_monitor.py`** - 核心漂移检测组件
2. **`examples/data_drift_monitoring_example.py`** - 使用示例

### 🔧 **核心特性**

#### 1. **多种漂移检测算法**
- **数值特征**: 基于均值和标准差变化
- **分类特征**: 使用 Jensen-Shannon 散度
- **自定义阈值**: 可配置漂移敏感度

#### 2. **全面的漂移分析**
```python
# 漂移分类
- 无漂移 (< 0.1)
- 轻微漂移 (0.1 - 0.3)
- 中等漂移 (0.3 - 0.5)
- 严重漂移 (> 0.5)
```

#### 3. **智能建议系统**
- 自动生成漂移处理建议
- 识别需要重点关注的特征
- 提供模型重训练建议

---

## 📋 **使用步骤**

### 1. **准备数据**

```bash
# 创建数据目录
mkdir -p data/baseline data/current

# 复制基线数据（训练时的数据）
cp your_training_data.csv data/baseline/

# 复制当前生产数据
cp your_production_data.csv data/current/
```

### 2. **运行漂移监控**

```python
from components.data_drift_monitor import DataDriftMonitor

# 在 TFX Pipeline 中使用
data_drift_monitor = DataDriftMonitor(
    baseline_examples=baseline_examples,
    current_examples=current_examples,
    schema=schema,
    drift_threshold=0.1,  # 漂移阈值
    feature_allowlist=[
        'trip_miles', 'fare', 'trip_seconds',
        'pickup_latitude', 'pickup_longitude',
        'payment_type', 'company'
    ]
)
```

### 3. **查看漂移报告**

```json
{
  "summary": {
    "overall_drift_detected": true,
    "drifted_features_count": 3,
    "total_features_checked": 8
  },
  "feature_details": {
    "trip_miles": {
      "drift_score": 0.25,
      "is_drifted": true,
      "drift_type": "轻微漂移"
    }
  },
  "recommendations": [
    "检测到数据漂移，建议重新训练模型",
    "特别关注严重漂移特征: payment_type"
  ]
}
```

---

## 📊 **集成到现有 Pipeline**

### 修改 `taxi_pipeline_native_keras.py`

```python
# 添加数据漂移监控
from components.data_drift_monitor import DataDriftMonitor

def _create_pipeline(...):
    # ... 现有组件 ...
    
    # 添加数据漂移监控
    data_drift_monitor = DataDriftMonitor(
        baseline_examples=baseline_example_gen.outputs['examples'],
        current_examples=example_gen.outputs['examples'],
        schema=schema_gen.outputs['schema'],
        drift_threshold=0.1
    )
    
    # 更新组件列表
    components = [
        example_gen,
        statistics_gen,
        schema_gen,
        example_validator,
        data_drift_monitor,  # 新增
        transform,
        trainer,
        # ... 其他组件
    ]
```

---

## 🔍 **监控指标集成**

### Prometheus 指标

```yaml
# 数据漂移指标
data_drift_overall:
  type: gauge
  description: "整体数据漂移状态"
  
data_drift_feature_score:
  type: gauge
  description: "特征级别漂移分数"
  labels: [feature_name, drift_type]
```

### Grafana 仪表板

```json
{
  "title": "数据漂移监控",
  "panels": [
    {
      "title": "整体漂移状态",
      "type": "stat",
      "targets": [{"expr": "data_drift_overall"}]
    },
    {
      "title": "特征漂移分数",
      "type": "graph",
      "targets": [{"expr": "data_drift_feature_score"}]
    }
  ]
}
```

---

## ⚡ **自动化部署**

### 1. **定时漂移检测**

```bash
# 创建 cron 任务
0 2 * * * /path/to/run_drift_monitoring.sh
```

### 2. **告警集成**

```yaml
# Prometheus 告警规则
groups:
  - name: data_drift_alerts
    rules:
      - alert: DataDriftDetected
        expr: data_drift_overall > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "检测到数据漂移"
          description: "Chicago Taxi 模型检测到数据漂移"
```

---

## 🎯 **最佳实践**

### 1. **漂移阈值设置**
- **保守**: 0.05 (高敏感度)
- **平衡**: 0.1 (推荐)
- **宽松**: 0.2 (低敏感度)

### 2. **监控频率**
- **实时**: 每小时检查
- **日常**: 每天检查
- **定期**: 每周检查

### 3. **响应策略**
- **轻微漂移**: 增加监控频率
- **中等漂移**: 准备模型重训练
- **严重漂移**: 立即重训练模型

---

## 📈 **效果评估**

### 预期收益

1. **提前发现问题**: 在模型性能下降前检测到数据变化
2. **自动化监控**: 减少人工检查工作量
3. **智能建议**: 提供具体的处理建议
4. **历史追踪**: 记录数据漂移历史趋势

### 成功指标

- 数据漂移检测准确率 > 90%
- 误报率 < 5%
- 监控响应时间 < 1小时
- 模型性能稳定性提升 20%

---

## 🔧 **故障排除**

### 常见问题

1. **统计信息生成失败**
   ```bash
   # 检查数据格式
   head -5 data/current/data.csv
   ```

2. **漂移分数异常**
   ```python
   # 检查特征分布
   import pandas as pd
   df = pd.read_csv('data/current/data.csv')
   df.describe()
   ```

3. **内存不足**
   ```python
   # 使用采样数据
   df_sample = df.sample(n=10000)
   ```

---

## 📚 **参考资源**

- [TensorFlow Data Validation 官方文档](https://www.tensorflow.org/tfx/data_validation)
- [数据漂移检测最佳实践](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
- [MLOps 监控指南](https://ml-ops.org/content/monitoring)

---

**总结**: 虽然项目已经使用了 TFDV 的基础功能，但我们现在提供了完整的数据漂移监控解决方案，包括自动检测、智能分析、可视化监控和告警集成。这将大大提升您的 MLOps 平台的数据质量监控能力！
