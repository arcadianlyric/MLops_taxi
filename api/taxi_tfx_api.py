#!/usr/bin/env python3
"""
Chicago Taxi Tip预测API - 使用TFX训练的模型
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import logging
import numpy as np
import tensorflow as tf
import os
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Chicago Taxi Tip Prediction API (TFX Model)",
    description="使用TFX训练的真实ML模型进行Taxi Tip预测",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量存储模型
MODEL = None
MODEL_PATH = None

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
    trip_start_day: int = Field(..., description="日期", ge=1, le=31)
    trip_start_month: int = Field(..., description="月份", ge=1, le=12)
    pickup_community_area: int = Field(..., description="上车社区区域", default=0)
    dropoff_community_area: int = Field(..., description="下车社区区域", default=0)
    payment_type: str = Field(..., description="支付方式")
    company: str = Field(..., description="出租车公司", default="")
    pickup_census_tract: int = Field(..., description="上车人口普查区", default=0)
    dropoff_census_tract: int = Field(..., description="下车人口普查区", default=0)


class PredictionResponse(BaseModel):
    """预测响应模型"""
    predicted_tip: float = Field(..., description="预测的小费金额")
    tip_percentage: float = Field(..., description="小费占车费的百分比")
    model_version: str = Field(..., description="模型版本")
    is_big_tipper: bool = Field(..., description="是否为大方的乘客（小费>20%）")


def find_latest_model():
    """查找最新的训练模型"""
    base_path = Path("/app/tfx_pipeline/pipelines/chicago_taxi_simple/Trainer/model")
    
    # 如果在本地运行，使用相对路径
    if not base_path.exists():
        base_path = Path("tfx_pipeline/pipelines/chicago_taxi_simple/Trainer/model")
    
    if not base_path.exists():
        logger.error(f"Model base path not found: {base_path}")
        return None
    
    # 查找所有模型目录
    model_dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.isdigit()]
    
    if not model_dirs:
        logger.error("No model directories found")
        return None
    
    # 获取最新的模型（按目录名数字排序）
    latest_model_dir = max(model_dirs, key=lambda x: int(x.name))
    model_path = latest_model_dir / "serving_model_dir"
    
    if model_path.exists():
        logger.info(f"Found latest model at: {model_path}")
        return str(model_path)
    
    return None


def load_model():
    """加载TFX训练的模型"""
    global MODEL, MODEL_PATH
    
    try:
        MODEL_PATH = find_latest_model()
        
        if MODEL_PATH is None:
            logger.warning("No trained model found, using fallback prediction")
            return False
        
        logger.info(f"Loading TFX model from: {MODEL_PATH}")
        MODEL = tf.saved_model.load(MODEL_PATH)
        logger.info("TFX model loaded successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        MODEL = None
        return False


def predict_with_tfx_model(trip: TaxiTripRequest) -> float:
    """使用TFX模型进行预测"""
    try:
        # 准备输入数据 - 创建 tf.Example
        feature = {
            'trip_miles': tf.train.Feature(float_list=tf.train.FloatList(value=[trip.trip_miles])),
            'trip_seconds': tf.train.Feature(float_list=tf.train.FloatList(value=[float(trip.trip_seconds)])),
            'fare': tf.train.Feature(float_list=tf.train.FloatList(value=[trip.fare])),
            'pickup_latitude': tf.train.Feature(float_list=tf.train.FloatList(value=[trip.pickup_latitude])),
            'pickup_longitude': tf.train.Feature(float_list=tf.train.FloatList(value=[trip.pickup_longitude])),
            'dropoff_latitude': tf.train.Feature(float_list=tf.train.FloatList(value=[trip.dropoff_latitude])),
            'dropoff_longitude': tf.train.Feature(float_list=tf.train.FloatList(value=[trip.dropoff_longitude])),
            'trip_start_hour': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.pickup_hour])),
            'trip_start_day': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.trip_start_day])),
            'trip_start_month': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.trip_start_month])),
            'pickup_community_area': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.pickup_community_area])),
            'dropoff_community_area': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.dropoff_community_area])),
            'payment_type': tf.train.Feature(bytes_list=tf.train.BytesList(value=[trip.payment_type.encode('utf-8')])),
            'company': tf.train.Feature(bytes_list=tf.train.BytesList(value=[trip.company.encode('utf-8')])),
            'pickup_census_tract': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.pickup_census_tract])),
            'dropoff_census_tract': tf.train.Feature(int64_list=tf.train.Int64List(value=[trip.dropoff_census_tract])),
            'tips': tf.train.Feature(float_list=tf.train.FloatList(value=[0.0])),  # Placeholder
        }
        
        example = tf.train.Example(features=tf.train.Features(feature=feature))
        serialized_example = example.SerializeToString()
        
        # 进行预测
        predictions = MODEL.signatures['serving_default'](
            examples=tf.constant([serialized_example])
        )
        
        # 提取预测结果（模型输出是概率，表示是否为大方的乘客）
        probability = float(predictions['output_0'][0][0])
        
        # 如果概率 > 0.5，预测小费 > 20% 的车费
        # 否则预测小费约为 15% 的车费
        if probability > 0.5:
            predicted_tip = trip.fare * 0.22  # 22% for big tippers
        else:
            predicted_tip = trip.fare * 0.15  # 15% for regular tippers
        
        return predicted_tip
        
    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        raise


def predict_with_fallback(trip: TaxiTripRequest) -> float:
    """回退预测方法（当模型不可用时）"""
    base_tip_rate = 0.15
    
    # 支付方式调整
    payment_multiplier = {
        "Credit Card": 1.5,
        "Cash": 0.5,
        "Mobile": 1.3,
        "Prcard": 1.2
    }.get(trip.payment_type, 1.0)
    
    # 时间段调整
    hour = trip.pickup_hour
    if 17 <= hour <= 20:  # 晚高峰
        time_multiplier = 1.3
    elif 0 <= hour <= 5:  # 深夜
        time_multiplier = 1.4
    elif 6 <= hour <= 9:  # 早高峰
        time_multiplier = 1.2
    else:
        time_multiplier = 1.0
    
    # 距离调整
    if trip.trip_miles > 10:
        distance_multiplier = 1.1
    elif trip.trip_miles < 2:
        distance_multiplier = 0.9
    else:
        distance_multiplier = 1.0
    
    # 计算最终小费
    tip = trip.fare * base_tip_rate * payment_multiplier * time_multiplier * distance_multiplier
    
    return round(tip, 2)


@app.on_event("startup")
async def startup_event():
    """应用启动时加载模型"""
    logger.info("Starting Taxi Tip Prediction API with TFX Model...")
    success = load_model()
    if success:
        logger.info("✅ TFX Model loaded successfully!")
    else:
        logger.warning("⚠️ TFX Model not available, using fallback prediction")


@app.get("/")
async def root():
    """根路径"""
    model_status = "TFX Model Loaded" if MODEL is not None else "Fallback Mode"
    return {
        "message": "Chicago Taxi Tip Prediction API (TFX)",
        "version": "2.0.0",
        "model_status": model_status,
        "model_path": MODEL_PATH
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "model_path": MODEL_PATH
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(trip: TaxiTripRequest):
    """
    预测单次行程的小费
    """
    try:
        # 使用TFX模型或回退方法
        if MODEL is not None:
            predicted_tip = predict_with_tfx_model(trip)
            model_version = "TFX v2.0"
        else:
            predicted_tip = predict_with_fallback(trip)
            model_version = "Fallback v1.0"
        
        # 计算小费百分比
        tip_percentage = (predicted_tip / trip.fare * 100) if trip.fare > 0 else 0
        
        # 判断是否为大方的乘客
        is_big_tipper = tip_percentage > 20
        
        logger.info(f"Prediction: ${predicted_tip:.2f} ({tip_percentage:.1f}%) - Model: {model_version}")
        
        return PredictionResponse(
            predicted_tip=round(predicted_tip, 2),
            tip_percentage=round(tip_percentage, 2),
            model_version=model_version,
            is_big_tipper=is_big_tipper
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch_predict")
async def batch_predict(trips: List[TaxiTripRequest]):
    """
    批量预测多次行程的小费
    """
    try:
        predictions = []
        
        for trip in trips:
            if MODEL is not None:
                predicted_tip = predict_with_tfx_model(trip)
                model_version = "TFX v2.0"
            else:
                predicted_tip = predict_with_fallback(trip)
                model_version = "Fallback v1.0"
            
            tip_percentage = (predicted_tip / trip.fare * 100) if trip.fare > 0 else 0
            is_big_tipper = tip_percentage > 20
            
            predictions.append({
                "predicted_tip": round(predicted_tip, 2),
                "tip_percentage": round(tip_percentage, 2),
                "model_version": model_version,
                "is_big_tipper": is_big_tipper
            })
        
        return {"predictions": predictions, "count": len(predictions)}
        
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """获取API指标"""
    return {
        "model_loaded": MODEL is not None,
        "model_path": MODEL_PATH,
        "api_version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
