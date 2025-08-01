#!/usr/bin/env python3
"""
Kafka Kraft 流处理组件
实现实时数据流处理和特征流式更新
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
import asyncio
import threading

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaxiKafkaProcessor:
    """出租车数据 Kafka 流处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Kafka 处理器
        
        Args:
            config: Kafka 配置
        """
        self.config = config
        self.bootstrap_servers = config.get('bootstrap_servers', ['localhost:9092'])
        self.group_id = config.get('group_id', 'taxi-mlops-group')
        
        # Topic 配置
        self.raw_data_topic = config.get('raw_data_topic', 'taxi-raw-data')
        self.features_topic = config.get('features_topic', 'taxi-features')
        self.predictions_topic = config.get('predictions_topic', 'taxi-predictions')
        self.monitoring_topic = config.get('monitoring_topic', 'taxi-monitoring')
        
        # 初始化 Kafka 客户端
        self.producer = None
        self.consumer = None
        self.admin_client = None
        
        # 处理状态
        self.is_running = False
        self.processing_thread = None
    
    def initialize(self):
        """初始化 Kafka 连接和 Topics"""
        try:
            # 创建管理客户端
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id='taxi-mlops-admin'
            )
            
            # 创建 Topics
            self._create_topics()
            
            # 创建生产者
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                acks='all',
                retries=3
            )
            
            # 创建消费者
            self.consumer = KafkaConsumer(
                self.raw_data_topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            
            logger.info("✅ Kafka 客户端初始化成功")
            
        except Exception as e:
            logger.error(f"❌ Kafka 初始化失败: {e}")
            raise
    
    def _create_topics(self):
        """创建必要的 Kafka Topics"""
        topics = [
            NewTopic(
                name=self.raw_data_topic,
                num_partitions=3,
                replication_factor=1,
                topic_configs={'retention.ms': '604800000'}  # 7天
            ),
            NewTopic(
                name=self.features_topic,
                num_partitions=3,
                replication_factor=1,
                topic_configs={'retention.ms': '259200000'}  # 3天
            ),
            NewTopic(
                name=self.predictions_topic,
                num_partitions=3,
                replication_factor=1,
                topic_configs={'retention.ms': '86400000'}   # 1天
            ),
            NewTopic(
                name=self.monitoring_topic,
                num_partitions=1,
                replication_factor=1,
                topic_configs={'retention.ms': '2592000000'}  # 30天
            )
        ]
        
        try:
            # 获取现有 topics
            existing_topics = self.admin_client.list_topics().topics
            
            # 创建不存在的 topics
            new_topics = [topic for topic in topics if topic.name not in existing_topics]
            
            if new_topics:
                result = self.admin_client.create_topics(new_topics)
                for topic_name, future in result.topic_futures.items():
                    try:
                        future.result()
                        logger.info(f"✅ Topic 创建成功: {topic_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Topic 创建失败 {topic_name}: {e}")
            else:
                logger.info("📋 所有 Topics 已存在")
                
        except Exception as e:
            logger.error(f"❌ Topics 创建失败: {e}")
            raise
    
    def start_processing(self):
        """启动流处理"""
        if self.is_running:
            logger.warning("流处理已在运行中")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_stream)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        logger.info("🚀 Kafka 流处理已启动")
    
    def stop_processing(self):
        """停止流处理"""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=10)
        
        logger.info("🛑 Kafka 流处理已停止")
    
    def _process_stream(self):
        """处理数据流"""
        logger.info("📊 开始处理数据流...")
        
        try:
            for message in self.consumer:
                if not self.is_running:
                    break
                
                try:
                    # 处理原始数据
                    raw_data = message.value
                    timestamp = datetime.now()
                    
                    logger.debug(f"收到原始数据: {raw_data}")
                    
                    # 特征提取
                    features = self._extract_features(raw_data, timestamp)
                    
                    # 发送特征到特征 Topic
                    self._send_features(features, message.key)
                    
                    # 模型预测 (如果配置了预测服务)
                    if self.config.get('enable_prediction', False):
                        prediction = self._make_prediction(features)
                        self._send_prediction(prediction, message.key)
                    
                    # 发送监控指标
                    monitoring_data = self._generate_monitoring_data(
                        raw_data, features, timestamp
                    )
                    self._send_monitoring_data(monitoring_data)
                    
                except Exception as e:
                    logger.error(f"❌ 消息处理失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ 流处理异常: {e}")
        finally:
            logger.info("📊 流处理结束")
    
    def _extract_features(self, raw_data: Dict[str, Any], timestamp: datetime) -> Dict[str, Any]:
        """从原始数据提取特征"""
        try:
            # 基于 tfx_pipeline 中的特征定义
            features = {
                'trip_id': raw_data.get('trip_id'),
                'trip_start_hour': timestamp.hour,
                'trip_start_day': timestamp.weekday(),
                'trip_start_month': timestamp.month,
                'trip_miles': float(raw_data.get('trip_miles', 0)),
                'fare': float(raw_data.get('fare', 0)),
                'trip_seconds': int(raw_data.get('trip_seconds', 0)),
                'pickup_latitude': float(raw_data.get('pickup_latitude', 0)),
                'pickup_longitude': float(raw_data.get('pickup_longitude', 0)),
                'dropoff_latitude': float(raw_data.get('dropoff_latitude', 0)),
                'dropoff_longitude': float(raw_data.get('dropoff_longitude', 0)),
                'pickup_census_tract': raw_data.get('pickup_census_tract', 0),
                'dropoff_census_tract': raw_data.get('dropoff_census_tract', 0),
                'pickup_community_area': raw_data.get('pickup_community_area', 0),
                'dropoff_community_area': raw_data.get('dropoff_community_area', 0),
                'company': raw_data.get('company', ''),
                'payment_type': raw_data.get('payment_type', ''),
                'event_timestamp': timestamp.isoformat(),
                'processed_at': datetime.now().isoformat()
            }
            
            # 计算衍生特征
            features['trip_speed'] = (
                features['trip_miles'] / (features['trip_seconds'] / 3600) 
                if features['trip_seconds'] > 0 else 0
            )
            
            features['fare_per_mile'] = (
                features['fare'] / features['trip_miles'] 
                if features['trip_miles'] > 0 else 0
            )
            
            return features
            
        except Exception as e:
            logger.error(f"❌ 特征提取失败: {e}")
            return {}
    
    def _send_features(self, features: Dict[str, Any], key: str):
        """发送特征到 Kafka"""
        try:
            self.producer.send(
                self.features_topic,
                key=key,
                value=features
            )
            logger.debug(f"✅ 特征已发送: {key}")
            
        except Exception as e:
            logger.error(f"❌ 特征发送失败: {e}")
    
    def _make_prediction(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """调用模型进行预测"""
        try:
            # 这里应该调用 KFServing 推理服务
            # 简化版本，返回模拟预测
            import random
            
            prediction = {
                'trip_id': features.get('trip_id'),
                'predicted_tips': random.choice([0, 1]),
                'prediction_score': random.uniform(0, 1),
                'model_version': 'v1.0',
                'prediction_timestamp': datetime.now().isoformat()
            }
            
            return prediction
            
        except Exception as e:
            logger.error(f"❌ 预测失败: {e}")
            return {}
    
    def _send_prediction(self, prediction: Dict[str, Any], key: str):
        """发送预测结果到 Kafka"""
        try:
            self.producer.send(
                self.predictions_topic,
                key=key,
                value=prediction
            )
            logger.debug(f"✅ 预测已发送: {key}")
            
        except Exception as e:
            logger.error(f"❌ 预测发送失败: {e}")
    
    def _generate_monitoring_data(self, raw_data: Dict[str, Any], 
                                features: Dict[str, Any], 
                                timestamp: datetime) -> Dict[str, Any]:
        """生成监控数据"""
        return {
            'timestamp': timestamp.isoformat(),
            'message_count': 1,
            'processing_latency_ms': 50,  # 模拟处理延迟
            'feature_count': len(features),
            'data_quality_score': 0.95,  # 模拟数据质量分数
            'pipeline_stage': 'feature_extraction',
            'status': 'success'
        }
    
    def _send_monitoring_data(self, monitoring_data: Dict[str, Any]):
        """发送监控数据"""
        try:
            self.producer.send(
                self.monitoring_topic,
                value=monitoring_data
            )
            
        except Exception as e:
            logger.error(f"❌ 监控数据发送失败: {e}")
    
    def send_raw_data(self, data: Dict[str, Any], key: Optional[str] = None):
        """发送原始数据到 Kafka (用于测试)"""
        try:
            self.producer.send(
                self.raw_data_topic,
                key=key or str(data.get('trip_id', 'unknown')),
                value=data
            )
            self.producer.flush()
            logger.info(f"✅ 原始数据已发送: {key}")
            
        except Exception as e:
            logger.error(f"❌ 原始数据发送失败: {e}")
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        try:
            # 这里应该从监控 Topic 读取统计信息
            # 简化版本，返回模拟统计
            return {
                'total_messages_processed': 1000,
                'average_processing_latency_ms': 45,
                'error_rate': 0.02,
                'throughput_per_second': 50,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 获取监控统计失败: {e}")
            return {}
    
    def close(self):
        """关闭 Kafka 连接"""
        try:
            self.stop_processing()
            
            if self.producer:
                self.producer.close()
            
            if self.consumer:
                self.consumer.close()
            
            if self.admin_client:
                self.admin_client.close()
            
            logger.info("✅ Kafka 连接已关闭")
            
        except Exception as e:
            logger.error(f"❌ 关闭 Kafka 连接失败: {e}")

# 使用示例
if __name__ == "__main__":
    # Kafka 配置
    kafka_config = {
        'bootstrap_servers': ['localhost:9092'],
        'group_id': 'taxi-mlops-group',
        'enable_prediction': True
    }
    
    # 创建处理器
    processor = TaxiKafkaProcessor(kafka_config)
    
    try:
        # 初始化
        processor.initialize()
        
        # 启动流处理
        processor.start_processing()
        
        # 发送测试数据
        test_data = {
            'trip_id': 'test_001',
            'trip_miles': 5.2,
            'fare': 15.50,
            'trip_seconds': 1200,
            'pickup_latitude': 41.8781,
            'pickup_longitude': -87.6298,
            'dropoff_latitude': 41.8851,
            'dropoff_longitude': -87.6234,
            'pickup_community_area': 8,
            'dropoff_community_area': 32,
            'company': 'Yellow Cab',
            'payment_type': 'Credit Card'
        }
        
        processor.send_raw_data(test_data)
        
        # 运行一段时间
        import time
        time.sleep(10)
        
        # 获取统计信息
        stats = processor.get_monitoring_stats()
        print(f"📊 监控统计: {stats}")
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    finally:
        processor.close()
