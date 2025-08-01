#!/usr/bin/env python3
"""
MLMD (ML Metadata) FastAPI 路由
提供数据血缘追踪和元数据管理 API
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
import pandas as pd

# 导入 MLMD 组件
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from components.mlmd_lineage_tracker import MLMDLineageTracker, mlmd_tracker
    MLMD_AVAILABLE = True
except ImportError:
    MLMD_AVAILABLE = False
    logging.warning("MLMD 组件未找到，使用模拟模式")

# 创建路由器
router = APIRouter(prefix="/mlmd", tags=["MLMD数据血缘"])

logger = logging.getLogger(__name__)


# Pydantic 模型
class DataIngestionRequest(BaseModel):
    """数据摄取请求模型"""
    dataset_name: str = Field(..., description="数据集名称")
    dataset_uri: str = Field(..., description="数据集 URI")
    source: str = Field(..., description="数据源")
    properties: Optional[Dict[str, Any]] = Field(None, description="附加属性")


class ModelTrainingRequest(BaseModel):
    """模型训练请求模型"""
    model_name: str = Field(..., description="模型名称")
    model_uri: str = Field(..., description="模型 URI")
    training_data_id: str = Field(..., description="训练数据 ID")
    algorithm: str = Field(..., description="算法名称")
    hyperparameters: Dict[str, Any] = Field(..., description="超参数")
    metrics: Dict[str, float] = Field(..., description="训练指标")


class LineageQueryRequest(BaseModel):
    """血缘查询请求模型"""
    artifact_id: Optional[str] = Field(None, description="Artifact ID")
    execution_id: Optional[str] = Field(None, description="Execution ID")
    depth: Optional[int] = Field(3, description="查询深度")


class MLMDStatus(BaseModel):
    """MLMD 状态模型"""
    available: bool
    mode: str
    database_path: str
    total_artifacts: int
    total_executions: int
    total_events: int
    last_updated: str


# MLMD 信息和状态路由
@router.get("/info", response_model=MLMDStatus, summary="获取 MLMD 服务信息")
async def get_mlmd_info():
    """获取 MLMD 服务基本信息和状态"""
    try:
        if not MLMD_AVAILABLE:
            return MLMDStatus(
                available=False,
                mode="unavailable",
                database_path="",
                total_artifacts=0,
                total_executions=0,
                total_events=0,
                last_updated=datetime.now().isoformat()
            )
        
        # 获取统计信息
        lineage_graph = mlmd_tracker.get_lineage_graph()
        nodes = lineage_graph.get("nodes", [])
        edges = lineage_graph.get("edges", [])
        
        artifacts_count = len([n for n in nodes if n["type"] == "artifact"])
        executions_count = len([n for n in nodes if n["type"] == "execution"])
        
        return MLMDStatus(
            available=True,
            mode="mock" if mlmd_tracker.enable_mock_mode else "production",
            database_path=mlmd_tracker.metadata_db_path,
            total_artifacts=artifacts_count,
            total_executions=executions_count,
            total_events=len(edges),
            last_updated=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"获取 MLMD 信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取 MLMD 信息失败: {str(e)}")


# 数据血缘追踪路由
@router.post("/track/data-ingestion", summary="追踪数据摄取过程")
async def track_data_ingestion(request: DataIngestionRequest):
    """追踪数据摄取过程的血缘关系"""
    try:
        if not MLMD_AVAILABLE:
            return {
                "status": "simulated",
                "execution_id": f"mock_ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "message": "MLMD 不可用，使用模拟模式"
            }
        
        execution_id = mlmd_tracker.track_data_ingestion(
            dataset_name=request.dataset_name,
            dataset_uri=request.dataset_uri,
            source=request.source,
            properties=request.properties
        )
        
        if execution_id:
            return {
                "status": "success",
                "execution_id": execution_id,
                "message": f"数据摄取血缘追踪成功: {request.dataset_name}"
            }
        else:
            raise HTTPException(status_code=500, detail="数据摄取血缘追踪失败")
            
    except Exception as e:
        logger.error(f"追踪数据摄取失败: {e}")
        raise HTTPException(status_code=500, detail=f"追踪数据摄取失败: {str(e)}")


@router.post("/track/model-training", summary="追踪模型训练过程")
async def track_model_training(request: ModelTrainingRequest):
    """追踪模型训练过程的血缘关系"""
    try:
        if not MLMD_AVAILABLE:
            return {
                "status": "simulated",
                "execution_id": f"mock_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "message": "MLMD 不可用，使用模拟模式"
            }
        
        execution_id = mlmd_tracker.track_model_training(
            model_name=request.model_name,
            model_uri=request.model_uri,
            training_data_id=request.training_data_id,
            algorithm=request.algorithm,
            hyperparameters=request.hyperparameters,
            metrics=request.metrics
        )
        
        if execution_id:
            return {
                "status": "success",
                "execution_id": execution_id,
                "message": f"模型训练血缘追踪成功: {request.model_name}"
            }
        else:
            raise HTTPException(status_code=500, detail="模型训练血缘追踪失败")
            
    except Exception as e:
        logger.error(f"追踪模型训练失败: {e}")
        raise HTTPException(status_code=500, detail=f"追踪模型训练失败: {str(e)}")


# 血缘关系查询路由
@router.get("/lineage/graph", summary="获取完整血缘关系图")
async def get_lineage_graph(
    artifact_id: Optional[str] = Query(None, description="Artifact ID"),
    execution_id: Optional[str] = Query(None, description="Execution ID")
):
    """获取数据和模型的血缘关系图"""
    try:
        if not MLMD_AVAILABLE:
            # 返回模拟数据
            return {
                "nodes": [
                    {
                        "id": "mock_dataset_1",
                        "name": "chicago_taxi_data",
                        "type": "artifact",
                        "subtype": "Dataset",
                        "properties": {"format": "csv", "size": "1GB"},
                        "timestamp": "2024-01-01T10:00:00Z"
                    },
                    {
                        "id": "mock_execution_1",
                        "name": "data_ingestion",
                        "type": "execution",
                        "subtype": "DataIngestion",
                        "properties": {"source": "taxi_api"},
                        "timestamp": "2024-01-01T10:05:00Z"
                    },
                    {
                        "id": "mock_model_1",
                        "name": "taxi_fare_predictor",
                        "type": "artifact",
                        "subtype": "Model",
                        "properties": {"framework": "TensorFlow", "version": "1.0"},
                        "timestamp": "2024-01-01T11:00:00Z"
                    }
                ],
                "edges": [
                    {
                        "source": "mock_dataset_1",
                        "target": "mock_execution_1",
                        "type": "input",
                        "timestamp": "2024-01-01T10:05:00Z"
                    },
                    {
                        "source": "mock_execution_1",
                        "target": "mock_model_1",
                        "type": "output",
                        "timestamp": "2024-01-01T11:00:00Z"
                    }
                ],
                "metadata": {
                    "total_nodes": 3,
                    "total_edges": 2,
                    "generated_at": datetime.now().isoformat(),
                    "mode": "mock"
                }
            }
        
        lineage_graph = mlmd_tracker.get_lineage_graph(artifact_id, execution_id)
        return lineage_graph
        
    except Exception as e:
        logger.error(f"获取血缘关系图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取血缘关系图失败: {str(e)}")


@router.get("/lineage/artifacts", summary="获取所有 Artifacts")
async def get_artifacts():
    """获取所有 Artifacts 列表"""
    try:
        lineage_graph = mlmd_tracker.get_lineage_graph()
        artifacts = [node for node in lineage_graph.get("nodes", []) if node["type"] == "artifact"]
        
        return {
            "artifacts": artifacts,
            "total_count": len(artifacts),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取 Artifacts 失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取 Artifacts 失败: {str(e)}")


@router.get("/lineage/executions", summary="获取所有 Executions")
async def get_executions():
    """获取所有 Executions 列表"""
    try:
        lineage_graph = mlmd_tracker.get_lineage_graph()
        executions = [node for node in lineage_graph.get("nodes", []) if node["type"] == "execution"]
        
        return {
            "executions": executions,
            "total_count": len(executions),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取 Executions 失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取 Executions 失败: {str(e)}")


# 血缘分析路由
@router.get("/analysis/pipeline-depth", summary="分析管道深度")
async def analyze_pipeline_depth():
    """分析 ML 管道的深度和复杂性"""
    try:
        lineage_graph = mlmd_tracker.get_lineage_graph()
        nodes = lineage_graph.get("nodes", [])
        edges = lineage_graph.get("edges", [])
        
        # 计算管道深度
        executions = [n for n in nodes if n["type"] == "execution"]
        artifacts = [n for n in nodes if n["type"] == "artifact"]
        
        # 按类型分组
        execution_types = {}
        artifact_types = {}
        
        for execution in executions:
            exec_type = execution.get("subtype", "unknown")
            execution_types[exec_type] = execution_types.get(exec_type, 0) + 1
        
        for artifact in artifacts:
            art_type = artifact.get("subtype", "unknown")
            artifact_types[art_type] = artifact_types.get(art_type, 0) + 1
        
        return {
            "pipeline_depth": len(executions),
            "total_artifacts": len(artifacts),
            "execution_types": execution_types,
            "artifact_types": artifact_types,
            "complexity_score": len(edges) / max(len(nodes), 1),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"分析管道深度失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析管道深度失败: {str(e)}")


@router.get("/analysis/data-flow", summary="分析数据流路径")
async def analyze_data_flow():
    """分析数据在管道中的流动路径"""
    try:
        lineage_graph = mlmd_tracker.get_lineage_graph()
        nodes = lineage_graph.get("nodes", [])
        edges = lineage_graph.get("edges", [])
        
        # 构建数据流路径
        data_flows = []
        
        # 找到所有数据集 artifacts
        datasets = [n for n in nodes if n["type"] == "artifact" and n.get("subtype") == "Dataset"]
        
        for dataset in datasets:
            flow_path = [dataset["name"]]
            current_id = dataset["id"]
            
            # 跟踪数据流
            visited = set()
            while current_id not in visited:
                visited.add(current_id)
                
                # 找到以当前节点为源的边
                next_edges = [e for e in edges if e["source"] == current_id]
                if not next_edges:
                    break
                
                # 选择第一个边（简化处理）
                next_edge = next_edges[0]
                target_id = next_edge["target"]
                
                # 找到目标节点
                target_node = next((n for n in nodes if n["id"] == target_id), None)
                if target_node:
                    flow_path.append(target_node["name"])
                    current_id = target_id
                else:
                    break
            
            data_flows.append({
                "source_dataset": dataset["name"],
                "flow_path": flow_path,
                "path_length": len(flow_path)
            })
        
        return {
            "data_flows": data_flows,
            "total_flows": len(data_flows),
            "average_path_length": sum(flow["path_length"] for flow in data_flows) / max(len(data_flows), 1),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"分析数据流失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析数据流失败: {str(e)}")


# 报告生成路由
@router.post("/reports/export", summary="导出血缘关系报告")
async def export_lineage_report(background_tasks: BackgroundTasks):
    """导出完整的血缘关系报告"""
    try:
        if not MLMD_AVAILABLE:
            return {
                "status": "simulated",
                "message": "MLMD 不可用，无法生成真实报告",
                "report_path": "mock_report.json"
            }
        
        # 在后台生成报告
        background_tasks.add_task(mlmd_tracker.export_lineage_report)
        
        return {
            "status": "generating",
            "message": "血缘关系报告正在后台生成",
            "report_path": "mlmd/lineage_report.json",
            "estimated_completion": "30 seconds"
        }
        
    except Exception as e:
        logger.error(f"导出血缘关系报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出血缘关系报告失败: {str(e)}")


# 测试和演示路由
@router.post("/demo/create-sample-lineage", summary="创建示例血缘数据")
async def create_sample_lineage():
    """创建示例血缘关系数据用于演示"""
    try:
        # 创建示例数据摄取
        ingestion_id = mlmd_tracker.track_data_ingestion(
            dataset_name="chicago_taxi_demo",
            dataset_uri="gs://taxi-data/demo.csv",
            source="chicago_taxi_api",
            properties={"format": "csv", "size_mb": 1024, "records": 50000}
        )
        
        # 创建示例模型训练
        training_id = mlmd_tracker.track_model_training(
            model_name="taxi_fare_predictor_demo",
            model_uri="gs://models/taxi_fare_v1.0",
            training_data_id=ingestion_id,
            algorithm="RandomForest",
            hyperparameters={
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42
            },
            metrics={
                "rmse": 2.5,
                "mae": 1.8,
                "r2_score": 0.85
            }
        )
        
        return {
            "status": "success",
            "message": "示例血缘关系数据创建成功",
            "ingestion_execution_id": ingestion_id,
            "training_execution_id": training_id,
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"创建示例血缘数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建示例血缘数据失败: {str(e)}")


# 导出路由器
mlmd_router = router
__all__ = ["mlmd_router"]
