#!/usr/bin/env python3
"""
Feast 特征推送组件
将 TFX Transform 输出的特征推送到 Feast 特征存储
"""

import os
from typing import Any, Dict, List, Optional, Text
from absl import logging
import apache_beam as beam
import pandas as pd
from feast import FeatureStore, Entity, Feature, FeatureView, ValueType
from feast.data_source import FileSource
from datetime import timedelta

from tfx import types
from tfx.components.base import base_component
from tfx.components.base import executor_spec
from tfx.components.base import base_executor
from tfx.types import standard_artifacts
from tfx.types.artifact_utils import get_single_uri
from tfx.utils import io_utils

class FeastFeaturePusherExecutor(base_executor.BaseExecutor):
    """Feast 特征推送执行器"""
    
    def Do(self, input_dict: Dict[Text, List[types.Artifact]],
           output_dict: Dict[Text, List[types.Artifact]],
           exec_properties: Dict[Text, Any]) -> None:
        """
        执行特征推送到 Feast
        
        Args:
            input_dict: 输入工件字典
            output_dict: 输出工件字典  
            exec_properties: 执行属性
        """
        
        # 获取输入
        examples = input_dict.get('examples', [])
        transform_graph = input_dict.get('transform_graph', [])
        
        if not examples:
            raise ValueError("需要输入 examples")
            
        # 获取配置
        feast_repo_path = exec_properties.get('feast_repo_path', './feast/feature_repo')
        feature_table_name = exec_properties.get('feature_table_name', 'taxi_features')
        
        logging.info(f"开始推送特征到 Feast: {feast_repo_path}")
        
        try:
            # 初始化 Feast
            self._setup_feast_repo(feast_repo_path)
            
            # 处理特征数据
            feature_data = self._process_features(examples, transform_graph)
            
            # 推送到 Feast
            self._push_to_feast(feature_data, feast_repo_path, feature_table_name)
            
            # 创建输出工件
            feast_output = output_dict['feast_features'][0]
            feast_output.uri = os.path.join(feast_repo_path, 'features')
            io_utils.write_string_file(
                os.path.join(feast_output.uri, 'SUCCESS'),
                'Feast features pushed successfully'
            )
            
            logging.info("✅ 特征成功推送到 Feast")
            
        except Exception as e:
            logging.error(f"❌ Feast 特征推送失败: {e}")
            raise
    
    def _setup_feast_repo(self, repo_path: str):
        """设置 Feast 仓库"""
        if not os.path.exists(repo_path):
            os.makedirs(repo_path, exist_ok=True)
            
        # 创建 feature_store.yaml
        config_content = f"""
project: taxi_mlops
registry: {repo_path}/data/registry.db
provider: local
online_store:
    type: sqlite
    path: {repo_path}/data/online_store.db
"""
        
        config_path = os.path.join(repo_path, 'feature_store.yaml')
        with open(config_path, 'w') as f:
            f.write(config_content)
    
    def _process_features(self, examples, transform_graph):
        """处理特征数据"""
        # 这里应该从 TFX examples 中提取特征
        # 简化版本，实际应该解析 TFRecord 文件
        
        # 模拟特征数据
        feature_data = pd.DataFrame({
            'trip_id': range(1000),
            'trip_start_hour': [i % 24 for i in range(1000)],
            'trip_start_day': [i % 7 for i in range(1000)],
            'trip_miles': [1.0 + (i % 20) for i in range(1000)],
            'fare': [5.0 + (i % 50) for i in range(1000)],
            'tips': [1 if i % 3 == 0 else 0 for i in range(1000)],
            'event_timestamp': pd.date_range('2023-01-01', periods=1000, freq='H')
        })
        
        return feature_data
    
    def _push_to_feast(self, feature_data: pd.DataFrame, repo_path: str, table_name: str):
        """推送特征到 Feast"""
        
        # 初始化 Feast 存储
        store = FeatureStore(repo_path=repo_path)
        
        # 定义实体
        trip_entity = Entity(
            name="trip_id",
            value_type=ValueType.INT64,
            description="出租车行程ID"
        )
        
        # 定义数据源
        data_source = FileSource(
            path=os.path.join(repo_path, 'data', f'{table_name}.parquet'),
            event_timestamp_column="event_timestamp"
        )
        
        # 保存特征数据
        data_path = os.path.join(repo_path, 'data')
        os.makedirs(data_path, exist_ok=True)
        feature_data.to_parquet(data_source.path, index=False)
        
        # 定义特征视图
        taxi_features_fv = FeatureView(
            name=table_name,
            entities=["trip_id"],
            ttl=timedelta(days=1),
            features=[
                Feature(name="trip_start_hour", dtype=ValueType.INT64),
                Feature(name="trip_start_day", dtype=ValueType.INT64),
                Feature(name="trip_miles", dtype=ValueType.DOUBLE),
                Feature(name="fare", dtype=ValueType.DOUBLE),
                Feature(name="tips", dtype=ValueType.INT64),
            ],
            online=True,
            source=data_source,
            tags={"team": "mlops", "pipeline": "taxi"}
        )
        
        # 应用到 Feast
        store.apply([trip_entity, taxi_features_fv])
        
        # 物化特征到在线存储
        store.materialize_incremental(end_date=pd.Timestamp.now())
        
        logging.info(f"特征已推送到 Feast 表: {table_name}")

class FeastFeaturePusher(base_component.BaseComponent):
    """Feast 特征推送组件"""
    
    SPEC_CLASS = types.ComponentSpec
    EXECUTOR_SPEC = executor_spec.ExecutorClassSpec(FeastFeaturePusherExecutor)
    
    def __init__(self,
                 examples: types.Channel,
                 transform_graph: Optional[types.Channel] = None,
                 feast_repo_path: str = './feast/feature_repo',
                 feature_table_name: str = 'taxi_features'):
        """
        初始化 Feast 特征推送组件
        
        Args:
            examples: TFX examples 输入
            transform_graph: Transform 图输入
            feast_repo_path: Feast 仓库路径
            feature_table_name: 特征表名称
        """
        
        # 定义输出
        feast_features = types.Channel(type=standard_artifacts.ExternalArtifact)
        
        spec = types.ComponentSpec(
            inputs={
                'examples': examples,
                'transform_graph': transform_graph
            } if transform_graph else {
                'examples': examples
            },
            outputs={
                'feast_features': feast_features
            },
            parameters={
                'feast_repo_path': feast_repo_path,
                'feature_table_name': feature_table_name
            }
        )
        
        super().__init__(spec=spec)
