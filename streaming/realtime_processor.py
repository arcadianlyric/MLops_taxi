#!/usr/bin/env python3
"""
高性能 Kafka 实时流处理器
Chicago Taxi MLOps 平台核心流处理组件
"""

import json
import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading

import numpy as np
import pandas as pd
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import requests
import redis
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TaxiRawData:
    """原始出租车数据模型"""
    trip_id: str
    pickup_datetime: str
    dropoff_datetime: str
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    passenger_count: int
    trip_distance: float
    fare_amount: float
    payment_type: str
    company: str
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ProcessedFeatures:
    """处理后的特征数据模型"""
    trip_id: str
    event_timestamp: str
    
    # 基础特征
    trip_miles: float
    trip_seconds: int
    fare: float
    
    # 地理特征
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    pickup_area_id: int
    dropoff_area_id: int
    
    # 时间特征
    pickup_hour: int
    pickup_day_of_week: int
    pickup_month: int
    is_weekend: bool
    is_holiday: bool
    
    # 计算特征
    haversine_distance: float
    manhattan_distance: float
    bearing: float
    speed_mph: float
    
    # 聚合特征
    area_avg_fare: float
    area_trip_count_1h: int
    company_avg_fare: float
    
    # 实时特征
    current_demand: float
    traffic_level: str
    weather_condition: str
    surge_multiplier: float
    
    # 元数据
    processing_timestamp: str
    feature_version: str = "v1.0"
    
    def __post_init__(self):
        if self.processing_timestamp is None:
            self.processing_timestamp = datetime.now().isoformat()


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        # Prometheus 指标
        self.messages_processed = Counter(
            'kafka_messages_processed_total',
            'Total processed messages',
            ['topic', 'status']
        )
        
        self.processing_duration = Histogram(
            'kafka_processing_duration_seconds',
            'Message processing duration',
            ['processor_type']
        )
        
        self.feature_count = Gauge(
            'features_generated_total',
            'Total features generated',
            ['feature_type']
        )
        
        self.error_count = Counter(
            'kafka_processing_errors_total',
            'Total processing errors',
            ['error_type']
        )
        
        self.throughput = Gauge(
            'kafka_throughput_messages_per_second',
            'Messages processed per second'
        )
        
        # 内部计数器
        self._message_count = 0
        self._start_time = time.time()
        self._last_throughput_update = time.time()
    
    def record_message_processed(self, topic: str, status: str = "success"):
        """记录消息处理"""
        self.messages_processed.labels(topic=topic, status=status).inc()
        self._message_count += 1
        
        # 更新吞吐量（每10秒更新一次）
        current_time = time.time()
        if current_time - self._last_throughput_update >= 10:
            elapsed = current_time - self._start_time
            if elapsed > 0:
                throughput = self._message_count / elapsed
                self.throughput.set(throughput)
            self._last_throughput_update = current_time
    
    def record_processing_time(self, processor_type: str, duration: float):
        """记录处理时间"""
        self.processing_duration.labels(processor_type=processor_type).observe(duration)
    
    def record_feature_generated(self, feature_type: str, count: int = 1):
        """记录特征生成"""
        self.feature_count.labels(feature_type=feature_type).inc(count)
    
    def record_error(self, error_type: str):
        """记录错误"""
        self.error_count.labels(error_type=error_type).inc()


