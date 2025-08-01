#!/usr/bin/env python3
"""
FastAPI Feast 特征存储路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from taxi_prediction_endpoints import (
    taxi_prediction_service, 
    feast_feature_service,
    TaxiPredictionService,
    FeastFeatureService
)

# 创建路由器
router = APIRouter(prefix="/feast", tags=["Feast特征存储"])

logger = logging.getLogger(__name__)


# Pydantic 模型
class OnlineFeaturesRequest(BaseModel):
    """在线特征请求模型"""
    entity_ids: List[str]
    feature_service: str = "model_inference_v1"


class HistoricalFeaturesRequest(BaseModel):
    """历史特征请求模型"""
    entity_data: Dict[str, Any]
    features: List[str]


# Feast 特征存储路由
@router.get("/info", summary="获取特征存储信息")
async def get_feature_store_info():
    """获取 Feast 特征存储基本信息"""
    try:
        info = await feast_feature_service.get_feature_store_info()
        return {
            "status": "success",
            "data": info,
            "message": "特征存储信息获取成功"
        }
    except Exception as e:
        logger.error(f"获取特征存储信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征存储信息失败: {str(e)}")


@router.get("/feature-views", summary="获取所有特征视图")
async def list_feature_views():
    """列出所有可用的特征视图"""
    try:
        feature_views = await feast_feature_service.get_feature_views()
        return {
            "status": "success",
            "data": feature_views,
            "count": len(feature_views),
            "message": f"成功获取 {len(feature_views)} 个特征视图"
        }
    except Exception as e:
        logger.error(f"获取特征视图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征视图失败: {str(e)}")


@router.get("/feature-services", summary="获取所有特征服务")
async def list_feature_services():
    """列出所有可用的特征服务"""
    try:
        feature_services = await feast_feature_service.get_feature_services()
        return {
            "status": "success",
            "data": feature_services,
            "count": len(feature_services),
            "message": f"成功获取 {len(feature_services)} 个特征服务"
        }
    except Exception as e:
        logger.error(f"获取特征服务失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征服务失败: {str(e)}")


@router.post("/online-features", summary="获取在线特征")
async def get_online_features(request: OnlineFeaturesRequest):
    """
    获取指定实体的在线特征
    
    用于实时推理场景
    """
    try:
        features = await feast_feature_service.get_online_features(
            entity_ids=request.entity_ids,
            feature_service=request.feature_service
        )
        
        return {
            "status": "success",
            "data": features,
            "entity_count": len(request.entity_ids),
            "feature_service": request.feature_service,
            "message": "在线特征获取成功"
        }
    except Exception as e:
        logger.error(f"获取在线特征失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取在线特征失败: {str(e)}")


@router.post("/historical-features", summary="获取历史特征")
async def get_historical_features(request: HistoricalFeaturesRequest):
    """
    获取历史特征数据
    
    用于模型训练和批量推理场景
    """
    try:
        features = await feast_feature_service.get_historical_features(
            entity_df_dict=request.entity_data,
            features=request.features
        )
        
        return {
            "status": "success",
            "data": features,
            "requested_features": request.features,
            "message": "历史特征获取成功"
        }
    except Exception as e:
        logger.error(f"获取历史特征失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史特征失败: {str(e)}")


@router.get("/features/trip/{trip_id}", summary="获取单个行程特征")
async def get_trip_features(
    trip_id: str,
    feature_service: str = Query("model_inference_v1", description="特征服务名称")
):
    """获取指定行程ID的特征"""
    try:
        features = await feast_feature_service.get_online_features(
            entity_ids=[trip_id],
            feature_service=feature_service
        )
        
        trip_features = features.get("features", {}).get(trip_id, {})
        
        return {
            "status": "success",
            "data": {
                "trip_id": trip_id,
                "features": trip_features,
                "feature_service": feature_service
            },
            "message": f"行程 {trip_id} 特征获取成功"
        }
    except Exception as e:
        logger.error(f"获取行程特征失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取行程特征失败: {str(e)}")


# 出租车预测路由
taxi_router = APIRouter(prefix="/taxi", tags=["出租车费用预测"])


@taxi_router.post("/predict", summary="单次费用预测")
async def predict_taxi_fare(request, use_feast: bool = Query(True, description="是否使用Feast特征")):
    """
    单次出租车费用预测
    
    支持使用 Feast 特征存储增强预测准确性
    """
    try:
        result = await taxi_prediction_service.predict_single(request, use_feast_features=use_feast)
        
        return {
            "status": "success",
            "data": result,
            "feast_enabled": use_feast,
            "message": "费用预测成功"
        }
    except Exception as e:
        logger.error(f"费用预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"费用预测失败: {str(e)}")


@taxi_router.post("/predict/batch", summary="批量费用预测")
async def predict_taxi_fare_batch(request, use_feast: bool = Query(True, description="是否使用Feast特征")):
    """
    批量出租车费用预测
    
    支持批量处理多个行程的费用预测
    """
    try:
        results = await taxi_prediction_service.predict_batch(
            requests=request.trips,
            use_feast_features=use_feast
        )
        
        return {
            "status": "success",
            "data": results,
            "batch_size": len(request.trips),
            "feast_enabled": use_feast,
            "message": f"批量预测完成，处理了 {len(results)} 个请求"
        }
    except Exception as e:
        logger.error(f"批量费用预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量费用预测失败: {str(e)}")


@taxi_router.get("/predict/demo", summary="演示预测")
async def demo_prediction():
    """
    演示出租车费用预测
    
    使用预设的示例数据进行预测演示
    """
    try:
        # 创建演示数据
        from taxi_prediction_endpoints import TaxiPredictionRequest
        
        demo_request = type('DemoRequest', (), {
            'trip_miles': 3.5,
            'trip_seconds': 900,
            'pickup_latitude': 41.88,
            'pickup_longitude': -87.63,
            'dropoff_latitude': 41.89,
            'dropoff_longitude': -87.62,
            'pickup_hour': 14,
            'pickup_day_of_week': 1,
            'pickup_month': 6,
            'passenger_count': 2,
            'payment_type': 'Credit Card',
            'company': 'Flash Cab'
        })()
        
        result = await taxi_prediction_service.predict_single(demo_request, use_feast_features=True)
        
        return {
            "status": "success",
            "data": result,
            "demo_input": {
                "trip_miles": 3.5,
                "trip_seconds": 900,
                "pickup_location": "芝加哥市中心",
                "dropoff_location": "芝加哥北区",
                "pickup_time": "下午2点",
                "passenger_count": 2,
                "payment_type": "信用卡",
                "company": "Flash Cab"
            },
            "message": "演示预测完成"
        }
    except Exception as e:
        logger.error(f"演示预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"演示预测失败: {str(e)}")


# 监控和统计路由
@router.get("/stats", summary="获取特征存储统计")
async def get_feature_store_stats():
    """获取特征存储使用统计"""
    try:
        # 获取基本信息
        info = await feast_feature_service.get_feature_store_info()
        feature_views = await feast_feature_service.get_feature_views()
        feature_services = await feast_feature_service.get_feature_services()
        
        stats = {
            "feature_store_info": info,
            "feature_views_count": len(feature_views),
            "feature_services_count": len(feature_services),
            "feature_views": [fv.get("name", "unknown") for fv in feature_views],
            "feature_services": [fs.get("name", "unknown") for fs in feature_services],
            "status": "healthy" if info.get("store_connected", False) else "degraded"
        }
        
        return {
            "status": "success",
            "data": stats,
            "message": "特征存储统计获取成功"
        }
    except Exception as e:
        logger.error(f"获取特征存储统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取特征存储统计失败: {str(e)}")


# 导出路由器
feast_router = router
__all__ = ["feast_router", "taxi_router"]
