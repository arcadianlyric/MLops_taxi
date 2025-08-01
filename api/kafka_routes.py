#!/usr/bin/env python3
"""
FastAPI Kafka 流处理集成路由
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
import pandas as pd
import numpy as np

try:
    from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
    from kafka.admin import ConfigResource, ConfigResourceType
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logging.warning("Kafka 未安装，使用模拟模式")

# 创建路由器
router = APIRouter(prefix="/kafka", tags=["Kafka流处理"])

logger = logging.getLogger(__name__)


# Pydantic 模型
class KafkaMessage(BaseModel):
    """Kafka 消息模型"""
    topic: str
    key: Optional[str] = None
    value: Dict[str, Any]
    headers: Optional[Dict[str, str]] = None


class TaxiRawDataMessage(BaseModel):
    """出租车原始数据消息模型"""
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


class StreamProcessingStatus(BaseModel):
    """流处理状态模型"""
    processor_name: str
    status: str
    last_processed: Optional[str]
    messages_processed: int
    processing_rate: float
    error_count: int


class KafkaClient:
    """Kafka 客户端封装"""
    
    def __init__(self, bootstrap_servers: List[str] = None):
        self.bootstrap_servers = bootstrap_servers or ['localhost:9092']
        self.producer = None
        self.admin_client = None
        self.logger = logging.getLogger(f"{__name__}.KafkaClient")
        
        if KAFKA_AVAILABLE:
            self._initialize_clients()
    
    def _initialize_clients(self):
        """初始化 Kafka 客户端"""
        try:
            # 创建生产者
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None,
                acks='all',
                retries=3,
                batch_size=16384,
                linger_ms=10
            )
            
            # 创建管理客户端
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id='fastapi-admin'
            )
            
            self.logger.info("Kafka 客户端初始化成功")
            
        except Exception as e:
            self.logger.error(f"Kafka 客户端初始化失败: {e}")
            self.producer = None
            self.admin_client = None
    
    async def send_message(self, topic: str, value: Dict[str, Any], 
                          key: str = None, headers: Dict[str, str] = None) -> bool:
        """发送消息到 Kafka"""
        if not KAFKA_AVAILABLE or not self.producer:
            self.logger.warning("Kafka 不可用，使用模拟模式")
            return True
        
        try:
            # 准备头部信息
            kafka_headers = []
            if headers:
                kafka_headers = [(k, v.encode('utf-8')) for k, v in headers.items()]
            
            # 发送消息
            future = self.producer.send(
                topic=topic,
                value=value,
                key=key,
                headers=kafka_headers
            )
            
            # 等待发送完成
            record_metadata = future.get(timeout=10)
            
            self.logger.info(f"消息发送成功: {topic}:{record_metadata.partition}:{record_metadata.offset}")
            return True
            
        except Exception as e:
            self.logger.error(f"消息发送失败: {e}")
            return False
    
    async def get_topic_info(self, topic: str) -> Dict[str, Any]:
        """获取主题信息"""
        if not KAFKA_AVAILABLE or not self.admin_client:
            return self._get_mock_topic_info(topic)
        
        try:
            # 获取主题元数据
            metadata = self.admin_client.describe_topics([topic])
            topic_metadata = metadata[topic]
            
            # 获取主题配置
            configs = self.admin_client.describe_configs(
                config_resources=[ConfigResource(ConfigResourceType.TOPIC, topic)]
            )
            topic_config = configs[ConfigResource(ConfigResourceType.TOPIC, topic)]
            
            return {
                "name": topic,
                "partitions": len(topic_metadata.partitions),
                "replication_factor": len(topic_metadata.partitions[0].replicas) if topic_metadata.partitions else 0,
                "config": {k: v.value for k, v in topic_config.configs.items()},
                "status": "active"
            }
            
        except Exception as e:
            self.logger.error(f"获取主题信息失败: {e}")
            return self._get_mock_topic_info(topic)
    
    def _get_mock_topic_info(self, topic: str) -> Dict[str, Any]:
        """获取模拟主题信息"""
        return {
            "name": topic,
            "partitions": 3,
            "replication_factor": 1,
            "config": {
                "cleanup.policy": "delete",
                "retention.ms": "604800000",
                "compression.type": "snappy"
            },
            "status": "mock"
        }
    
    async def get_consumer_group_info(self, group_id: str) -> Dict[str, Any]:
        """获取消费者组信息"""
        if not KAFKA_AVAILABLE:
            return {
                "group_id": group_id,
                "state": "mock",
                "members": 1,
                "lag": 0
            }
        
        # 实际实现需要更复杂的逻辑
        return {
            "group_id": group_id,
            "state": "stable",
            "members": 1,
            "lag": 0
        }


# 全局 Kafka 客户端
kafka_client = KafkaClient()


# Kafka 管理路由
@router.get("/info", summary="获取 Kafka 集群信息")
async def get_kafka_info():
    """获取 Kafka 集群基本信息"""
    try:
        info = {
            "kafka_available": KAFKA_AVAILABLE,
            "bootstrap_servers": kafka_client.bootstrap_servers,
            "client_connected": kafka_client.producer is not None,
            "status": "connected" if KAFKA_AVAILABLE and kafka_client.producer else "disconnected"
        }
        
        return {
            "status": "success",
            "data": info,
            "message": "Kafka 集群信息获取成功"
        }
    except Exception as e:
        logger.error(f"获取 Kafka 信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取 Kafka 信息失败: {str(e)}")


@router.get("/topics", summary="获取所有主题")
async def list_topics():
    """列出所有 Kafka 主题"""
    try:
        # 预定义的主题列表
        topics = [
            "taxi-raw-data",
            "taxi-features", 
            "taxi-features-realtime",
            "taxi-predictions",
            "taxi-model-metrics",
            "taxi-data-quality",
            "taxi-alerts",
            "taxi-business-metrics",
            "taxi-training-data",
            "taxi-system-events"
        ]
        
        topic_info = []
        for topic in topics:
            info = await kafka_client.get_topic_info(topic)
            topic_info.append(info)
        
        return {
            "status": "success",
            "data": topic_info,
            "count": len(topic_info),
            "message": f"成功获取 {len(topic_info)} 个主题信息"
        }
    except Exception as e:
        logger.error(f"获取主题列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取主题列表失败: {str(e)}")


@router.get("/topics/{topic_name}", summary="获取主题详情")
async def get_topic_details(topic_name: str):
    """获取指定主题的详细信息"""
    try:
        topic_info = await kafka_client.get_topic_info(topic_name)
        
        return {
            "status": "success",
            "data": topic_info,
            "message": f"主题 {topic_name} 信息获取成功"
        }
    except Exception as e:
        logger.error(f"获取主题详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取主题详情失败: {str(e)}")


# 消息生产路由
@router.post("/messages/send", summary="发送消息")
async def send_message(message: KafkaMessage):
    """发送消息到指定主题"""
    try:
        # 添加时间戳
        message.value["timestamp"] = datetime.now().isoformat()
        
        success = await kafka_client.send_message(
            topic=message.topic,
            value=message.value,
            key=message.key,
            headers=message.headers
        )
        
        if success:
            return {
                "status": "success",
                "data": {
                    "topic": message.topic,
                    "key": message.key,
                    "timestamp": message.value["timestamp"]
                },
                "message": "消息发送成功"
            }
        else:
            raise HTTPException(status_code=500, detail="消息发送失败")
            
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@router.post("/messages/taxi-data", summary="发送出租车数据")
async def send_taxi_data(taxi_data: TaxiRawDataMessage):
    """发送出租车原始数据到流处理系统"""
    try:
        # 转换为字典
        data_dict = taxi_data.dict()
        data_dict["timestamp"] = datetime.now().isoformat()
        
        success = await kafka_client.send_message(
            topic="taxi-raw-data",
            value=data_dict,
            key=taxi_data.trip_id,
            headers={"source": "api", "data_type": "taxi_trip"}
        )
        
        if success:
            return {
                "status": "success",
                "data": {
                    "trip_id": taxi_data.trip_id,
                    "topic": "taxi-raw-data",
                    "timestamp": data_dict["timestamp"]
                },
                "message": "出租车数据发送成功，将进入流处理管道"
            }
        else:
            raise HTTPException(status_code=500, detail="出租车数据发送失败")
            
    except Exception as e:
        logger.error(f"发送出租车数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送出租车数据失败: {str(e)}")


@router.post("/messages/batch-taxi-data", summary="批量发送出租车数据")
async def send_batch_taxi_data(taxi_data_list: List[TaxiRawDataMessage]):
    """批量发送出租车数据"""
    try:
        results = []
        success_count = 0
        
        for taxi_data in taxi_data_list:
            try:
                data_dict = taxi_data.dict()
                data_dict["timestamp"] = datetime.now().isoformat()
                
                success = await kafka_client.send_message(
                    topic="taxi-raw-data",
                    value=data_dict,
                    key=taxi_data.trip_id,
                    headers={"source": "api", "data_type": "taxi_trip"}
                )
                
                if success:
                    success_count += 1
                    results.append({
                        "trip_id": taxi_data.trip_id,
                        "status": "success"
                    })
                else:
                    results.append({
                        "trip_id": taxi_data.trip_id,
                        "status": "failed",
                        "error": "发送失败"
                    })
                    
            except Exception as e:
                results.append({
                    "trip_id": taxi_data.trip_id,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "status": "success",
            "data": {
                "total": len(taxi_data_list),
                "success": success_count,
                "failed": len(taxi_data_list) - success_count,
                "results": results
            },
            "message": f"批量发送完成，成功 {success_count}/{len(taxi_data_list)} 条"
        }
        
    except Exception as e:
        logger.error(f"批量发送出租车数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量发送失败: {str(e)}")


# 流处理监控路由
@router.get("/stream-processors", summary="获取流处理器状态")
async def get_stream_processors_status():
    """获取所有流处理器的状态"""
    try:
        # 模拟流处理器状态
        processors = [
            {
                "processor_name": "taxi-feature-processor",
                "status": "running",
                "last_processed": datetime.now().isoformat(),
                "messages_processed": np.random.randint(1000, 10000),
                "processing_rate": np.random.uniform(10, 100),
                "error_count": np.random.randint(0, 10),
                "input_topics": ["taxi-raw-data"],
                "output_topics": ["taxi-features", "taxi-features-realtime"]
            },
            {
                "processor_name": "taxi-prediction-processor", 
                "status": "running",
                "last_processed": datetime.now().isoformat(),
                "messages_processed": np.random.randint(500, 5000),
                "processing_rate": np.random.uniform(5, 50),
                "error_count": np.random.randint(0, 5),
                "input_topics": ["taxi-features"],
                "output_topics": ["taxi-predictions", "taxi-model-metrics"]
            },
            {
                "processor_name": "taxi-monitoring-processor",
                "status": "running", 
                "last_processed": datetime.now().isoformat(),
                "messages_processed": np.random.randint(100, 1000),
                "processing_rate": np.random.uniform(1, 20),
                "error_count": np.random.randint(0, 3),
                "input_topics": ["taxi-predictions", "taxi-model-metrics"],
                "output_topics": ["taxi-alerts", "taxi-business-metrics"]
            }
        ]
        
        return {
            "status": "success",
            "data": processors,
            "count": len(processors),
            "message": "流处理器状态获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取流处理器状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取流处理器状态失败: {str(e)}")


@router.get("/consumer-groups", summary="获取消费者组信息")
async def get_consumer_groups():
    """获取所有消费者组信息"""
    try:
        groups = [
            "feature-processor-group",
            "prediction-service-group", 
            "monitoring-group",
            "alert-processor-group",
            "training-data-group"
        ]
        
        group_info = []
        for group in groups:
            info = await kafka_client.get_consumer_group_info(group)
            group_info.append(info)
        
        return {
            "status": "success",
            "data": group_info,
            "count": len(group_info),
            "message": "消费者组信息获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取消费者组信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取消费者组信息失败: {str(e)}")


# 数据生成路由
@router.post("/generate-test-data", summary="生成测试数据")
async def generate_test_data(
    count: int = Query(10, description="生成数据条数", ge=1, le=1000),
    rate: float = Query(1.0, description="发送速率（条/秒）", ge=0.1, le=100.0),
    background_tasks: BackgroundTasks = None
):
    """生成测试用的出租车数据"""
    try:
        def generate_and_send_data():
            """后台任务：生成并发送数据"""
            import time
            import random
            
            companies = [
                "Flash Cab", "Taxi Affiliation Services", "Yellow Cab",
                "Blue Diamond", "Chicago Carriage Cab Corp", "City Service"
            ]
            
            payment_types = ["Credit Card", "Cash", "No Charge", "Dispute"]
            
            for i in range(count):
                try:
                    # 生成随机行程数据
                    now = datetime.now()
                    pickup_time = now - timedelta(minutes=random.randint(0, 60))
                    trip_duration = random.randint(300, 3600)
                    dropoff_time = pickup_time + timedelta(seconds=trip_duration)
                    
                    # 芝加哥市区坐标
                    pickup_lat = random.uniform(41.6, 42.1)
                    pickup_lon = random.uniform(-87.9, -87.5)
                    dropoff_lat = random.uniform(41.6, 42.1)
                    dropoff_lon = random.uniform(-87.9, -87.5)
                    
                    distance = random.exponential(3.0)
                    fare = 2.25 + distance * 1.75 + (trip_duration / 60) * 0.25 + random.normal(0, 1)
                    fare = max(2.25, fare)
                    
                    trip_data = {
                        "trip_id": f"test_trip_{int(time.time() * 1000)}_{i}",
                        "pickup_datetime": pickup_time.isoformat(),
                        "dropoff_datetime": dropoff_time.isoformat(),
                        "pickup_latitude": pickup_lat,
                        "pickup_longitude": pickup_lon,
                        "dropoff_latitude": dropoff_lat,
                        "dropoff_longitude": dropoff_lon,
                        "passenger_count": random.randint(1, 4),
                        "trip_distance": distance,
                        "fare_amount": round(fare, 2),
                        "payment_type": random.choice(payment_types),
                        "company": random.choice(companies),
                        "timestamp": now.isoformat()
                    }
                    
                    # 发送数据
                    asyncio.run(kafka_client.send_message(
                        topic="taxi-raw-data",
                        value=trip_data,
                        key=trip_data["trip_id"],
                        headers={"source": "test_generator", "data_type": "taxi_trip"}
                    ))
                    
                    # 控制发送速率
                    time.sleep(1.0 / rate)
                    
                except Exception as e:
                    logger.error(f"生成测试数据失败: {e}")
        
        # 添加后台任务
        if background_tasks:
            background_tasks.add_task(generate_and_send_data)
        
        return {
            "status": "success",
            "data": {
                "count": count,
                "rate": rate,
                "estimated_duration": count / rate,
                "topic": "taxi-raw-data"
            },
            "message": f"开始生成 {count} 条测试数据，速率: {rate} 条/秒"
        }
        
    except Exception as e:
        logger.error(f"生成测试数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成测试数据失败: {str(e)}")


# 导出路由器
kafka_router = router
__all__ = ["kafka_router"]
