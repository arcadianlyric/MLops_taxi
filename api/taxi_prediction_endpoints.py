#!/usr/bin/env python3
"""
Chicago Taxi 预测和 Feast 特征存储集成端点
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from fastapi import HTTPException
from pydantic import BaseModel

from feast_client import feast_client, FeatureRequest


class TaxiPredictionService:
    """出租车费用预测服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model_version = "v1.0.0"
    
    async def predict_single(self, request, use_feast_features: bool = True) -> Dict[str, Any]:
        """
        单次出租车费用预测
        
        Args:
            request: 预测请求
            use_feast_features: 是否使用 Feast 特征
            
        Returns:
            预测结果
        """
        try:
            # 生成行程ID
            trip_id = f"trip_{uuid.uuid4().hex[:8]}"
            
            # 准备基础特征
            base_features = {
                "trip_miles": request.trip_miles,
                "trip_seconds": request.trip_seconds,
                "pickup_latitude": request.pickup_latitude,
                "pickup_longitude": request.pickup_longitude,
                "dropoff_latitude": request.dropoff_latitude,
                "dropoff_longitude": request.dropoff_longitude,
                "pickup_hour": request.pickup_hour,
                "pickup_day_of_week": request.pickup_day_of_week,
                "pickup_month": request.pickup_month,
                "passenger_count": request.passenger_count,
                "payment_type": request.payment_type,
                "company": request.company
            }
            
            # 如果使用 Feast 特征，获取增强特征
            enhanced_features = base_features.copy()
            feast_features = {}
            
            if use_feast_features:
                try:
                    # 从 Feast 获取在线特征
                    feature_request = FeatureRequest(
                        entity_ids=[trip_id],
                        feature_service="model_inference_v1"
                    )
                    
                    feast_response = await feast_client.get_online_features(feature_request)
                    
                    if feast_response.status == "success" and feast_response.features:
                        feast_features = feast_response.features.get(trip_id, {})
                        enhanced_features.update(feast_features)
                        
                        self.logger.info(f"成功获取 Feast 特征: {len(feast_features)} 个")
                    else:
                        self.logger.warning("Feast 特征获取失败，使用基础特征")
                        
                except Exception as e:
                    self.logger.warning(f"Feast 特征获取异常: {e}")
            
            # 执行费用预测
            predicted_fare, confidence = self._predict_fare(enhanced_features)
            
            return {
                "trip_id": trip_id,
                "predicted_fare": round(predicted_fare, 2),
                "confidence": round(confidence, 3),
                "features_used": {
                    "base_features": base_features,
                    "feast_features": feast_features,
                    "total_features": len(enhanced_features)
                },
                "model_version": self.model_version,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"预测失败: {e}")
            raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")
    
    async def predict_batch(self, requests: List, use_feast_features: bool = True) -> List[Dict[str, Any]]:
        """
        批量出租车费用预测
        
        Args:
            requests: 批量预测请求
            use_feast_features: 是否使用 Feast 特征
            
        Returns:
            批量预测结果
        """
        results = []
        
        for request in requests:
            try:
                result = await self.predict_single(request, use_feast_features)
                results.append(result)
            except Exception as e:
                self.logger.error(f"批量预测中的单个请求失败: {e}")
                # 添加错误结果
                results.append({
                    "trip_id": f"error_{uuid.uuid4().hex[:8]}",
                    "predicted_fare": 0.0,
                    "confidence": 0.0,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        return results
    
    def _predict_fare(self, features: Dict[str, Any]) -> tuple:
        """
        费用预测算法（简化版本）
        
        Args:
            features: 特征字典
            
        Returns:
            (预测费用, 置信度)
        """
        try:
            # 基础费用计算
            base_fare = 2.25  # 起步价
            
            # 距离费用
            trip_miles = features.get("trip_miles", 0)
            distance_fare = trip_miles * 1.75
            
            # 时间费用
            trip_seconds = features.get("trip_seconds", 0)
            time_fare = (trip_seconds / 60) * 0.25  # 每分钟 $0.25
            
            # 时段调整
            pickup_hour = features.get("pickup_hour", 12)
            peak_multiplier = 1.0
            if pickup_hour in [7, 8, 17, 18, 19]:  # 高峰时段
                peak_multiplier = 1.3
            elif pickup_hour >= 22 or pickup_hour <= 5:  # 夜间
                peak_multiplier = 1.2
            
            # 乘客数量调整
            passenger_count = features.get("passenger_count", 1)
            passenger_multiplier = 1.0 + (passenger_count - 1) * 0.1
            
            # 公司调整
            company = features.get("company", "")
            company_multiplier = 1.0
            if "Yellow" in company:
                company_multiplier = 1.05
            elif "Blue" in company:
                company_multiplier = 0.95
            
            # 计算总费用
            total_fare = (base_fare + distance_fare + time_fare) * peak_multiplier * passenger_multiplier * company_multiplier
            
            # 添加随机变化以模拟真实情况
            noise = np.random.normal(0, 0.5)
            total_fare += noise
            
            # 确保费用合理
            total_fare = max(2.25, min(total_fare, 100.0))
            
            # 计算置信度（基于特征完整性）
            feature_completeness = len([v for v in features.values() if v is not None and v != ""]) / len(features)
            base_confidence = 0.7 + (feature_completeness * 0.3)
            
            # 基于距离和时间的置信度调整
            if trip_miles > 0 and trip_seconds > 0:
                speed = trip_miles / (trip_seconds / 3600)  # mph
                if 5 <= speed <= 60:  # 合理速度范围
                    base_confidence += 0.1
                else:
                    base_confidence -= 0.1
            
            confidence = max(0.1, min(base_confidence, 0.99))
            
            return total_fare, confidence
            
        except Exception as e:
            self.logger.error(f"费用预测计算失败: {e}")
            # 返回默认值
            return 10.0, 0.5


class FeastFeatureService:
    """Feast 特征服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def get_feature_views(self) -> List[Dict[str, Any]]:
        """获取所有特征视图"""
        try:
            return await feast_client.list_feature_views()
        except Exception as e:
            self.logger.error(f"获取特征视图失败: {e}")
            return []
    
    async def get_feature_services(self) -> List[Dict[str, Any]]:
        """获取所有特征服务"""
        try:
            return await feast_client.list_feature_services()
        except Exception as e:
            self.logger.error(f"获取特征服务失败: {e}")
            return []
    
    async def get_online_features(self, entity_ids: List[str], 
                                 feature_service: str = "model_inference_v1") -> Dict[str, Any]:
        """获取在线特征"""
        try:
            feature_request = FeatureRequest(
                entity_ids=entity_ids,
                feature_service=feature_service
            )
            
            response = await feast_client.get_online_features(feature_request)
            return response.dict()
            
        except Exception as e:
            self.logger.error(f"获取在线特征失败: {e}")
            return {"error": str(e)}
    
    async def get_historical_features(self, entity_df_dict: Dict[str, Any], 
                                    features: List[str]) -> Dict[str, Any]:
        """获取历史特征"""
        try:
            # 转换为 DataFrame
            entity_df = pd.DataFrame(entity_df_dict)
            
            # 确保有 event_timestamp 列
            if "event_timestamp" not in entity_df.columns:
                entity_df["event_timestamp"] = datetime.now()
            
            result_df = await feast_client.get_historical_features(
                entity_df=entity_df,
                features=features
            )
            
            return {
                "features": result_df.to_dict('records'),
                "shape": result_df.shape,
                "columns": list(result_df.columns)
            }
            
        except Exception as e:
            self.logger.error(f"获取历史特征失败: {e}")
            return {"error": str(e)}
    
    async def get_feature_store_info(self) -> Dict[str, Any]:
        """获取特征存储信息"""
        try:
            return await feast_client.get_feature_store_info()
        except Exception as e:
            self.logger.error(f"获取特征存储信息失败: {e}")
            return {"error": str(e)}


# 全局服务实例
taxi_prediction_service = TaxiPredictionService()
feast_feature_service = FeastFeatureService()
