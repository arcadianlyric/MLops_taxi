# 集成TFX训练模型指南

## 当前状态

**现在使用的**: 基于规则的简单算法（不是ML模型）
**目标**: 使用TFX pipeline训练的真实Keras模型

## 步骤1: 安装TFX依赖

```bash
pip3 install -r tfx-requirements.txt
```

这将安装：
- TFX 1.14.0
- TensorFlow 2.13
- Apache Beam
- 其他兼容依赖

## 步骤2: 运行TFX Pipeline训练模型

```bash
cd /Users/yc/Documents/GitHub/tech_cs/projects/MLops/MLops_test
python3 tfx_pipeline/taxi_pipeline_native_keras.py
```

这将：
1. 读取 `tfx_pipeline/data/simple/data.csv`
2. 执行数据验证、转换
3. 训练Keras神经网络模型
4. 评估模型性能
5. 保存模型到 `tfx_pipeline/serving_model/chicago_taxi_native_keras/`

## 步骤3: 修改API使用训练的模型

创建新的API文件 `api/taxi_tfx_api.py`:

```python
import tensorflow as tf
import numpy as np

# 加载TFX训练的模型
MODEL_PATH = "tfx_pipeline/serving_model/chicago_taxi_native_keras/latest"
model = tf.keras.models.load_model(MODEL_PATH)

def predict_tip_with_tfx_model(trip: TaxiTripRequest) -> float:
    """使用TFX训练的模型预测tip"""
    
    # 准备特征（需要与训练时的特征一致）
    features = {
        'trip_miles': trip.trip_miles,
        'trip_seconds': trip.trip_seconds,
        'fare': trip.fare,
        'pickup_latitude': trip.pickup_latitude,
        'pickup_longitude': trip.pickup_longitude,
        'dropoff_latitude': trip.dropoff_latitude,
        'dropoff_longitude': trip.dropoff_longitude,
        'trip_start_hour': trip.pickup_hour,
        'trip_start_day': trip.trip_start_day,
        'trip_start_month': trip.trip_start_month,
        # ... 其他特征
    }
    
    # 模型推理
    prediction = model.predict(features)
    
    return float(prediction[0])
```

## 步骤4: 更新Dockerfile包含模型

```dockerfile
# 复制训练好的模型
COPY tfx_pipeline/serving_model/ /app/models/
```

## 步骤5: 重新构建和部署

```bash
# 构建新镜像
eval $(/opt/homebrew/bin/minikube docker-env)
docker build -f Dockerfile.app -t taxi-app:latest .

# 重启deployment
kubectl rollout restart deployment/fastapi -n taxi-app
```

## 对比

### 当前（规则算法）
```python
tip = fare × 15% × payment_mult × time_mult × distance_mult
```
- ❌ 不是机器学习
- ❌ 固定规则
- ✅ 简单快速
- ✅ 无需训练

### TFX模型（真实ML）
```python
tip = keras_model.predict(features)
```
- ✅ 真实的神经网络
- ✅ 从数据学习模式
- ✅ 考虑特征交互
- ❌ 需要训练时间
- ❌ 依赖复杂

## 快速验证方案

如果你想立即看到TFX模型的效果，可以：

1. **本地运行TFX pipeline**（不在K8s中）
```bash
python3 tfx_pipeline/taxi_pipeline_native_keras.py
```

2. **查看训练结果**
```bash
ls -la tfx_pipeline/serving_model/chicago_taxi_native_keras/
```

3. **本地测试模型**
```python
import tensorflow as tf
model = tf.keras.models.load_model('tfx_pipeline/serving_model/chicago_taxi_native_keras/latest')
# 测试预测
```

## 总结

**当前系统**: 
- ✅ K8s部署成功
- ✅ UI可以返回预测值
- ⚠️  使用规则算法（不是ML模型）

**下一步**:
- 运行TFX pipeline训练真实模型
- 集成模型到API
- 重新部署

**现在的优势**:
- 系统架构已经完成
- 可以快速替换预测算法
- 基础设施已就绪
