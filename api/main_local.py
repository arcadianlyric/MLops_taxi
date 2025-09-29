#!/usr/bin/env python3
"""
FastAPI 本地运行版本 - 简化的 MLOps 平台 API 服务
用于本地开发和测试，不依赖 TFX/KFServing/Feast
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import random
import numpy as np
from datetime import datetime
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Chicago Taxi MLOps 平台 API (本地版)",
    description="本地开发版本的 Chicago Taxi 费用预测 API 服务",
    version="1.0.0-local",
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

# Pydantic 模型定义
class TaxiFeatures(BaseModel):
    """出租车特征模型"""
    trip_miles: float = Field(..., description="行程距离（英里）", example=3.5)
    trip_seconds: int = Field(..., description="行程时长（秒）", example=900)
    fare: float = Field(..., description="车费", example=12.5)
    pickup_latitude: float = Field(..., description="上车纬度", example=41.88)
    pickup_longitude: float = Field(..., description="上车经度", example=-87.63)
    dropoff_latitude: float = Field(..., description="下车纬度", example=41.89)
    dropoff_longitude: float = Field(..., description="下车经度", example=-87.62)
    trip_start_hour: int = Field(..., description="出发小时", example=14)
    trip_start_day: int = Field(..., description="出发日", example=15)
    trip_start_month: int = Field(..., description="出发月", example=6)
    pickup_community_area: float = Field(..., description="上车社区区域", example=8)
    dropoff_community_area: float = Field(..., description="下车社区区域", example=24)
    pickup_census_tract: float = Field(..., description="上车人口普查区", example=170301)
    dropoff_census_tract: float = Field(..., description="下车人口普查区", example=170401)
    payment_type: str = Field(..., description="支付方式", example="Credit Card")
    company: str = Field(..., description="出租车公司", example="Flash Cab")

class PredictionRequest(BaseModel):
    """预测请求模型"""
    features: TaxiFeatures
    model_name: str = Field("taxi_model", description="模型名称")

class BatchPredictionRequest(BaseModel):
    """批量预测请求模型"""
    trips: List[TaxiFeatures]
    model_name: str = Field("taxi_model", description="模型名称")

class PredictionResponse(BaseModel):
    """预测响应模型"""
    prediction: float
    confidence: float
    model_version: str
    timestamp: str

class BatchPredictionResponse(BaseModel):
    """批量预测响应模型"""
    predictions: List[float]
    total_processed: int
    model_version: str
    timestamp: str

class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    timestamp: str
    api_status: bool
    model_status: str
    total_predictions: int

# 全局状态
prediction_count = 0

def simulate_taxi_tip_prediction(features: TaxiFeatures) -> float:
    """
    模拟出租车小费预测
    基于一些简单的规则和随机性
    """
    global prediction_count
    prediction_count += 1
    
    # 基础小费计算
    base_tip = features.fare * 0.15  # 基础15%小费率
    
    # 根据支付方式调整
    payment_multiplier = {
        "Credit Card": 1.2,
        "Cash": 0.8,
        "No Charge": 0.0,
        "Dispute": 0.1,
        "Unknown": 1.0
    }.get(features.payment_type, 1.0)
    
    # 根据时间调整（晚上和早上高峰期小费更高）
    hour_multiplier = 1.0
    if 6 <= features.trip_start_hour <= 9:  # 早高峰
        hour_multiplier = 1.3
    elif 17 <= features.trip_start_hour <= 20:  # 晚高峰
        hour_multiplier = 1.4
    elif 22 <= features.trip_start_hour or features.trip_start_hour <= 5:  # 深夜
        hour_multiplier = 1.5
    
    # 根据距离调整
    distance_multiplier = 1.0
    if features.trip_miles > 10:  # 长途
        distance_multiplier = 1.2
    elif features.trip_miles < 1:  # 短途
        distance_multiplier = 0.9
    
    # 根据公司调整
    company_multiplier = {
        "Flash Cab": 1.1,
        "Taxi Affiliation Services": 1.0,
        "Yellow Cab": 0.95,
        "Blue Diamond": 1.05,
        "Other": 1.0
    }.get(features.company, 1.0)
    
    # 计算最终小费
    predicted_tip = base_tip * payment_multiplier * hour_multiplier * distance_multiplier * company_multiplier
    
    # 添加一些随机性
    noise = random.gauss(0, 0.5)
    predicted_tip = max(0, predicted_tip + noise)
    
    return round(predicted_tip, 2)

# API 路由定义

@app.get("/", summary="API 信息")
async def root():
    """根路径 - API 信息"""
    return {
        "message": "Chicago Taxi MLOps 平台 API 服务 (本地版)",
        "version": "1.0.0-local",
        "description": "本地开发版本，使用模拟预测",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "出租车小费预测 (模拟)",
            "批量预测",
            "健康检查",
            "指标监控"
        ]
    }

@app.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        api_status=True,
        model_status="simulated",
        total_predictions=prediction_count
    )

@app.post("/predict", response_model=PredictionResponse, summary="单次预测")
async def predict(request: PredictionRequest):
    """
    单次出租车小费预测
    """
    try:
        logger.info(f"🚕 收到预测请求: {request.features.trip_miles} 英里行程")
        
        # 执行预测
        predicted_tip = simulate_taxi_tip_prediction(request.features)
        
        # 计算置信度（模拟）
        confidence = random.uniform(0.75, 0.95)
        
        response = PredictionResponse(
            prediction=predicted_tip,
            confidence=confidence,
            model_version="taxi_model_v1.0_simulated",
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"✅ 预测完成: ${predicted_tip} 小费")
        return response
        
    except Exception as e:
        logger.error(f"❌ 预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"预测服务错误: {str(e)}")

@app.post("/batch_predict", response_model=BatchPredictionResponse, summary="批量预测")
async def batch_predict(request: BatchPredictionRequest):
    """
    批量出租车小费预测
    """
    try:
        logger.info(f"📦 收到批量预测请求: {len(request.trips)} 个行程")
        
        predictions = []
        for trip in request.trips:
            predicted_tip = simulate_taxi_tip_prediction(trip)
            predictions.append(predicted_tip)
        
        response = BatchPredictionResponse(
            predictions=predictions,
            total_processed=len(predictions),
            model_version="taxi_model_v1.0_simulated",
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"✅ 批量预测完成: {len(predictions)} 个结果")
        return response
        
    except Exception as e:
        logger.error(f"❌ 批量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量预测服务错误: {str(e)}")

@app.get("/metrics", summary="服务指标")
async def get_metrics():
    """获取服务指标"""
    return {
        "service": "mlops-api-local",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "total_predictions": prediction_count,
        "model_status": "simulated",
        "api_status": True
    }

# 运行服务
if __name__ == "__main__":
    uvicorn.run(
        "main_local:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
