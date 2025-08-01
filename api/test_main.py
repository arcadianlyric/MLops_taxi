#!/usr/bin/env python3
"""
简化版 FastAPI 服务 - 用于测试基本功能
不依赖 Feast、KFServing 等复杂组件
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="MLOps Test API",
    description="简化版 MLOps API 服务 - 用于测试基本功能",
    version="1.0.0"
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
class PredictionRequest(BaseModel):
    features: Dict[str, Any]
    model_name: Optional[str] = "taxi_model"

class PredictionResponse(BaseModel):
    prediction: float
    confidence: float
    model_name: str
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

# 模拟预测函数
def mock_prediction(features: Dict[str, Any]) -> Dict[str, Any]:
    """模拟模型预测"""
    # 简单的线性模拟预测
    trip_distance = features.get('trip_distance', 1.0)
    pickup_hour = features.get('pickup_hour', 12)
    
    # 模拟出租车费用预测
    base_fare = 2.5
    distance_rate = 2.0
    time_multiplier = 1.0 + (pickup_hour - 12) * 0.1 / 12  # 高峰时段调整
    
    prediction = base_fare + (trip_distance * distance_rate * time_multiplier)
    confidence = min(0.95, 0.7 + np.random.random() * 0.25)
    
    return {
        "prediction": round(prediction, 2),
        "confidence": round(confidence, 3)
    }

@app.get("/", response_model=Dict[str, str])
async def root():
    """根路径"""
    return {
        "message": "MLOps Test API 服务运行中",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """在线预测"""
    try:
        logger.info(f"收到预测请求: {request.features}")
        
        # 模拟预测
        result = mock_prediction(request.features)
        
        response = PredictionResponse(
            prediction=result["prediction"],
            confidence=result["confidence"],
            model_name=request.model_name,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"预测结果: {response}")
        return response
        
    except Exception as e:
        logger.error(f"预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")

@app.post("/predict/batch")
async def predict_batch(requests: List[PredictionRequest]):
    """批量预测"""
    try:
        logger.info(f"收到批量预测请求，数量: {len(requests)}")
        
        results = []
        for req in requests:
            result = mock_prediction(req.features)
            results.append(PredictionResponse(
                prediction=result["prediction"],
                confidence=result["confidence"],
                model_name=req.model_name,
                timestamp=datetime.now().isoformat()
            ))
        
        logger.info(f"批量预测完成，结果数量: {len(results)}")
        return {"predictions": results, "count": len(results)}
        
    except Exception as e:
        logger.error(f"批量预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量预测失败: {str(e)}")

@app.get("/models")
async def list_models():
    """列出可用模型"""
    return {
        "models": [
            {
                "name": "taxi_model",
                "version": "v1.0",
                "status": "ready",
                "description": "出租车费用预测模型（模拟）"
            }
        ]
    }

@app.get("/metrics")
async def get_metrics():
    """获取服务指标"""
    return {
        "requests_total": 100,
        "predictions_total": 85,
        "errors_total": 2,
        "avg_response_time_ms": 45.2,
        "model_accuracy": 0.89,
        "uptime_seconds": 3600
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
