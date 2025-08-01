#!/usr/bin/env python3
"""
MLMD (ML Metadata) 数据血缘追踪组件
实现端到端的数据和模型血缘关系监控
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import ml_metadata as mlmd
    from ml_metadata.proto import metadata_store_pb2
    from ml_metadata.metadata_store import metadata_store
    MLMD_AVAILABLE = True
except ImportError:
    MLMD_AVAILABLE = False
    logging.warning("ML Metadata 未安装，使用模拟模式")

import pandas as pd
import numpy as np


@dataclass
class LineageNode:
    """血缘节点数据结构"""
    id: str
    name: str
    type: str  # 'data', 'model', 'execution', 'artifact'
    properties: Dict[str, Any]
    timestamp: str
    parent_ids: List[str]
    child_ids: List[str]


@dataclass
class LineageEdge:
    """血缘边数据结构"""
    source_id: str
    target_id: str
    relationship_type: str  # 'input', 'output', 'derived_from', 'trained_on'
    properties: Dict[str, Any]
    timestamp: str


class MLMDLineageTracker:
    """MLMD 数据血缘追踪器"""
    
    def __init__(self, 
                 metadata_db_path: str = "mlmd/metadata.db",
                 enable_mock_mode: bool = False):
        """
        初始化 MLMD 血缘追踪器
        
        Args:
            metadata_db_path: MLMD 数据库路径
            enable_mock_mode: 是否启用模拟模式
        """
        self.metadata_db_path = metadata_db_path
        self.enable_mock_mode = enable_mock_mode or not MLMD_AVAILABLE
        self.logger = logging.getLogger(__name__)
        
        # 创建数据库目录
        os.makedirs(os.path.dirname(metadata_db_path), exist_ok=True)
        
        if not self.enable_mock_mode:
            self._initialize_mlmd_store()
        else:
            self._initialize_mock_store()
    
    def _initialize_mlmd_store(self):
        """初始化 MLMD 存储"""
        try:
            # 配置 SQLite 连接
            connection_config = metadata_store_pb2.ConnectionConfig()
            connection_config.sqlite.filename_uri = f"sqlite:///{self.metadata_db_path}"
            connection_config.sqlite.connection_mode = 3  # READWRITE_OPENCREATE
            
            # 创建 metadata store
            self.store = metadata_store.MetadataStore(connection_config)
            
            # 注册标准类型
            self._register_standard_types()
            
            self.logger.info(f"MLMD 存储初始化成功: {self.metadata_db_path}")
            
        except Exception as e:
            self.logger.error(f"MLMD 存储初始化失败: {e}")
            self.enable_mock_mode = True
            self._initialize_mock_store()
    
    def _initialize_mock_store(self):
        """初始化模拟存储"""
        self.mock_artifacts = {}
        self.mock_executions = {}
        self.mock_contexts = {}
        self.mock_events = []
        self.logger.info("使用模拟模式进行 MLMD 血缘追踪")
    
    def _register_standard_types(self):
        """注册标准的 MLMD 类型"""
        if self.enable_mock_mode:
            return
        
        try:
            # 注册 Artifact 类型
            artifact_types = [
                ("Dataset", {"format": metadata_store_pb2.STRING}),
                ("Model", {"framework": metadata_store_pb2.STRING, "version": metadata_store_pb2.STRING}),
                ("Metrics", {"accuracy": metadata_store_pb2.DOUBLE, "loss": metadata_store_pb2.DOUBLE}),
                ("Schema", {"version": metadata_store_pb2.STRING}),
                ("Statistics", {"num_examples": metadata_store_pb2.INT}),
            ]
            
            for type_name, properties in artifact_types:
                artifact_type = metadata_store_pb2.ArtifactType()
                artifact_type.name = type_name
                for prop_name, prop_type in properties.items():
                    artifact_type.properties[prop_name] = prop_type
                self.store.put_artifact_type(artifact_type)
            
            # 注册 Execution 类型
            execution_types = [
                ("DataIngestion", {"source": metadata_store_pb2.STRING}),
                ("DataValidation", {"status": metadata_store_pb2.STRING}),
                ("DataTransformation", {"transform_graph": metadata_store_pb2.STRING}),
                ("Training", {"algorithm": metadata_store_pb2.STRING, "hyperparameters": metadata_store_pb2.STRING}),
                ("Evaluation", {"metrics": metadata_store_pb2.STRING}),
                ("ModelDeployment", {"serving_platform": metadata_store_pb2.STRING}),
            ]
            
            for type_name, properties in execution_types:
                execution_type = metadata_store_pb2.ExecutionType()
                execution_type.name = type_name
                for prop_name, prop_type in properties.items():
                    execution_type.properties[prop_name] = prop_type
                self.store.put_execution_type(execution_type)
            
            # 注册 Context 类型
            context_types = [
                ("Pipeline", {"version": metadata_store_pb2.STRING}),
                ("Experiment", {"name": metadata_store_pb2.STRING}),
            ]
            
            for type_name, properties in context_types:
                context_type = metadata_store_pb2.ContextType()
                context_type.name = type_name
                for prop_name, prop_type in properties.items():
                    context_type.properties[prop_name] = prop_type
                self.store.put_context_type(context_type)
                
        except Exception as e:
            self.logger.error(f"注册 MLMD 类型失败: {e}")
    
    def track_data_ingestion(self, 
                           dataset_name: str,
                           dataset_uri: str,
                           source: str,
                           properties: Dict[str, Any] = None) -> str:
        """
        追踪数据摄取过程
        
        Args:
            dataset_name: 数据集名称
            dataset_uri: 数据集 URI
            source: 数据源
            properties: 附加属性
            
        Returns:
            execution_id: 执行 ID
        """
        if self.enable_mock_mode:
            return self._mock_track_data_ingestion(dataset_name, dataset_uri, source, properties)
        
        try:
            # 创建数据集 Artifact
            dataset_artifact = metadata_store_pb2.Artifact()
            dataset_artifact.type_id = self._get_artifact_type_id("Dataset")
            dataset_artifact.name = dataset_name
            dataset_artifact.uri = dataset_uri
            if properties:
                for key, value in properties.items():
                    if isinstance(value, str):
                        dataset_artifact.properties[key].string_value = value
                    elif isinstance(value, (int, float)):
                        dataset_artifact.properties[key].double_value = float(value)
            
            artifact_id = self.store.put_artifacts([dataset_artifact])[0]
            
            # 创建数据摄取 Execution
            ingestion_execution = metadata_store_pb2.Execution()
            ingestion_execution.type_id = self._get_execution_type_id("DataIngestion")
            ingestion_execution.name = f"ingestion_{dataset_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ingestion_execution.properties["source"].string_value = source
            
            execution_id = self.store.put_executions([ingestion_execution])[0]
            
            # 创建 Event (输出关系)
            event = metadata_store_pb2.Event()
            event.artifact_id = artifact_id
            event.execution_id = execution_id
            event.type = metadata_store_pb2.Event.OUTPUT
            
            self.store.put_events([event])
            
            self.logger.info(f"数据摄取血缘追踪完成: {dataset_name}")
            return str(execution_id)
            
        except Exception as e:
            self.logger.error(f"数据摄取血缘追踪失败: {e}")
            return None
    
    def track_model_training(self,
                           model_name: str,
                           model_uri: str,
                           training_data_id: str,
                           algorithm: str,
                           hyperparameters: Dict[str, Any],
                           metrics: Dict[str, float]) -> str:
        """
        追踪模型训练过程
        
        Args:
            model_name: 模型名称
            model_uri: 模型 URI
            training_data_id: 训练数据 ID
            algorithm: 算法名称
            hyperparameters: 超参数
            metrics: 训练指标
            
        Returns:
            execution_id: 执行 ID
        """
        if self.enable_mock_mode:
            return self._mock_track_model_training(
                model_name, model_uri, training_data_id, algorithm, hyperparameters, metrics
            )
        
        try:
            # 创建模型 Artifact
            model_artifact = metadata_store_pb2.Artifact()
            model_artifact.type_id = self._get_artifact_type_id("Model")
            model_artifact.name = model_name
            model_artifact.uri = model_uri
            model_artifact.properties["framework"].string_value = "TensorFlow"
            model_artifact.properties["version"].string_value = "1.0"
            
            model_id = self.store.put_artifacts([model_artifact])[0]
            
            # 创建指标 Artifact
            metrics_artifact = metadata_store_pb2.Artifact()
            metrics_artifact.type_id = self._get_artifact_type_id("Metrics")
            metrics_artifact.name = f"{model_name}_metrics"
            for metric_name, metric_value in metrics.items():
                metrics_artifact.properties[metric_name].double_value = metric_value
            
            metrics_id = self.store.put_artifacts([metrics_artifact])[0]
            
            # 创建训练 Execution
            training_execution = metadata_store_pb2.Execution()
            training_execution.type_id = self._get_execution_type_id("Training")
            training_execution.name = f"training_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            training_execution.properties["algorithm"].string_value = algorithm
            training_execution.properties["hyperparameters"].string_value = json.dumps(hyperparameters)
            
            execution_id = self.store.put_executions([training_execution])[0]
            
            # 创建 Events
            events = []
            
            # 输入事件 (训练数据)
            input_event = metadata_store_pb2.Event()
            input_event.artifact_id = int(training_data_id)
            input_event.execution_id = execution_id
            input_event.type = metadata_store_pb2.Event.INPUT
            events.append(input_event)
            
            # 输出事件 (模型)
            model_output_event = metadata_store_pb2.Event()
            model_output_event.artifact_id = model_id
            model_output_event.execution_id = execution_id
            model_output_event.type = metadata_store_pb2.Event.OUTPUT
            events.append(model_output_event)
            
            # 输出事件 (指标)
            metrics_output_event = metadata_store_pb2.Event()
            metrics_output_event.artifact_id = metrics_id
            metrics_output_event.execution_id = execution_id
            metrics_output_event.type = metadata_store_pb2.Event.OUTPUT
            events.append(metrics_output_event)
            
            self.store.put_events(events)
            
            self.logger.info(f"模型训练血缘追踪完成: {model_name}")
            return str(execution_id)
            
        except Exception as e:
            self.logger.error(f"模型训练血缘追踪失败: {e}")
            return None
    
    def get_lineage_graph(self, artifact_id: str = None, execution_id: str = None) -> Dict[str, Any]:
        """
        获取血缘关系图
        
        Args:
            artifact_id: Artifact ID (可选)
            execution_id: Execution ID (可选)
            
        Returns:
            血缘关系图数据
        """
        if self.enable_mock_mode:
            return self._mock_get_lineage_graph(artifact_id, execution_id)
        
        try:
            nodes = []
            edges = []
            
            # 获取所有 Artifacts
            artifacts = self.store.get_artifacts()
            for artifact in artifacts:
                node = {
                    "id": f"artifact_{artifact.id}",
                    "name": artifact.name,
                    "type": "artifact",
                    "subtype": self._get_artifact_type_name(artifact.type_id),
                    "uri": artifact.uri,
                    "properties": self._extract_properties(artifact.properties),
                    "timestamp": datetime.fromtimestamp(artifact.create_time_since_epoch / 1000).isoformat()
                }
                nodes.append(node)
            
            # 获取所有 Executions
            executions = self.store.get_executions()
            for execution in executions:
                node = {
                    "id": f"execution_{execution.id}",
                    "name": execution.name,
                    "type": "execution",
                    "subtype": self._get_execution_type_name(execution.type_id),
                    "properties": self._extract_properties(execution.properties),
                    "timestamp": datetime.fromtimestamp(execution.create_time_since_epoch / 1000).isoformat()
                }
                nodes.append(node)
            
            # 获取所有 Events (构建边)
            events = self.store.get_events()
            for event in events:
                if event.type == metadata_store_pb2.Event.INPUT:
                    edge = {
                        "source": f"artifact_{event.artifact_id}",
                        "target": f"execution_{event.execution_id}",
                        "type": "input",
                        "timestamp": datetime.fromtimestamp(event.milliseconds_since_epoch).isoformat()
                    }
                elif event.type == metadata_store_pb2.Event.OUTPUT:
                    edge = {
                        "source": f"execution_{event.execution_id}",
                        "target": f"artifact_{event.artifact_id}",
                        "type": "output",
                        "timestamp": datetime.fromtimestamp(event.milliseconds_since_epoch).isoformat()
                    }
                edges.append(edge)
            
            lineage_graph = {
                "nodes": nodes,
                "edges": edges,
                "metadata": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            return lineage_graph
            
        except Exception as e:
            self.logger.error(f"获取血缘关系图失败: {e}")
            return {"nodes": [], "edges": [], "error": str(e)}
    
    def export_lineage_report(self, output_path: str = "mlmd/lineage_report.json"):
        """
        导出血缘关系报告
        
        Args:
            output_path: 输出文件路径
        """
        try:
            lineage_graph = self.get_lineage_graph()
            
            # 添加统计信息
            stats = self._generate_lineage_stats(lineage_graph)
            lineage_graph["statistics"] = stats
            
            # 保存到文件
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(lineage_graph, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"血缘关系报告导出成功: {output_path}")
            
        except Exception as e:
            self.logger.error(f"导出血缘关系报告失败: {e}")
    
    def _generate_lineage_stats(self, lineage_graph: Dict[str, Any]) -> Dict[str, Any]:
        """生成血缘关系统计信息"""
        nodes = lineage_graph.get("nodes", [])
        edges = lineage_graph.get("edges", [])
        
        # 按类型统计节点
        node_types = {}
        for node in nodes:
            node_type = node.get("subtype", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # 按类型统计边
        edge_types = {}
        for edge in edges:
            edge_type = edge.get("type", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        return {
            "node_count_by_type": node_types,
            "edge_count_by_type": edge_types,
            "total_artifacts": len([n for n in nodes if n["type"] == "artifact"]),
            "total_executions": len([n for n in nodes if n["type"] == "execution"]),
            "pipeline_depth": self._calculate_pipeline_depth(nodes, edges),
            "last_updated": datetime.now().isoformat()
        }
    
    def _calculate_pipeline_depth(self, nodes: List[Dict], edges: List[Dict]) -> int:
        """计算管道深度"""
        # 简化的深度计算
        execution_nodes = [n for n in nodes if n["type"] == "execution"]
        return len(execution_nodes)
    
    # Mock 模式方法
    def _mock_track_data_ingestion(self, dataset_name, dataset_uri, source, properties):
        """模拟数据摄取追踪"""
        execution_id = f"mock_ingestion_{len(self.mock_executions)}"
        artifact_id = f"mock_artifact_{len(self.mock_artifacts)}"
        
        self.mock_artifacts[artifact_id] = {
            "name": dataset_name,
            "uri": dataset_uri,
            "type": "Dataset",
            "properties": properties or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.mock_executions[execution_id] = {
            "name": f"ingestion_{dataset_name}",
            "type": "DataIngestion",
            "properties": {"source": source},
            "timestamp": datetime.now().isoformat()
        }
        
        self.mock_events.append({
            "execution_id": execution_id,
            "artifact_id": artifact_id,
            "type": "output"
        })
        
        return execution_id
    
    def _mock_track_model_training(self, model_name, model_uri, training_data_id, algorithm, hyperparameters, metrics):
        """模拟模型训练追踪"""
        execution_id = f"mock_training_{len(self.mock_executions)}"
        model_id = f"mock_model_{len(self.mock_artifacts)}"
        metrics_id = f"mock_metrics_{len(self.mock_artifacts)}"
        
        self.mock_artifacts[model_id] = {
            "name": model_name,
            "uri": model_uri,
            "type": "Model",
            "properties": {"framework": "TensorFlow", "version": "1.0"},
            "timestamp": datetime.now().isoformat()
        }
        
        self.mock_artifacts[metrics_id] = {
            "name": f"{model_name}_metrics",
            "type": "Metrics",
            "properties": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        self.mock_executions[execution_id] = {
            "name": f"training_{model_name}",
            "type": "Training",
            "properties": {
                "algorithm": algorithm,
                "hyperparameters": json.dumps(hyperparameters)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 添加事件
        self.mock_events.extend([
            {"execution_id": execution_id, "artifact_id": training_data_id, "type": "input"},
            {"execution_id": execution_id, "artifact_id": model_id, "type": "output"},
            {"execution_id": execution_id, "artifact_id": metrics_id, "type": "output"}
        ])
        
        return execution_id
    
    def _mock_get_lineage_graph(self, artifact_id, execution_id):
        """模拟获取血缘关系图"""
        nodes = []
        edges = []
        
        # 添加 artifact 节点
        for aid, artifact in self.mock_artifacts.items():
            nodes.append({
                "id": aid,
                "name": artifact["name"],
                "type": "artifact",
                "subtype": artifact["type"],
                "uri": artifact.get("uri", ""),
                "properties": artifact["properties"],
                "timestamp": artifact["timestamp"]
            })
        
        # 添加 execution 节点
        for eid, execution in self.mock_executions.items():
            nodes.append({
                "id": eid,
                "name": execution["name"],
                "type": "execution",
                "subtype": execution["type"],
                "properties": execution["properties"],
                "timestamp": execution["timestamp"]
            })
        
        # 添加边
        for event in self.mock_events:
            if event["type"] == "input":
                edges.append({
                    "source": event["artifact_id"],
                    "target": event["execution_id"],
                    "type": "input",
                    "timestamp": datetime.now().isoformat()
                })
            elif event["type"] == "output":
                edges.append({
                    "source": event["execution_id"],
                    "target": event["artifact_id"],
                    "type": "output",
                    "timestamp": datetime.now().isoformat()
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "generated_at": datetime.now().isoformat(),
                "mode": "mock"
            }
        }
    
    # 辅助方法
    def _get_artifact_type_id(self, type_name: str) -> int:
        """获取 Artifact 类型 ID"""
        if self.enable_mock_mode:
            return 1
        artifact_types = self.store.get_artifact_types()
        for artifact_type in artifact_types:
            if artifact_type.name == type_name:
                return artifact_type.id
        return None
    
    def _get_execution_type_id(self, type_name: str) -> int:
        """获取 Execution 类型 ID"""
        if self.enable_mock_mode:
            return 1
        execution_types = self.store.get_execution_types()
        for execution_type in execution_types:
            if execution_type.name == type_name:
                return execution_type.id
        return None
    
    def _get_artifact_type_name(self, type_id: int) -> str:
        """获取 Artifact 类型名称"""
        if self.enable_mock_mode:
            return "MockType"
        artifact_types = self.store.get_artifact_types()
        for artifact_type in artifact_types:
            if artifact_type.id == type_id:
                return artifact_type.name
        return "Unknown"
    
    def _get_execution_type_name(self, type_id: int) -> str:
        """获取 Execution 类型名称"""
        if self.enable_mock_mode:
            return "MockExecution"
        execution_types = self.store.get_execution_types()
        for execution_type in execution_types:
            if execution_type.id == type_id:
                return execution_type.name
        return "Unknown"
    
    def _extract_properties(self, properties) -> Dict[str, Any]:
        """提取属性值"""
        if self.enable_mock_mode:
            return properties
        
        result = {}
        for key, value in properties.items():
            if value.HasField('string_value'):
                result[key] = value.string_value
            elif value.HasField('int_value'):
                result[key] = value.int_value
            elif value.HasField('double_value'):
                result[key] = value.double_value
            elif value.HasField('bool_value'):
                result[key] = value.bool_value
        return result


# 全局实例
mlmd_tracker = MLMDLineageTracker()

__all__ = ["MLMDLineageTracker", "mlmd_tracker", "LineageNode", "LineageEdge"]
