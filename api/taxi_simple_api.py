#!/usr/bin/env python3
"""
简化的Chicago Taxi Tip预测API
用于K8s部署和UI测试
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import logging
import numpy as np
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Chicago Taxi Tip Prediction API",
    description="简化版Taxi Tip预测服务",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class TaxiTripRequest(BaseModel):
    """Taxi行程请求模型"""
    trip_miles: float = Field(..., description="行程距离（英里）")
    trip_seconds: int = Field(..., description="行程时长（秒）")
    fare: float = Field(..., description="车费（美元）")
    pickup_latitude: float = Field(..., description="上车纬度")
    pickup_longitude: float = Field(..., description="上车经度")
    dropoff_latitude: float = Field(..., description="下车纬度")
    dropoff_longitude: float = Field(..., description="下车经度")
    pickup_hour: int = Field(..., description="上车小时", ge=0, le=23)
    pickup_day_of_week: int = Field(..., description="星期几", ge=0, le=6)
    trip_start_day: int = Field(..., description="日期", ge=1, le=31)
    trip_start_month: int = Field(..., description="月份", ge=1, le=12)
    pickup_community_area: int = Field(..., description="上车社区区域")
    dropoff_community_area: int = Field(..., description="下车社区区域")
    pickup_census_tract: int = Field(..., description="上车人口普查区")
    dropoff_census_tract: int = Field(..., description="下车人口普查区")
    payment_type: str = Field(..., description="支付方式")
    company: str = Field(..., description="出租车公司")
    passenger_count: int = Field(default=1, description="乘客数量")

class BatchTripRequest(BaseModel):
    """批量预测请求"""
    trips: List[TaxiTripRequest]
    model_name: str = "taxi_model"

# 简化的tip预测函数（基于规则的模型）
def predict_tip(trip: TaxiTripRequest) -> float:
    """
    基于规则的tip预测
    实际部署中应该调用训练好的ML模型
    """
    # 基础tip率
    base_tip_rate = 0.15
    
    # 根据支付方式调整
    payment_multiplier = {
        "Credit Card": 1.5,
        "Cash": 0.5,
        "No Charge": 0.0,
        "Dispute": 0.1,
        "Unknown": 0.3
    }.get(trip.payment_type, 0.8)
    
    # 根据时间调整（晚高峰tip更高）
    time_multiplier = 1.0
    if 17 <= trip.pickup_hour <= 20:  # 晚高峰
        time_multiplier = 1.3
    elif 6 <= trip.pickup_hour <= 9:  # 早高峰
        time_multiplier = 1.2
    elif 0 <= trip.pickup_hour <= 5:  # 深夜
        time_multiplier = 1.4
    
    # 根据距离调整
    distance_multiplier = 1.0
    if trip.trip_miles > 10:
        distance_multiplier = 1.1
    elif trip.trip_miles < 2:
        distance_multiplier = 0.9
    
    # 计算预测tip
    predicted_tip = (
        trip.fare * base_tip_rate * 
        payment_multiplier * 
        time_multiplier * 
        distance_multiplier
    )
    
    # 添加一些随机性使其更真实
    noise = np.random.normal(0, 0.5)
    predicted_tip = max(0, predicted_tip + noise)
    
    return round(predicted_tip, 2)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Chicago Taxi Tip Prediction API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "predict": "/predict",
            "batch_predict": "/batch_predict",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "taxi-tip-prediction",
        "version": "1.0.0"
    }

@app.post("/predict")
async def predict(trip: TaxiTripRequest):
    """
    单次tip预测
    """
    try:
        logger.info(f"收到预测请求: fare=${trip.fare}, miles={trip.trip_miles}")
        
        # 预测tip
        predicted_tip = predict_tip(trip)
        
        # 计算额外信息
        tip_rate = (predicted_tip / trip.fare * 100) if trip.fare > 0 else 0
        total_cost = trip.fare + predicted_tip
        
        response = {
            "fare_amount": trip.fare,
            "predicted_tip": predicted_tip,
            "tip_rate": round(tip_rate, 2),
            "total_cost": round(total_cost, 2),
            "payment_type": trip.payment_type,
            "trip_miles": trip.trip_miles,
            "pickup_hour": trip.pickup_hour,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"预测完成: tip=${predicted_tip}, rate={tip_rate:.1f}%")
        return response
        
    except Exception as e:
        logger.error(f"预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预测错误: {str(e)}")

@app.post("/batch_predict")
async def batch_predict(request: BatchTripRequest):
    """
    批量tip预测
    """
    try:
        logger.info(f"收到批量预测请求: {len(request.trips)} 个行程")
        
        predictions = []
        for trip in request.trips:
            predicted_tip = predict_tip(trip)
            predictions.append(predicted_tip)
        
        response = {
            "predictions": predictions,
            "count": len(predictions),
            "model_name": request.model_name,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"批量预测完成: {len(predictions)} 个结果")
        return response
        
    except Exception as e:
        logger.error(f"批量预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量预测错误: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """获取服务指标"""
    return {
        "service": "taxi-tip-prediction",
        "status": "running",
        "model_status": "loaded",
        "api_status": True,
        "total_predictions": 0,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
