#!/usr/bin/env python3
"""
FastAPI 主应用 - 包含 Feast Feature Store 集成
简化版本，专注于 Feast 功能
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import pandas as pd
import numpy as np
import uuid

# 尝试导入 Feast 相关模块
try:
    from api.feast_client import FeastClient
    feast_client = FeastClient()
    FEAST_CLIENT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Feast client import failed: {e}")
    feast_client = None
    FEAST_CLIENT_AVAILABLE = False

# 尝试导入 Kafka 路由
try:
    from api.kafka_routes import router as kafka_router
    KAFKA_ROUTES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Kafka routes import failed: {e}")
    KAFKA_ROUTES_AVAILABLE = False

# 尝试导入 MLflow 路由
try:
    from api.mlflow_routes import mlflow_router
    MLFLOW_ROUTES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"MLflow routes import failed: {e}")
    MLFLOW_ROUTES_AVAILABLE = False

# 尝试导入 MLMD 路由
try:
    from api.mlmd_routes import mlmd_router
    MLMD_ROUTES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"MLMD routes import failed: {e}")
    MLMD_ROUTES_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Chicago Taxi MLOps 平台 API",
    description="基于 Feast 的 Chicago Taxi 费用预测 API 服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含 Kafka 路由
if KAFKA_ROUTES_AVAILABLE:
    app.include_router(kafka_router)
    logger.info("Kafka routes included successfully")
else:
    logger.warning("Kafka routes not available")

# 包含 MLflow 路由
if MLFLOW_ROUTES_AVAILABLE:
    app.include_router(mlflow_router)
    logger.info("MLflow routes included successfully")
else:
    logger.warning("MLflow routes not available")

# 包含 MLMD 路由
if MLMD_ROUTES_AVAILABLE:
    app.include_router(mlmd_router)
    logger.info("MLMD routes included successfully")
else:
    logger.warning("MLMD routes not available")

# 数据模型
class TaxiPredictionRequest(BaseModel):
    """出租车预测请求模型"""
    trip_miles: float = Field(..., description="行程距离（英里）")
    trip_seconds: int = Field(..., description="行程时间（秒）")
    pickup_latitude: float = Field(..., description="上车纬度")
    pickup_longitude: float = Field(..., description="上车经度")
    dropoff_latitude: float = Field(..., description="下车纬度")
    dropoff_longitude: float = Field(..., description="下车经度")
    pickup_hour: int = Field(..., description="上车小时")
    pickup_day_of_week: int = Field(..., description="上车星期几")
    passenger_count: int = Field(1, description="乘客数量")
    company: str = Field("", description="出租车公司")

class PredictionResponse(BaseModel):
    """预测响应模型"""
    trip_id: str
    predicted_fare: float
    confidence: float
    features_used: Dict[str, Any]
    timestamp: str

# 简化的预测服务
class SimpleTaxiPredictionService:
    """简化的出租车费用预测服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model_version = "v1.0.0"
    
    def predict_fare(self, features: Dict[str, Any]) -> tuple:
        """简化的费用预测算法"""
        try:
            # 基础费用计算
            base_fare = 2.25
            trip_miles = features.get("trip_miles", 0)
            distance_fare = trip_miles * 1.75
            trip_seconds = features.get("trip_seconds", 0)
            time_fare = (trip_seconds / 60) * 0.25
            
            # 时段调整
            pickup_hour = features.get("pickup_hour", 12)
            peak_multiplier = 1.0
            if pickup_hour in [7, 8, 17, 18, 19]:
                peak_multiplier = 1.3
            elif pickup_hour >= 22 or pickup_hour <= 5:
                peak_multiplier = 1.2
            
            # 计算总费用
            total_fare = (base_fare + distance_fare + time_fare) * peak_multiplier
            noise = np.random.normal(0, 0.5)
            total_fare += noise
            total_fare = max(2.25, min(total_fare, 100.0))
            
            # 计算置信度
            confidence = 0.85 + np.random.normal(0, 0.1)
            confidence = max(0.1, min(confidence, 0.99))
            
            return total_fare, confidence
            
        except Exception as e:
            self.logger.error(f"预测失败: {e}")
            return 10.0, 0.5

# 初始化服务
prediction_service = SimpleTaxiPredictionService()

