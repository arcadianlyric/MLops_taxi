#!/usr/bin/env python3
"""
简化版 FastAPI 主应用 - 快速启动 MLOps 平台
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Chicago Taxi MLOps 平台 API",
    description="基于 KFServing 和 Feast 的 Chicago Taxi 费用预测 API 服务",
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
        """
        简化的费用预测算法
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
            
            # 计算置信度
            feature_completeness = len([v for v in features.values() if v is not None and v != ""]) / len(features)
            confidence = 0.7 + (feature_completeness * 0.3)
            confidence = max(0.1, min(confidence, 0.99))
            
            return total_fare, confidence
            
        except Exception as e:
            self.logger.error(f"预测失败: {e}")
            return 10.0, 0.5  # 默认值

# 初始化服务
prediction_service = SimpleTaxiPredictionService()

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Chicago Taxi MLOps 平台 API",
        "version": "1.0.0",
        "status": "running",
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
            "prediction": "available"
        }
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict_taxi_fare(request: TaxiPredictionRequest):
    """
    单次出租车费用预测
    """
    try:
        # 生成行程ID
        import uuid
        trip_id = f"trip_{uuid.uuid4().hex[:8]}"
        
        # 准备特征
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
        
        # 预测费用
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
    """
    批量出租车费用预测
    """
    results = []
    
    for request in requests:
        try:
            result = await predict_taxi_fare(request)
            results.append(result)
        except Exception as e:
            logger.error(f"批量预测中的单个请求失败: {e}")
            # 添加错误结果
            import uuid
            results.append(PredictionResponse(
                trip_id=f"error_{uuid.uuid4().hex[:8]}",
                predicted_fare=0.0,
                confidence=0.0,
                features_used={},
                timestamp=datetime.now().isoformat()
            ))
    
    return {"results": results, "total_processed": len(results)}

@app.get("/metrics")
async def get_metrics():
    """获取服务指标"""
    return {
        "service_name": "taxi_prediction_api",
        "version": "1.0.0",
        "uptime": "running",
        "predictions_served": "N/A",
        "average_response_time": "N/A",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
