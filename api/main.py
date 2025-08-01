#!/usr/bin/env python3
"""
FastAPI 主应用 - MLOps 平台 API 服务
集成 KFServing 在线推理和 Feast 特征存储
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from feast_routes import feast_router
from taxi_prediction_endpoints import taxi_router
from kafka_routes import kafka_router
from mlflow_routes import mlflow_router
from mlmd_routes import mlmd_router
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import asyncio
from datetime import datetime
import uvicorn
import pandas as pd
import numpy as np

from inference_client import KFServingInferenceClient
from feast_client import feast_client, FeatureRequest, FeatureResponse

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
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局推理客户端
inference_client = None

# Pydantic 模型定义
class TaxiPredictionRequest(BaseModel):
    """出租车费用预测请求模型"""
    trip_miles: float = Field(..., description="行程距离（英里）", example=3.5)
    trip_seconds: int = Field(..., description="行程时长（秒）", example=900)
    pickup_latitude: float = Field(..., description="上车纬度", example=41.88)
    pickup_longitude: float = Field(..., description="上车经度", example=-87.63)
    dropoff_latitude: float = Field(..., description="下车纬度", example=41.89)
    dropoff_longitude: float = Field(..., description="下车经度", example=-87.62)
    pickup_hour: int = Field(..., description="上车小时", example=14)
    pickup_day_of_week: int = Field(..., description="上车星期几", example=1)
    pickup_month: int = Field(..., description="上车月份", example=6)
    passenger_count: int = Field(..., description="乘客数量", example=2)
    payment_type: str = Field(..., description="支付方式", example="Credit Card")
    company: str = Field(..., description="出租车公司", example="Flash Cab")
    
    class Config:
        schema_extra = {
            "example": {
                "trip_miles": 3.5,
                "trip_seconds": 900,
                "pickup_latitude": 41.88,
                "pickup_longitude": -87.63,
                "dropoff_latitude": 41.89,
                "dropoff_longitude": -87.62,
                "pickup_hour": 14,
                "pickup_day_of_week": 1,
                "pickup_month": 6,
                "passenger_count": 2,
                "payment_type": "Credit Card",
                "company": "Flash Cab"
            }
        }

class TaxiPredictionResponse(BaseModel):
    """出租车费用预测响应模型"""
    trip_id: str
    predicted_fare: float
    confidence: float
    features_used: Dict[str, Any]
    model_version: str
    timestamp: str

class BatchTaxiPredictionRequest(BaseModel):
    """批量出租车费用预测请求模型"""
    trips: List[TaxiPredictionRequest] = Field(..., description="批量行程请求列表")
    batch_size: Optional[int] = Field(32, description="批次大小")
    use_feast_features: bool = Field(True, description="是否使用Feast特征")

class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    timestamp: str
    service_health: bool
    version: str
    feast_health: Optional[Dict[str, Any]] = None

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global inference_client
    
    logger.info("🚀 启动 MLOps API 服务...")
    
    # 初始化推理客户端
    try:
        inference_client = KFServingInferenceClient(
            service_url="http://movie-recommendation-model.default.svc.cluster.local",
            feast_repo_path="./feast/feature_repo"
        )
        logger.info("✅ KFServing 推理客户端初始化成功")
    except Exception as e:
        logger.error(f"❌ 推理客户端初始化失败: {e}")
        # 使用本地测试地址作为备用
        inference_client = KFServingInferenceClient(
            service_url="http://localhost:8080",
            feast_repo_path="./feast/feature_repo"
        )

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    logger.info("🛑 关闭 MLOps API 服务...")

# API 路由定义

@app.get("/", summary="API 信息")
async def root():
    """
    根路径 - API 信息
    """
    return {
        "message": "Chicago Taxi MLOps 平台 API 服务",
        "version": "1.0.0",
        "description": "基于 KFServing 和 Feast 的 Chicago Taxi 费用预测 API",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "出租车费用预测",
            "Feast 特征存储集成",
            "批量预测",
            "实时特征获取",
            "历史特征查询"
        ]
    }

@app.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check():
    """
    健康检查接口
    """
    try:
        # 检查推理客户端状态
        client_status = inference_client is not None
        
        # 检查 Feast 状态
        feast_health = await feast_client.health_check()
        
        overall_status = "healthy"
        if not client_status or feast_health["status"] != "healthy":
            overall_status = "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            service_health=client_status,
            version="1.0.0",
            feast_health=feast_health
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")

@app.post("/predict", response_model=List[TaxiPredictionResponse])
async def predict(request: TaxiPredictionRequest):
    """
    单次推理接口
    
    执行用户-电影推荐预测
    """
    try:
        if not inference_client:
            raise HTTPException(status_code=503, detail="推理服务未初始化")
        
        # 验证输入
        if len(request.user_ids) != len(request.movie_ids):
            raise HTTPException(
                status_code=400, 
                detail="用户ID和电影ID列表长度必须相同"
            )
        
        if not request.user_ids:
            raise HTTPException(status_code=400, detail="输入列表不能为空")
        
        logger.info(f"🎯 收到推理请求: {len(request.user_ids)} 个用户-电影对")
        
        # 执行推理
        results = inference_client.predict(request.user_ids, request.movie_ids)
        
        # 转换为响应模型
        response = [
            PredictionResponse(**result) for result in results
        ]
        
        logger.info(f"✅ 推理完成: {len(response)} 个结果")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 推理失败: {e}")
        raise HTTPException(status_code=500, detail=f"推理服务错误: {str(e)}")

@app.post("/predict/async", response_model=List[PredictionResponse])
async def predict_async(request: PredictionRequest):
    """
    异步推理接口
    
    执行异步用户-电影推荐预测
    """
    try:
        if not inference_client:
            raise HTTPException(status_code=503, detail="推理服务未初始化")
        
        # 验证输入
        if len(request.user_ids) != len(request.movie_ids):
            raise HTTPException(
                status_code=400, 
                detail="用户ID和电影ID列表长度必须相同"
            )
        
        logger.info(f"⚡ 收到异步推理请求: {len(request.user_ids)} 个用户-电影对")
        
        # 执行异步推理
        results = await inference_client.predict_async(request.user_ids, request.movie_ids)
        
        # 转换为响应模型
        response = [
            PredictionResponse(**result) for result in results
        ]
        
        logger.info(f"✅ 异步推理完成: {len(response)} 个结果")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 异步推理失败: {e}")
        raise HTTPException(status_code=500, detail=f"异步推理服务错误: {str(e)}")

@app.post("/predict/batch", response_model=List[PredictionResponse])
async def predict_batch(request: BatchPredictionRequest):
    """
    批量推理接口
    
    执行批量用户-电影推荐预测
    """
    try:
        if not inference_client:
            raise HTTPException(status_code=503, detail="推理服务未初始化")
        
        if not request.requests:
            raise HTTPException(status_code=400, detail="批量请求列表不能为空")
        
        logger.info(f"📦 收到批量推理请求: {len(request.requests)} 个批次")
        
        # 执行批量推理
        results = inference_client.batch_predict(
            request.requests, 
            batch_size=request.batch_size
        )
        
        # 转换为响应模型
        response = [
            PredictionResponse(**result) for result in results
        ]
        
        logger.info(f"✅ 批量推理完成: {len(response)} 个结果")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 批量推理失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量推理服务错误: {str(e)}")

@app.get("/recommend/{user_id}")
async def recommend_for_user(
    user_id: int, 
    num_recommendations: int = 10,
    min_score: float = 0.5
):
    """
    为特定用户推荐电影
    
    Args:
        user_id: 用户ID
        num_recommendations: 推荐数量
        min_score: 最低推荐分数
    """
    try:
        if not inference_client:
            raise HTTPException(status_code=503, detail="推理服务未初始化")
        
        # 生成候选电影列表 (实际应用中从数据库获取)
        candidate_movies = list(range(1, num_recommendations * 2 + 1))
        user_ids = [user_id] * len(candidate_movies)
        
        logger.info(f"🎬 为用户 {user_id} 生成 {num_recommendations} 个推荐")
        
        # 执行推理
        results = inference_client.predict(user_ids, candidate_movies)
        
        # 过滤和排序
        filtered_results = [
            result for result in results 
            if result['prediction_score'] >= min_score
        ]
        
        # 按分数排序
        sorted_results = sorted(
            filtered_results, 
            key=lambda x: x['prediction_score'], 
            reverse=True
        )[:num_recommendations]
        
        # 转换为推荐格式
        recommendations = [
            {
                "movie_id": result['movie_id'],
                "score": result['prediction_score'],
                "confidence": result['confidence'],
                "rank": i + 1
            }
            for i, result in enumerate(sorted_results)
        ]
        
        logger.info(f"✅ 为用户 {user_id} 生成了 {len(recommendations)} 个推荐")
        
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "total_candidates": len(candidate_movies),
            "filtered_count": len(filtered_results),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 推荐生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"推荐服务错误: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """获取服务指标"""
    try:
        # 这里可以集成 Prometheus 指标
        return {
            "service": "mlops-api",
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "inference_client_status": inference_client.health_check() if inference_client else False
        }
    except Exception as e:
        logger.error(f"❌ 指标获取失败: {e}")
        raise HTTPException(status_code=500, detail="指标服务错误")

# 后台任务示例
@app.post("/predict/background")
async def predict_background(request: PredictionRequest, background_tasks: BackgroundTasks):
    """后台推理任务"""
    
    def run_background_prediction():
        """后台执行推理"""
        try:
            results = inference_client.predict(request.user_ids, request.movie_ids)
            logger.info(f"🔄 后台推理完成: {len(results)} 个结果")
            # 这里可以将结果保存到数据库或发送到消息队列
        except Exception as e:
            logger.error(f"❌ 后台推理失败: {e}")
    
    background_tasks.add_task(run_background_prediction)
    
    return {
        "message": "后台推理任务已提交",
        "request_id": f"bg_{datetime.now().timestamp()}",
        "status": "submitted"
    }

# 注册路由器
app.include_router(feast_router)
app.include_router(taxi_router)
app.include_router(kafka_router)
app.include_router(mlflow_router)
app.include_router(mlmd_router)

# 运行服务
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
