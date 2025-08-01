#!/usr/bin/env python3
"""
Chicago Taxi 特征定义
定义出租车相关的实体、特征视图和特征服务
"""

from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource, FeatureService
from feast.types import Float32, Float64, Int32, Int64, String, UnixTimestamp


# ===== 实体定义 =====

# 行程实体
trip_entity = Entity(
    name="trip_id",
    description="出租车行程唯一标识符",
    value_type=String,
)

# 区域实体
area_entity = Entity(
    name="area_id", 
    description="社区区域标识符",
    value_type=Int32,
)

# 公司实体
company_entity = Entity(
    name="company_id",
    description="出租车公司标识符", 
    value_type=String,
)


# ===== 数据源定义 =====

# 行程基础特征数据源
trip_source = FileSource(
    name="trip_source",
    path="data/offline_store/trip_features.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# 区域聚合特征数据源
area_source = FileSource(
    name="area_source", 
    path="data/offline_store/area_features.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# 公司统计特征数据源
company_source = FileSource(
    name="company_source",
    path="data/offline_store/company_features.parquet", 
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# 实时特征数据源（来自 Kafka）
from feast.data_source import KafkaSource

kafka_source = KafkaSource(
    name="taxi_kafka_source",
    kafka_bootstrap_servers="localhost:9092",
    topic="taxi-features-realtime",
    timestamp_field="event_timestamp",
    batch_source=trip_source,  # 用于历史数据回填
)


# ===== 特征视图定义 =====

# 行程基础特征视图
trip_features_view = FeatureView(
    name="trip_features",
    entities=[trip_entity],
    ttl=timedelta(days=7),  # 特征存活时间
    schema=[
        Field(name="trip_miles", dtype=Float32, description="行程距离（英里）"),
        Field(name="trip_seconds", dtype=Int32, description="行程时长（秒）"),
        Field(name="fare", dtype=Float32, description="车费金额"),
        Field(name="pickup_latitude", dtype=Float64, description="上车纬度"),
        Field(name="pickup_longitude", dtype=Float64, description="上车经度"),
        Field(name="dropoff_latitude", dtype=Float64, description="下车纬度"),
        Field(name="dropoff_longitude", dtype=Float64, description="下车经度"),
        Field(name="pickup_hour", dtype=Int32, description="上车小时"),
        Field(name="pickup_day_of_week", dtype=Int32, description="上车星期几"),
        Field(name="pickup_month", dtype=Int32, description="上车月份"),
        Field(name="passenger_count", dtype=Int32, description="乘客数量"),
        Field(name="payment_type", dtype=String, description="支付方式"),
        Field(name="company", dtype=String, description="出租车公司"),
    ],
    source=trip_source,
    tags={"team": "mlops", "type": "batch"},
)

# 实时行程特征视图
trip_realtime_features_view = FeatureView(
    name="trip_realtime_features",
    entities=[trip_entity],
    ttl=timedelta(hours=1),  # 实时特征短期存活
    schema=[
        Field(name="current_speed", dtype=Float32, description="当前速度"),
        Field(name="estimated_duration", dtype=Int32, description="预估时长"),
        Field(name="traffic_level", dtype=String, description="交通状况"),
        Field(name="weather_condition", dtype=String, description="天气状况"),
        Field(name="demand_level", dtype=String, description="需求水平"),
    ],
    source=kafka_source,
    tags={"team": "mlops", "type": "streaming"},
)

# 区域聚合特征视图
area_features_view = FeatureView(
    name="area_features",
    entities=[area_entity],
    ttl=timedelta(days=30),
    schema=[
        Field(name="avg_trip_distance", dtype=Float32, description="平均行程距离"),
        Field(name="avg_trip_duration", dtype=Float32, description="平均行程时长"),
        Field(name="avg_fare", dtype=Float32, description="平均车费"),
        Field(name="trip_count_1h", dtype=Int32, description="1小时内行程数"),
        Field(name="trip_count_24h", dtype=Int32, description="24小时内行程数"),
        Field(name="pickup_density", dtype=Float32, description="上车点密度"),
        Field(name="dropoff_density", dtype=Float32, description="下车点密度"),
    ],
    source=area_source,
    tags={"team": "mlops", "type": "aggregated"},
)

# 公司统计特征视图
company_features_view = FeatureView(
    name="company_features", 
    entities=[company_entity],
    ttl=timedelta(days=30),
    schema=[
        Field(name="company_avg_fare", dtype=Float32, description="公司平均车费"),
        Field(name="company_trip_count", dtype=Int32, description="公司行程总数"),
        Field(name="company_rating", dtype=Float32, description="公司评分"),
        Field(name="company_active_drivers", dtype=Int32, description="活跃司机数"),
    ],
    source=company_source,
    tags={"team": "mlops", "type": "company_stats"},
)


# ===== 特征服务定义 =====

# 模型推理特征服务
model_inference_service = FeatureService(
    name="model_inference_v1",
    features=[
        trip_features_view[["trip_miles", "trip_seconds", "fare", "pickup_latitude", 
                           "pickup_longitude", "dropoff_latitude", "dropoff_longitude",
                           "pickup_hour", "pickup_day_of_week", "pickup_month", 
                           "passenger_count", "payment_type", "company"]],
        area_features_view[["avg_trip_distance", "avg_trip_duration", "avg_fare", 
                           "trip_count_1h", "pickup_density"]],
        company_features_view[["company_avg_fare", "company_rating"]],
    ],
    tags={"service": "inference", "version": "v1"},
)

# 实时推理特征服务
realtime_inference_service = FeatureService(
    name="realtime_inference_v1",
    features=[
        trip_features_view[["trip_miles", "trip_seconds", "pickup_latitude", 
                           "pickup_longitude", "pickup_hour", "pickup_day_of_week"]],
        trip_realtime_features_view[["current_speed", "estimated_duration", 
                                    "traffic_level", "weather_condition", "demand_level"]],
        area_features_view[["avg_fare", "trip_count_1h", "pickup_density"]],
    ],
    tags={"service": "realtime", "version": "v1"},
)

# 监控特征服务
monitoring_service = FeatureService(
    name="monitoring_v1",
    features=[
        trip_features_view,  # 所有基础特征用于监控
        area_features_view[["avg_trip_distance", "avg_trip_duration", "trip_count_24h"]],
        company_features_view[["company_trip_count", "company_rating"]],
    ],
    tags={"service": "monitoring", "version": "v1"},
)

# 训练特征服务
training_service = FeatureService(
    name="training_v1", 
    features=[
        trip_features_view,  # 所有历史特征
        area_features_view,  # 所有区域特征
        company_features_view,  # 所有公司特征
    ],
    tags={"service": "training", "version": "v1"},
)