# API 路由
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Chicago Taxi MLOps 平台 API",
        "version": "1.0.0",
        "status": "running",
        "feast_available": FEAST_CLIENT_AVAILABLE,
        "mlflow_available": MLFLOW_ROUTES_AVAILABLE,
        "kafka_available": KAFKA_ROUTES_AVAILABLE,
        "mlmd_available": MLMD_ROUTES_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running",
            "prediction": "available",
            "feast": "available" if FEAST_CLIENT_AVAILABLE else "mock_mode",
            "mlflow": "available" if MLFLOW_ROUTES_AVAILABLE else "unavailable",
            "kafka": "available" if KAFKA_ROUTES_AVAILABLE else "unavailable",
            "mlmd": "available" if MLMD_ROUTES_AVAILABLE else "unavailable"
        }
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict_taxi_fare(request: TaxiPredictionRequest):
    """单次出租车费用预测"""
    try:
        trip_id = f"trip_{uuid.uuid4().hex[:8]}"
        
        features = {
            "trip_miles": request.trip_miles,
            "trip_seconds": request.trip_seconds,
            "pickup_latitude": request.pickup_latitude,
            "pickup_longitude": request.pickup_longitude,
            "dropoff_latitude": request.dropoff_latitude,
            "dropoff_longitude": request.dropoff_longitude,
            "pickup_hour": request.pickup_hour,
            "pickup_day_of_week": request.pickup_day_of_week,
            "passenger_count": request.passenger_count,
            "company": request.company
        }
        
        predicted_fare, confidence = prediction_service.predict_fare(features)
        
        return PredictionResponse(
            trip_id=trip_id,
            predicted_fare=round(predicted_fare, 2),
            confidence=round(confidence, 3),
            features_used=features,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")

@app.post("/predict/batch")
async def predict_taxi_fare_batch(requests: List[TaxiPredictionRequest]):
    """批量出租车费用预测"""
    results = []
    
    for request in requests:
        try:
            result = await predict_taxi_fare(request)
            results.append(result)
        except Exception as e:
            logger.error(f"批量预测中的单个请求失败: {e}")
            results.append(PredictionResponse(
                trip_id=f"error_{uuid.uuid4().hex[:8]}",
                predicted_fare=0.0,
                confidence=0.0,
                features_used={},
                timestamp=datetime.now().isoformat()
            ))
    
    return {"results": results, "total_processed": len(results)}

# Feast Feature Store 路由
@app.get("/feast/info")
async def get_feast_info():
    """获取 Feast 特征存储信息"""
    try:
        if FEAST_CLIENT_AVAILABLE:
            info = await feast_client.get_feature_store_info()
            return {
                "status": "success",
                "data": info,
                "message": "特征存储信息获取成功"
            }
        else:
            # 模拟模式
            mock_info = {
                "feast_available": False,
                "redis_available": False,
                "store_connected": False,
                "redis_connected": False,
                "repo_path": "feast",
                "feature_views_count": 2,
                "feature_services_count": 2,
                "status": "mock_mode",
                "message": "使用模拟模式 - Feast 或 Redis 服务未运行"
            }
            return {
                "status": "success",
                "data": mock_info,
                "message": "特征存储信息获取成功（模拟模式）"
            }
    except Exception as e:
        logger.error(f"获取特征存储信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征存储信息失败: {str(e)}")

@app.get("/feast/feature-views")
async def get_feature_views():
    """获取特征视图列表"""
    try:
        if FEAST_CLIENT_AVAILABLE:
            feature_views = await feast_client.list_feature_views()
            return {
                "status": "success",
                "data": feature_views,
                "count": len(feature_views),
                "message": f"成功获取 {len(feature_views)} 个特征视图"
            }
        else:
            # 模拟数据
            mock_feature_views = [
                {
                    "name": "trip_features",
                    "entities": ["trip_id"],
                    "features": ["trip_miles", "trip_seconds", "fare", "pickup_latitude", "pickup_longitude"],
                    "ttl_seconds": 604800,
                    "tags": {"team": "mlops", "type": "batch"}
                },
                {
                    "name": "area_features",
                    "entities": ["area_id"],
                    "features": ["avg_trip_distance", "avg_trip_duration", "avg_fare"],
                    "ttl_seconds": 2592000,
                    "tags": {"team": "mlops", "type": "aggregated"}
                }
            ]
            return {
                "status": "success",
                "data": mock_feature_views,
                "count": len(mock_feature_views),
                "message": f"成功获取 {len(mock_feature_views)} 个特征视图（模拟模式）"
            }
    except Exception as e:
        logger.error(f"获取特征视图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征视图失败: {str(e)}")

@app.get("/feast/feature-services")
async def get_feature_services():
    """获取特征服务列表"""
    try:
        if FEAST_CLIENT_AVAILABLE:
            feature_services = await feast_client.list_feature_services()
            return {
                "status": "success",
                "data": feature_services,
                "count": len(feature_services),
                "message": f"成功获取 {len(feature_services)} 个特征服务"
            }
        else:
            # 模拟数据
            mock_feature_services = [
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
            return {
                "status": "success",
                "data": mock_feature_services,
                "count": len(mock_feature_services),
                "message": f"成功获取 {len(mock_feature_services)} 个特征服务（模拟模式）"
            }
    except Exception as e:
        logger.error(f"获取特征服务失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征服务失败: {str(e)}")

@app.get("/feast/stats")
async def get_feast_stats():
    """获取 Feast 统计信息"""
    try:
        if FEAST_CLIENT_AVAILABLE:
            info = await feast_client.get_feature_store_info()
            feature_views = await feast_client.list_feature_views()
            feature_services = await feast_client.list_feature_services()
            
            stats = {
                "feature_store_info": info,
                "feature_views_count": len(feature_views),
                "feature_services_count": len(feature_services),
                "feature_views": [fv.get("name", "unknown") for fv in feature_views],
                "feature_services": [fs.get("name", "unknown") for fs in feature_services],
                "status": "healthy" if info.get("store_connected", False) else "degraded"
            }
        else:
            # 模拟统计数据
            stats = {
                "feature_store_info": {
                    "feast_available": False,
                    "redis_available": False,
                    "store_connected": False,
                    "status": "mock_mode"
                },
                "feature_views_count": 2,
                "feature_services_count": 2,
                "feature_views": ["trip_features", "area_features"],
                "feature_services": ["model_inference_v1", "realtime_inference_v1"],
                "status": "mock_mode"
            }
        
        return {
            "status": "success",
            "data": stats,
            "message": "特征存储统计获取成功"
        }
    except Exception as e:
        logger.error(f"获取特征存储统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征存储统计失败: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """获取服务指标"""
    return {
        "service_name": "taxi_prediction_api",
        "version": "1.0.0",
        "uptime": "running",
        "feast_status": "available" if FEAST_CLIENT_AVAILABLE else "mock_mode",
        "predictions_served": "N/A",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
