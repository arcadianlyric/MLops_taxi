#!/usr/bin/env python3
"""
Kafka Kraft 流处理器实现
Chicago Taxi 实时数据流处理和应用
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import requests


@dataclass
class TaxiRide:
    """出租车行程数据结构"""
    trip_id: str
    pickup_datetime: str
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    passenger_count: int
    trip_distance: float
    fare_amount: float
    payment_type: str
    company: str


@dataclass
class TaxiFeatures:
    """实时特征数据结构"""
    trip_id: str
    timestamp: str
    pickup_hour: int
    pickup_day_of_week: int
    pickup_community_area: int
    trip_duration_seconds: int
    trip_distance_miles: float
    avg_speed_mph: float
    weather_condition: str
    demand_level: str


@dataclass
class TaxiPrediction:
    """预测结果数据结构"""
    trip_id: str
    timestamp: str
    predicted_fare: float
    predicted_tip: float
    confidence_score: float
    model_version: str


@dataclass
class ModelMetric:
    """模型指标数据结构"""
    model_name: str
    timestamp: str
    metric_name: str
    metric_value: float
    threshold: float


class KafkaStreamProcessor:
    """Kafka 流处理器"""
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        """
        初始化 Kafka 流处理器
        
        Args:
            bootstrap_servers: Kafka 服务器地址
        """
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumers = {}
        self.logger = self._setup_logging()
        
        # 配置
        self.topics = {
            'raw_rides': 'taxi-rides-raw',
            'features': 'taxi-features-realtime',
            'predictions': 'taxi-predictions',
            'metrics': 'model-metrics',
            'alerts': 'data-quality-alerts'
        }
        
        # FastAPI 服务地址
        self.api_base_url = 'http://localhost:8000'
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _get_producer(self) -> KafkaProducer:
        """获取 Kafka Producer"""
        if not self.producer:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
        return self.producer
    
    def _get_consumer(self, topic: str, group_id: str) -> KafkaConsumer:
        """获取 Kafka Consumer"""
        consumer_key = f"{topic}_{group_id}"
        if consumer_key not in self.consumers:
            self.consumers[consumer_key] = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
        return self.consumers[consumer_key]
    
    def publish_ride_data(self, ride: TaxiRide) -> bool:
        """发布原始行程数据到 Kafka"""
        try:
            producer = self._get_producer()
            producer.send(
                self.topics['raw_rides'],
                key=ride.trip_id,
                value=asdict(ride)
            )
            producer.flush()
            self.logger.info(f"发布行程数据: {ride.trip_id}")
            return True
        except Exception as e:
            self.logger.error(f"发布行程数据失败: {e}")
            return False
    
    def process_feature_engineering(self):
        """实时特征工程处理器"""
        consumer = self._get_consumer(self.topics['raw_rides'], 'feature-engineering-group')
        producer = self._get_producer()
        
        self.logger.info("启动特征工程处理器...")
        
        for message in consumer:
            try:
                ride_data = message.value
                ride = TaxiRide(**ride_data)
                
                # 计算实时特征
                features = self._calculate_features(ride)
                
                # 发布特征数据
                producer.send(
                    self.topics['features'],
                    key=features.trip_id,
                    value=asdict(features)
                )
                
                self.logger.info(f"处理特征: {features.trip_id}")
                
            except Exception as e:
                self.logger.error(f"特征工程处理失败: {e}")
    
    def _calculate_features(self, ride: TaxiRide) -> TaxiFeatures:
        """计算实时特征"""
        pickup_time = datetime.fromisoformat(ride.pickup_datetime.replace('Z', '+00:00'))
        
        # 计算行程时长（模拟）
        trip_duration = max(int(ride.trip_distance * 180), 60)  # 基于距离估算时长
        
        # 计算平均速度
        avg_speed = (ride.trip_distance / (trip_duration / 3600)) if trip_duration > 0 else 0
        
        # 社区区域映射（简化）
        pickup_community_area = self._get_community_area(ride.pickup_latitude, ride.pickup_longitude)
        
        # 需求水平（基于时间和位置）
        demand_level = self._calculate_demand_level(pickup_time, pickup_community_area)
        
        return TaxiFeatures(
            trip_id=ride.trip_id,
            timestamp=datetime.now().isoformat(),
            pickup_hour=pickup_time.hour,
            pickup_day_of_week=pickup_time.weekday(),
            pickup_community_area=pickup_community_area,
            trip_duration_seconds=trip_duration,
            trip_distance_miles=ride.trip_distance,
            avg_speed_mph=avg_speed,
            weather_condition="Clear",  # 简化，实际应从天气API获取
            demand_level=demand_level
        )
    
    def _get_community_area(self, lat: float, lon: float) -> int:
        """根据经纬度获取社区区域ID（简化实现）"""
        # 芝加哥市中心区域映射
        if 41.85 <= lat <= 41.95 and -87.7 <= lon <= -87.6:
            return 32  # Loop
        elif 41.88 <= lat <= 41.92 and -87.65 <= lon <= -87.62:
            return 8   # Near North Side
        else:
            return 1   # 默认区域
    
    def _calculate_demand_level(self, pickup_time: datetime, area: int) -> str:
        """计算需求水平"""
        hour = pickup_time.hour
        
        # 高峰时段
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            return "High"
        elif 22 <= hour <= 23 or 6 <= hour <= 7:
            return "Medium"
        else:
            return "Low"
    
    def process_model_inference(self):
        """模型推理处理器"""
        consumer = self._get_consumer(self.topics['features'], 'model-inference-group')
        producer = self._get_producer()
        
        self.logger.info("启动模型推理处理器...")
        
        for message in consumer:
            try:
                feature_data = message.value
                features = TaxiFeatures(**feature_data)
                
                # 调用模型推理服务
                prediction = self._call_model_inference(features)
                
                if prediction:
                    # 发布预测结果
                    producer.send(
                        self.topics['predictions'],
                        key=prediction.trip_id,
                        value=asdict(prediction)
                    )
                    
                    self.logger.info(f"生成预测: {prediction.trip_id}")
                
            except Exception as e:
                self.logger.error(f"模型推理处理失败: {e}")
    
    def _call_model_inference(self, features: TaxiFeatures) -> Optional[TaxiPrediction]:
        """调用模型推理服务"""
        try:
            # 构造推理请求
            inference_data = {
                "trip_miles": features.trip_distance_miles,
                "trip_seconds": features.trip_duration_seconds,
                "pickup_latitude": 41.88,  # 简化
                "pickup_longitude": -87.63,
                "dropoff_latitude": 41.89,
                "dropoff_longitude": -87.62,
                "fare": 10.0,  # 简化
                "trip_start_hour": features.pickup_hour,
                "trip_start_day": features.pickup_day_of_week,
                "trip_start_month": datetime.now().month,
                "pickup_community_area": features.pickup_community_area,
                "dropoff_community_area": features.pickup_community_area + 1,
                "payment_type": "Credit Card",
                "company": "Flash Cab"
            }
            
            # 调用 FastAPI 预测端点
            response = requests.post(
                f"{self.api_base_url}/predict",
                json=inference_data,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                
                return TaxiPrediction(
                    trip_id=features.trip_id,
                    timestamp=datetime.now().isoformat(),
                    predicted_fare=result.get('predicted_fare', 0.0),
                    predicted_tip=result.get('predicted_tip', 0.0),
                    confidence_score=result.get('confidence', 0.8),
                    model_version="v1.0"
                )
            
        except Exception as e:
            self.logger.error(f"模型推理调用失败: {e}")
        
        return None
    
    def process_metrics_calculation(self):
        """指标计算处理器"""
        consumer = self._get_consumer(self.topics['predictions'], 'metrics-calculation-group')
        producer = self._get_producer()
        
        self.logger.info("启动指标计算处理器...")
        
        prediction_buffer = []
        last_metrics_time = datetime.now()
        
        for message in consumer:
            try:
                prediction_data = message.value
                prediction = TaxiPrediction(**prediction_data)
                
                prediction_buffer.append(prediction)
                
                # 每分钟计算一次指标
                if datetime.now() - last_metrics_time > timedelta(minutes=1):
                    metrics = self._calculate_metrics(prediction_buffer)
                    
                    for metric in metrics:
                        producer.send(
                            self.topics['metrics'],
                            key=f"{metric.model_name}_{metric.metric_name}",
                            value=asdict(metric)
                        )
                    
                    # 推送到 Prometheus（如果可用）
                    self._push_to_prometheus(metrics)
                    
                    prediction_buffer.clear()
                    last_metrics_time = datetime.now()
                    
                    self.logger.info(f"计算并发布 {len(metrics)} 个指标")
                
            except Exception as e:
                self.logger.error(f"指标计算处理失败: {e}")
    
    def _calculate_metrics(self, predictions: List[TaxiPrediction]) -> List[ModelMetric]:
        """计算模型指标"""
        if not predictions:
            return []
        
        metrics = []
        timestamp = datetime.now().isoformat()
        
        # 预测数量
        metrics.append(ModelMetric(
            model_name="chicago_taxi_model",
            timestamp=timestamp,
            metric_name="predictions_per_minute",
            metric_value=len(predictions),
            threshold=100.0
        ))
        
        # 平均置信度
        avg_confidence = np.mean([p.confidence_score for p in predictions])
        metrics.append(ModelMetric(
            model_name="chicago_taxi_model",
            timestamp=timestamp,
            metric_name="average_confidence",
            metric_value=avg_confidence,
            threshold=0.7
        ))
        
        # 平均预测费用
        avg_fare = np.mean([p.predicted_fare for p in predictions])
        metrics.append(ModelMetric(
            model_name="chicago_taxi_model",
            timestamp=timestamp,
            metric_name="average_predicted_fare",
            metric_value=avg_fare,
            threshold=15.0
        ))
        
        return metrics
    
    def _push_to_prometheus(self, metrics: List[ModelMetric]):
        """推送指标到 Prometheus（如果可用）"""
        try:
            # 这里可以集成 Prometheus Python 客户端
            # 或者通过 HTTP API 推送指标
            pass
        except Exception as e:
            self.logger.error(f"推送 Prometheus 指标失败: {e}")
    
    def consume_predictions_for_ui(self, callback):
        """为 UI 消费预测结果"""
        consumer = self._get_consumer(self.topics['predictions'], 'ui-consumer-group')
        
        self.logger.info("启动 UI 预测结果消费者...")
        
        for message in consumer:
            try:
                prediction_data = message.value
                prediction = TaxiPrediction(**prediction_data)
                
                # 调用回调函数处理预测结果
                callback(prediction)
                
            except Exception as e:
                self.logger.error(f"UI 预测结果消费失败: {e}")
    
    def simulate_taxi_rides(self, num_rides: int = 10):
        """模拟生成出租车行程数据"""
        self.logger.info(f"开始模拟 {num_rides} 个出租车行程...")
        
        for i in range(num_rides):
            ride = TaxiRide(
                trip_id=f"trip_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                pickup_datetime=datetime.now().isoformat(),
                pickup_latitude=41.88 + np.random.normal(0, 0.01),
                pickup_longitude=-87.63 + np.random.normal(0, 0.01),
                dropoff_latitude=41.89 + np.random.normal(0, 0.01),
                dropoff_longitude=-87.62 + np.random.normal(0, 0.01),
                passenger_count=np.random.randint(1, 5),
                trip_distance=np.random.exponential(3.0),
                fare_amount=np.random.exponential(12.0),
                payment_type=np.random.choice(['Credit Card', 'Cash', 'No Charge']),
                company=np.random.choice(['Flash Cab', 'Taxi Affiliation Services', 'Yellow Cab'])
            )
            
            self.publish_ride_data(ride)
            
        self.logger.info(f"模拟数据发布完成")
    
    def start_all_processors(self):
        """启动所有流处理器"""
        import threading
        
        # 启动特征工程处理器
        feature_thread = threading.Thread(target=self.process_feature_engineering)
        feature_thread.daemon = True
        feature_thread.start()
        
        # 启动模型推理处理器
        inference_thread = threading.Thread(target=self.process_model_inference)
        inference_thread.daemon = True
        inference_thread.start()
        
        # 启动指标计算处理器
        metrics_thread = threading.Thread(target=self.process_metrics_calculation)
        metrics_thread.daemon = True
        metrics_thread.start()
        
        self.logger.info("所有流处理器已启动")
        
        return [feature_thread, inference_thread, metrics_thread]
    
    def close(self):
        """关闭所有连接"""
        if self.producer:
            self.producer.close()
        
        for consumer in self.consumers.values():
            consumer.close()
        
        self.logger.info("Kafka 连接已关闭")


# 使用示例
if __name__ == "__main__":
    processor = KafkaStreamProcessor()
    
    try:
        # 启动所有处理器
        threads = processor.start_all_processors()
        
        # 模拟一些数据
        processor.simulate_taxi_rides(5)
        
        # 保持运行
        for thread in threads:
            thread.join()
            
    except KeyboardInterrupt:
        print("停止流处理器...")
    finally:
        processor.close()
