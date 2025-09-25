#!/usr/bin/env python3
"""
简化的 Chicago Taxi 特征定义
使用基础配置避免复杂的类型问题
"""

from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource, FeatureService
from feast.types import Float32, Int32, String
from feast.value_type import ValueType

# ===== 实体定义 =====

# 行程实体
trip_entity = Entity(
    name="trip_id",
    description="出租车行程唯一标识符",
    value_type=ValueType.STRING,
)

# ===== 数据源定义 =====

# 行程基础特征数据源
trip_source = FileSource(
    path="data/trip_features.parquet",
    timestamp_field="event_timestamp",
)

# ===== 特征视图定义 =====

# 行程基础特征视图
trip_features_view = FeatureView(
    name="trip_features",
    entities=[trip_entity],
    ttl=timedelta(days=7),
    schema=[
        Field(name="trip_miles", dtype=Float32),
        Field(name="trip_seconds", dtype=Int32),
        Field(name="fare", dtype=Float32),
        Field(name="pickup_hour", dtype=Int32),
        Field(name="pickup_day_of_week", dtype=Int32),
        Field(name="passenger_count", dtype=Int32),
        Field(name="payment_type", dtype=String),
    ],
    source=trip_source,
    tags={"team": "mlops", "type": "batch"},
)

# ===== 特征服务定义 =====

# 模型推理特征服务
model_inference_service = FeatureService(
    name="model_inference_v1",
    features=[
        trip_features_view[["trip_miles", "trip_seconds", "fare", 
                           "pickup_hour", "pickup_day_of_week", 
                           "passenger_count", "payment_type"]],
    ],
    tags={"service": "inference", "version": "v1"},
)