class FeatureProcessor:
    """特征处理器"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.logger = logging.getLogger(f"{__name__}.FeatureProcessor")
        
        # 缓存的聚合数据
        self._area_cache = {}
        self._company_cache = {}
        self._cache_ttl = 300  # 5分钟缓存
        self._last_cache_update = 0
    
    def process_raw_data(self, raw_data: TaxiRawData) -> ProcessedFeatures:
        """处理原始数据生成特征"""
        
        try:
            # 解析时间
            pickup_dt = pd.to_datetime(raw_data.pickup_datetime)
            dropoff_dt = pd.to_datetime(raw_data.dropoff_datetime)
            
            # 计算基础特征
            trip_seconds = int((dropoff_dt - pickup_dt).total_seconds())
            trip_seconds = max(60, trip_seconds)  # 最少1分钟
            
            # 地理特征计算
            haversine_dist = self._calculate_haversine_distance(
                raw_data.pickup_latitude, raw_data.pickup_longitude,
                raw_data.dropoff_latitude, raw_data.dropoff_longitude
            )
            
            manhattan_dist = self._calculate_manhattan_distance(
                raw_data.pickup_latitude, raw_data.pickup_longitude,
                raw_data.dropoff_latitude, raw_data.dropoff_longitude
            )
            
            bearing = self._calculate_bearing(
                raw_data.pickup_latitude, raw_data.pickup_longitude,
                raw_data.dropoff_latitude, raw_data.dropoff_longitude
            )
            
            # 速度计算
            speed_mph = (raw_data.trip_distance / (trip_seconds / 3600)) if trip_seconds > 0 else 0
            speed_mph = min(speed_mph, 80)  # 限制最大速度
            
            # 区域ID计算
            pickup_area_id = self._get_area_id(raw_data.pickup_latitude, raw_data.pickup_longitude)
            dropoff_area_id = self._get_area_id(raw_data.dropoff_latitude, raw_data.dropoff_longitude)
            
            # 时间特征
            is_weekend = pickup_dt.weekday() >= 5
            is_holiday = self._is_holiday(pickup_dt)
            
            # 获取聚合特征
            area_features = self._get_area_features(pickup_area_id)
            company_features = self._get_company_features(raw_data.company)
            
            # 实时特征
            realtime_features = self._get_realtime_features(
                raw_data.pickup_latitude, raw_data.pickup_longitude, pickup_dt
            )
            
            # 构建特征对象
            features = ProcessedFeatures(
                trip_id=raw_data.trip_id,
                event_timestamp=raw_data.pickup_datetime,
                
                # 基础特征
                trip_miles=raw_data.trip_distance,
                trip_seconds=trip_seconds,
                fare=raw_data.fare_amount,
                
                # 地理特征
                pickup_latitude=raw_data.pickup_latitude,
                pickup_longitude=raw_data.pickup_longitude,
                dropoff_latitude=raw_data.dropoff_latitude,
                dropoff_longitude=raw_data.dropoff_longitude,
                pickup_area_id=pickup_area_id,
                dropoff_area_id=dropoff_area_id,
                
                # 时间特征
                pickup_hour=pickup_dt.hour,
                pickup_day_of_week=pickup_dt.weekday(),
                pickup_month=pickup_dt.month,
                is_weekend=is_weekend,
                is_holiday=is_holiday,
                
                # 计算特征
                haversine_distance=haversine_dist,
                manhattan_distance=manhattan_dist,
                bearing=bearing,
                speed_mph=speed_mph,
                
                # 聚合特征
                area_avg_fare=area_features.get("avg_fare", 12.0),
                area_trip_count_1h=area_features.get("trip_count_1h", 10),
                company_avg_fare=company_features.get("avg_fare", 12.0),
                
                # 实时特征
                current_demand=realtime_features.get("demand", 1.0),
                traffic_level=realtime_features.get("traffic", "normal"),
                weather_condition=realtime_features.get("weather", "clear"),
                surge_multiplier=realtime_features.get("surge", 1.0),
                
                processing_timestamp=datetime.now().isoformat()
            )
            
            return features
            
        except Exception as e:
            self.logger.error(f"特征处理失败: {e}")
            raise
    
    def _calculate_haversine_distance(self, lat1: float, lon1: float, 
                                    lat2: float, lon2: float) -> float:
        """计算两点间的球面距离"""
        R = 3959  # 地球半径（英里）
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def _calculate_manhattan_distance(self, lat1: float, lon1: float,
                                    lat2: float, lon2: float) -> float:
        """计算曼哈顿距离"""
        # 简化的曼哈顿距离计算（基于经纬度差）
        lat_diff = abs(lat2 - lat1) * 69  # 1度纬度约69英里
        lon_diff = abs(lon2 - lon1) * 54.6  # 1度经度约54.6英里（芝加哥纬度）
        
        return lat_diff + lon_diff
    
    def _calculate_bearing(self, lat1: float, lon1: float,
                         lat2: float, lon2: float) -> float:
        """计算方位角"""
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        
        dlon = lon2 - lon1
        y = np.sin(dlon) * np.cos(lat2)
        x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
        
        bearing = np.degrees(np.arctan2(y, x))
        return (bearing + 360) % 360
    
    def _get_area_id(self, lat: float, lon: float) -> int:
        """根据经纬度获取区域ID"""
        # 简化的区域映射（基于芝加哥网格）
        lat_grid = int((lat - 41.6) * 100)
        lon_grid = int((lon + 88.0) * 100)
        
        return abs(lat_grid * 1000 + lon_grid) % 100 + 1
    
    def _is_holiday(self, dt: datetime) -> bool:
        """判断是否为节假日"""
        # 简化的节假日判断
        holidays = [
            (1, 1),   # 新年
            (7, 4),   # 独立日
            (12, 25), # 圣诞节
        ]
        
        return (dt.month, dt.day) in holidays
    
    def _get_area_features(self, area_id: int) -> Dict[str, Any]:
        """获取区域聚合特征"""
        current_time = time.time()
        
        # 检查缓存
        if (current_time - self._last_cache_update > self._cache_ttl or 
            area_id not in self._area_cache):
            self._update_area_cache(area_id)
        
        return self._area_cache.get(area_id, {
            "avg_fare": 12.0,
            "trip_count_1h": 10,
            "avg_distance": 3.0
        })
    
    def _get_company_features(self, company: str) -> Dict[str, Any]:
        """获取公司聚合特征"""
        current_time = time.time()
        
        # 检查缓存
        if (current_time - self._last_cache_update > self._cache_ttl or 
            company not in self._company_cache):
            self._update_company_cache(company)
        
        return self._company_cache.get(company, {
            "avg_fare": 12.0,
            "rating": 4.2,
            "trip_count": 100
        })
    
    def _get_realtime_features(self, lat: float, lon: float, dt: datetime) -> Dict[str, Any]:
        """获取实时特征"""
        # 模拟实时特征（实际应用中从外部API获取）
        hour = dt.hour
        
        # 需求模拟
        if hour in [7, 8, 17, 18, 19]:  # 高峰时段
            demand = np.random.uniform(1.5, 2.5)
            surge = np.random.uniform(1.2, 1.8)
            traffic = "heavy"
        elif hour >= 22 or hour <= 5:  # 夜间
            demand = np.random.uniform(0.3, 0.8)
            surge = np.random.uniform(1.0, 1.3)
            traffic = "light"
        else:  # 正常时段
            demand = np.random.uniform(0.8, 1.5)
            surge = np.random.uniform(1.0, 1.2)
            traffic = "normal"
        
        # 天气模拟
        weather_conditions = ["clear", "cloudy", "rainy", "snowy"]
        weather = np.random.choice(weather_conditions, p=[0.6, 0.2, 0.15, 0.05])
        
        return {
            "demand": demand,
            "surge": surge,
            "traffic": traffic,
            "weather": weather
        }
    
    def _update_area_cache(self, area_id: int):
        """更新区域缓存"""
        # 从 Redis 或数据库获取区域统计
        if self.redis_client:
            try:
                area_key = f"area_stats:{area_id}"
                area_data = self.redis_client.hgetall(area_key)
                
                if area_data:
                    self._area_cache[area_id] = {
                        "avg_fare": float(area_data.get("avg_fare", 12.0)),
                        "trip_count_1h": int(area_data.get("trip_count_1h", 10)),
                        "avg_distance": float(area_data.get("avg_distance", 3.0))
                    }
                else:
                    # 生成模拟数据
                    self._area_cache[area_id] = {
                        "avg_fare": np.random.normal(12.0, 3.0),
                        "trip_count_1h": np.random.poisson(15),
                        "avg_distance": np.random.exponential(3.0)
                    }
            except Exception as e:
                self.logger.warning(f"Redis 区域缓存更新失败: {e}")
        
        self._last_cache_update = time.time()
    
    def _update_company_cache(self, company: str):
        """更新公司缓存"""
        # 从 Redis 或数据库获取公司统计
        if self.redis_client:
            try:
                company_key = f"company_stats:{company}"
                company_data = self.redis_client.hgetall(company_key)
                
                if company_data:
                    self._company_cache[company] = {
                        "avg_fare": float(company_data.get("avg_fare", 12.0)),
                        "rating": float(company_data.get("rating", 4.2)),
                        "trip_count": int(company_data.get("trip_count", 100))
                    }
                else:
                    # 生成模拟数据
                    self._company_cache[company] = {
                        "avg_fare": np.random.normal(12.0, 2.0),
                        "rating": np.random.normal(4.2, 0.3),
                        "trip_count": np.random.poisson(150)
                    }
            except Exception as e:
                self.logger.warning(f"Redis 公司缓存更新失败: {e}")


class RealtimeStreamProcessor:
    """实时流处理器主类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.RealtimeStreamProcessor")
        
        # 初始化组件
        self.metrics = MetricsCollector()
        self.feature_processor = FeatureProcessor()
        
        # Kafka 配置
        self.kafka_config = {
            'bootstrap_servers': config.get('kafka_servers', ['localhost:9092']),
            'value_serializer': lambda x: json.dumps(x, default=str).encode('utf-8'),
            'value_deserializer': lambda x: json.loads(x.decode('utf-8')),
        }
        
        # 初始化 Kafka 客户端
        self.producer = None
        self.consumer = None
        
        # 处理状态
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=config.get('max_workers', 4))
        
        # Redis 连接
        try:
            self.redis_client = redis.Redis(
                host=config.get('redis_host', 'localhost'),
                port=config.get('redis_port', 6379),
                db=config.get('redis_db', 0),
                decode_responses=True
            )
            self.redis_client.ping()
            self.feature_processor.redis_client = self.redis_client
        except Exception as e:
            self.logger.warning(f"Redis 连接失败: {e}")
            self.redis_client = None
    
    def start(self):
        """启动流处理器"""
        self.logger.info("启动实时流处理器...")
        
        try:
            # 初始化 Kafka 客户端
            self._initialize_kafka()
            
            # 启动指标服务器
            metrics_port = self.config.get('metrics_port', 8080)
            start_http_server(metrics_port)
            self.logger.info(f"指标服务器启动在端口 {metrics_port}")
            
            # 启动处理循环
            self.running = True
            self._process_messages()
            
        except Exception as e:
            self.logger.error(f"流处理器启动失败: {e}")
            raise
    
    def stop(self):
        """停止流处理器"""
        self.logger.info("停止实时流处理器...")
        
        self.running = False
        
        if self.consumer:
            self.consumer.close()
        
        if self.producer:
            self.producer.close()
        
        self.executor.shutdown(wait=True)
        
        self.logger.info("流处理器已停止")
    
    def _initialize_kafka(self):
        """初始化 Kafka 客户端"""
        try:
            # 创建生产者
            producer_config = self.kafka_config.copy()
            producer_config.update({
                'acks': 'all',
                'retries': 3,
                'batch_size': 16384,
                'linger_ms': 10,
                'buffer_memory': 33554432,
            })
            
            self.producer = KafkaProducer(**producer_config)
            
            # 创建消费者
            consumer_config = self.kafka_config.copy()
            consumer_config.update({
                'group_id': self.config.get('consumer_group', 'realtime-processor'),
                'auto_offset_reset': 'latest',
                'enable_auto_commit': True,
                'auto_commit_interval_ms': 1000,
                'max_poll_records': 100,
            })
            
            input_topics = self.config.get('input_topics', ['taxi-raw-data'])
            self.consumer = KafkaConsumer(*input_topics, **consumer_config)
            
            self.logger.info(f"Kafka 客户端初始化成功，监听主题: {input_topics}")
            
        except Exception as e:
            self.logger.error(f"Kafka 客户端初始化失败: {e}")
            raise
    
    def _process_messages(self):
        """处理消息主循环"""
        self.logger.info("开始处理消息...")
        
        while self.running:
            try:
                # 批量获取消息
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    continue
                
                # 处理每个分区的消息
                for topic_partition, messages in message_batch.items():
                    self.logger.debug(f"处理 {len(messages)} 条消息来自 {topic_partition}")
                    
                    # 并行处理消息
                    futures = []
                    for message in messages:
                        future = self.executor.submit(self._process_single_message, message)
                        futures.append(future)
                    
                    # 等待处理完成
                    for future in futures:
                        try:
                            future.result(timeout=30)  # 30秒超时
                        except Exception as e:
                            self.logger.error(f"消息处理失败: {e}")
                            self.metrics.record_error("message_processing")
                
            except Exception as e:
                self.logger.error(f"消息批处理失败: {e}")
                self.metrics.record_error("batch_processing")
                time.sleep(1)  # 短暂休息后重试
    
    def _process_single_message(self, message):
        """处理单条消息"""
        start_time = time.time()
        
        try:
            # 解析原始数据
            raw_data_dict = message.value
            raw_data = TaxiRawData(**raw_data_dict)
            
            # 特征处理
            features = self.feature_processor.process_raw_data(raw_data)
            
            # 发送处理后的特征
            self._send_processed_features(features)
            
            # 记录指标
            processing_time = time.time() - start_time
            self.metrics.record_message_processed(message.topic)
            self.metrics.record_processing_time("feature_processing", processing_time)
            self.metrics.record_feature_generated("processed_features")
            
            self.logger.debug(f"消息处理完成: {raw_data.trip_id}, 耗时: {processing_time:.3f}s")
            
        except Exception as e:
            self.logger.error(f"单条消息处理失败: {e}")
            self.metrics.record_error("single_message_processing")
            raise
    
    def _send_processed_features(self, features: ProcessedFeatures):
        """发送处理后的特征"""
        try:
            features_dict = asdict(features)
            
            # 发送到特征主题
            self.producer.send('taxi-features', value=features_dict)
            
            # 发送实时特征到实时主题
            realtime_features = {
                'trip_id': features.trip_id,
                'event_timestamp': features.event_timestamp,
                'current_demand': features.current_demand,
                'traffic_level': features.traffic_level,
                'weather_condition': features.weather_condition,
                'surge_multiplier': features.surge_multiplier,
                'processing_timestamp': features.processing_timestamp
            }
            
            self.producer.send('taxi-features-realtime', value=realtime_features)
            
            # 确保消息发送
            self.producer.flush()
            
        except Exception as e:
            self.logger.error(f"特征发送失败: {e}")
            self.metrics.record_error("feature_sending")
            raise


def main():
    """主函数"""
    # 配置
    config = {
        'kafka_servers': ['localhost:9092'],
        'consumer_group': 'realtime-processor-group',
        'input_topics': ['taxi-raw-data'],
        'max_workers': 4,
        'metrics_port': 8080,
        'redis_host': 'localhost',
        'redis_port': 6379,
        'redis_db': 0
    }
    
    # 创建并启动流处理器
    processor = RealtimeStreamProcessor(config)
    
    try:
        processor.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    finally:
        processor.stop()


if __name__ == "__main__":
    main()
