#!/usr/bin/env python3
"""
FastAPI Feast 集成客户端
为 FastAPI 提供 Feast 特征存储访问功能
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
from pydantic import BaseModel

# Feast 相关导入
try:
    from feast import FeatureStore
    from feast.errors import FeatureViewNotFoundException, FeatureServiceNotFoundException
    FEAST_AVAILABLE = True
except ImportError:
    FEAST_AVAILABLE = False
    logging.warning("Feast 未安装，使用模拟模式")

# Redis 导入（备用在线存储）
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class FeatureRequest(BaseModel):
    """特征请求模型"""
    entity_ids: List[str]
    feature_service: str = "model_inference_v1"
    timestamp: Optional[datetime] = None


class FeatureResponse(BaseModel):
    """特征响应模型"""
    features: Dict[str, Any]
    metadata: Dict[str, Any]
    status: str = "success"
    message: str = ""


class FeastClient:
    """Feast 客户端"""
    
    def __init__(self, feast_repo_path: str = "feast_repo"):
        """
        初始化 Feast 客户端
        
        Args:
            feast_repo_path: Feast 仓库路径
        """
        self.feast_repo_path = Path(feast_repo_path)
        self.logger = logging.getLogger(__name__)
        
        # 初始化存储
        self.store = None
        self.redis_client = None
        
        self._initialize_stores()
    
    def _initialize_stores(self):
        """初始化存储连接"""
        
        if FEAST_AVAILABLE:
            try:
                self.store = FeatureStore(repo_path=str(self.feast_repo_path))
                self.logger.info("Feast 存储初始化成功")
            except Exception as e:
                self.logger.error(f"Feast 存储初始化失败: {e}")
                self.store = None
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host='localhost', port=6379, db=0, decode_responses=True
                )
                self.redis_client.ping()
                self.logger.info("Redis 连接成功")
            except Exception as e:
                self.logger.warning(f"Redis 连接失败: {e}")
                self.redis_client = None
    
    async def get_online_features(self, request: FeatureRequest) -> FeatureResponse:
        """
        获取在线特征
        
        Args:
            request: 特征请求
            
        Returns:
            特征响应
        """
        try:
            if self.store:
                return await self._get_online_features_feast(request)
            elif self.redis_client:
                return await self._get_online_features_redis(request)
            else:
                return await self._get_online_features_mock(request)
                
        except Exception as e:
            self.logger.error(f"获取在线特征失败: {e}")
            return FeatureResponse(
                features={},
                metadata={"error": str(e)},
                status="error",
                message=f"获取在线特征失败: {e}"
            )
    
    async def _get_online_features_feast(self, request: FeatureRequest) -> FeatureResponse:
        """使用 Feast 获取在线特征"""
        
        try:
            # 准备实体数据
            entity_rows = []
            for entity_id in request.entity_ids:
                entity_rows.append({"trip_id": entity_id})
            
            # 获取特征服务
            try:
                feature_service = self.store.get_feature_service(request.feature_service)
                feature_refs = [f.name for f in feature_service.features]
            except FeatureServiceNotFoundException:
                # 如果服务不存在，使用默认特征
                feature_refs = [
                    "trip_features:trip_miles",
                    "trip_features:trip_seconds",
                    "trip_features:fare",
                    "trip_features:pickup_latitude",
                    "trip_features:pickup_longitude",
                    "trip_features:pickup_hour",
                    "trip_features:passenger_count"
                ]
            
            # 获取在线特征
            online_features = self.store.get_online_features(
                features=feature_refs,
                entity_rows=entity_rows
            )
            
            # 转换为字典格式
            features_dict = online_features.to_dict()
            
            return FeatureResponse(
                features=features_dict,
                metadata={
                    "source": "feast",
                    "feature_service": request.feature_service,
                    "entity_count": len(request.entity_ids),
                    "feature_count": len(feature_refs)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Feast 在线特征获取失败: {e}")
            # 降级到 Redis 或模拟模式
            if self.redis_client:
                return await self._get_online_features_redis(request)
            else:
                return await self._get_online_features_mock(request)
    
    async def _get_online_features_redis(self, request: FeatureRequest) -> FeatureResponse:
        """使用 Redis 获取在线特征"""
        
        features_dict = {}
        
        for entity_id in request.entity_ids:
            feature_key = f"feast:trip_features:{entity_id}"
            
            try:
                # 从 Redis 获取特征
                feature_data = self.redis_client.hgetall(feature_key)
                
                if feature_data:
                    # 转换数据类型
                    processed_features = {}
                    for key, value in feature_data.items():
                        try:
                            # 尝试转换为数值
                            if '.' in value:
                                processed_features[key] = float(value)
                            else:
                                processed_features[key] = int(value)
                        except ValueError:
                            processed_features[key] = value
                    
                    features_dict[entity_id] = processed_features
                else:
                    # 如果 Redis 中没有数据，生成模拟数据
                    features_dict[entity_id] = self._generate_mock_features(entity_id)
                    
            except Exception as e:
                self.logger.warning(f"Redis 获取特征失败 {entity_id}: {e}")
                features_dict[entity_id] = self._generate_mock_features(entity_id)
        
        return FeatureResponse(
            features=features_dict,
            metadata={
                "source": "redis",
                "feature_service": request.feature_service,
                "entity_count": len(request.entity_ids)
            }
        )
    
    async def _get_online_features_mock(self, request: FeatureRequest) -> FeatureResponse:
        """生成模拟在线特征"""
        
        features_dict = {}
        
        for entity_id in request.entity_ids:
            features_dict[entity_id] = self._generate_mock_features(entity_id)
        
        return FeatureResponse(
            features=features_dict,
            metadata={
                "source": "mock",
                "feature_service": request.feature_service,
                "entity_count": len(request.entity_ids),
                "warning": "使用模拟数据，请检查 Feast 和 Redis 连接"
            }
        )
    
    def _generate_mock_features(self, entity_id: str) -> Dict[str, Any]:
        """生成模拟特征数据"""
        
        # 基于 entity_id 生成一致的随机数
        np.random.seed(hash(entity_id) % 2**32)
        
        return {
            "trip_miles": round(np.random.exponential(3.0), 2),
            "trip_seconds": int(np.random.exponential(900)),
            "fare": round(np.random.exponential(12.0), 2),
            "pickup_latitude": round(np.random.normal(41.88, 0.05), 6),
            "pickup_longitude": round(np.random.normal(-87.63, 0.05), 6),
            "dropoff_latitude": round(np.random.normal(41.89, 0.05), 6),
            "dropoff_longitude": round(np.random.normal(-87.62, 0.05), 6),
            "pickup_hour": np.random.randint(0, 24),
            "pickup_day_of_week": np.random.randint(0, 7),
            "pickup_month": np.random.randint(1, 13),
            "passenger_count": np.random.randint(1, 5),
            "payment_type": np.random.choice(["Credit Card", "Cash", "No Charge"]),
            "company": np.random.choice(["Flash Cab", "Yellow Cab", "Blue Diamond"])
        }
    
    async def get_historical_features(self, 
                                    entity_df: pd.DataFrame,
                                    features: List[str],
                                    full_feature_names: bool = True) -> pd.DataFrame:
        """
        获取历史特征
        
        Args:
            entity_df: 实体 DataFrame
            features: 特征列表
            full_feature_names: 是否使用完整特征名
            
        Returns:
            包含特征的 DataFrame
        """
        try:
            if self.store:
                return await self._get_historical_features_feast(entity_df, features, full_feature_names)
            else:
                return await self._get_historical_features_mock(entity_df, features)
                
        except Exception as e:
            self.logger.error(f"获取历史特征失败: {e}")
            return await self._get_historical_features_mock(entity_df, features)
    
    async def _get_historical_features_feast(self, 
                                           entity_df: pd.DataFrame,
                                           features: List[str],
                                           full_feature_names: bool) -> pd.DataFrame:
        """使用 Feast 获取历史特征"""
        
        try:
            # 获取历史特征
            historical_features = self.store.get_historical_features(
                entity_df=entity_df,
                features=features,
                full_feature_names=full_feature_names
            )
            
            return historical_features.to_df()
            
        except Exception as e:
            self.logger.error(f"Feast 历史特征获取失败: {e}")
            return await self._get_historical_features_mock(entity_df, features)
    
    async def _get_historical_features_mock(self, 
                                          entity_df: pd.DataFrame,
                                          features: List[str]) -> pd.DataFrame:
        """生成模拟历史特征"""
        
        result_df = entity_df.copy()
        
        # 为每个特征生成模拟数据
        for feature in features:
            feature_name = feature.split(':')[-1] if ':' in feature else feature
            
            if feature_name in ['trip_miles', 'fare']:
                result_df[feature_name] = np.random.exponential(3.0 if 'miles' in feature_name else 12.0, len(result_df))
            elif feature_name in ['trip_seconds']:
                result_df[feature_name] = np.random.exponential(900, len(result_df)).astype(int)
            elif 'latitude' in feature_name:
                result_df[feature_name] = np.random.normal(41.88, 0.05, len(result_df))
            elif 'longitude' in feature_name:
                result_df[feature_name] = np.random.normal(-87.63, 0.05, len(result_df))
            elif 'hour' in feature_name:
                result_df[feature_name] = np.random.randint(0, 24, len(result_df))
            elif 'passenger' in feature_name:
                result_df[feature_name] = np.random.randint(1, 5, len(result_df))
            else:
                result_df[feature_name] = np.random.normal(0, 1, len(result_df))
        
        return result_df
    
    async def list_feature_views(self) -> List[Dict[str, Any]]:
        """列出所有特征视图"""
        
        try:
            if self.store:
                feature_views = self.store.list_feature_views()
                return [
                    {
                        "name": fv.name,
                        "entities": [e.name for e in fv.entities],
                        "features": [f.name for f in fv.features],
                        "ttl_seconds": fv.ttl.total_seconds() if fv.ttl else None,
                        "tags": fv.tags
                    }
                    for fv in feature_views
                ]
            else:
                # 返回模拟的特征视图
                return [
                    {
                        "name": "trip_features",
                        "entities": ["trip_id"],
                        "features": ["trip_miles", "trip_seconds", "fare", "pickup_latitude", 
                                   "pickup_longitude", "pickup_hour", "passenger_count"],
                        "ttl_seconds": 604800,  # 7 days
                        "tags": {"team": "mlops", "type": "batch"}
                    },
                    {
                        "name": "area_features", 
                        "entities": ["area_id"],
                        "features": ["avg_trip_distance", "avg_trip_duration", "avg_fare"],
                        "ttl_seconds": 2592000,  # 30 days
                        "tags": {"team": "mlops", "type": "aggregated"}
                    }
                ]
                
        except Exception as e:
            self.logger.error(f"列出特征视图失败: {e}")
            return []
    
    async def list_feature_services(self) -> List[Dict[str, Any]]:
        """列出所有特征服务"""
        
        try:
            if self.store:
                feature_services = self.store.list_feature_services()
                return [
                    {
                        "name": fs.name,
                        "features": [f.name for f in fs.features],
                        "tags": fs.tags
                    }
                    for fs in feature_services
                ]
            else:
                # 返回模拟的特征服务
                return [
                    {
                        "name": "model_inference_v1",
                        "features": ["trip_features", "area_features"],
                        "tags": {"service": "inference", "version": "v1"}
                    },
                    {
                        "name": "realtime_inference_v1",
                        "features": ["trip_features", "trip_realtime_features"],
                        "tags": {"service": "realtime", "version": "v1"}
                    }
                ]
                
        except Exception as e:
            self.logger.error(f"列出特征服务失败: {e}")
            return []
    
    async def get_feature_store_info(self) -> Dict[str, Any]:
        """获取特征存储信息"""
        
        info = {
            "feast_available": FEAST_AVAILABLE,
            "redis_available": REDIS_AVAILABLE,
            "store_connected": self.store is not None,
            "redis_connected": self.redis_client is not None,
            "repo_path": str(self.feast_repo_path)
        }
        
        # 如果 Feast 不可用，提供模拟数据
        if not FEAST_AVAILABLE or self.store is None:
            info.update({
                "feature_views_count": 2,
                "feature_services_count": 2,
                "status": "mock_mode",
                "message": "使用模拟模式 - Feast 或 Redis 服务未运行"
            })
        else:
            try:
                info["feature_views_count"] = len(self.store.list_feature_views())
                info["feature_services_count"] = len(self.store.list_feature_services())
                info["status"] = "connected"
            except Exception as e:
                info["error"] = str(e)
                info["status"] = "error"
                # 提供降级的模拟数据
                info.update({
                    "feature_views_count": 2,
                    "feature_services_count": 2
                })
        
        return info
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        
        health = {
            "status": "healthy",
            "checks": {}
        }
        
        # 检查 Feast 存储
        if self.store:
            try:
                self.store.list_feature_views()
                health["checks"]["feast_store"] = "ok"
            except Exception as e:
                health["checks"]["feast_store"] = f"error: {e}"
                health["status"] = "degraded"
        else:
            health["checks"]["feast_store"] = "not_available"
            health["status"] = "degraded"
        
        # 检查 Redis
        if self.redis_client:
            try:
                self.redis_client.ping()
                health["checks"]["redis"] = "ok"
            except Exception as e:
                health["checks"]["redis"] = f"error: {e}"
                health["status"] = "degraded"
        else:
            health["checks"]["redis"] = "not_available"
        
        return health


# 全局 Feast 客户端实例
feast_client = FeastClient()
