#!/usr/bin/env python3
"""
数据漂移监控使用示例
演示如何在 TFX Pipeline 中集成数据漂移监控
"""

import os
import sys
from typing import List

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tfx.components import CsvExampleGen
from tfx.components import StatisticsGen
from tfx.components import SchemaGen
from tfx.components import ExampleValidator
from tfx.orchestration import pipeline
from tfx.orchestration import metadata
from tfx.orchestration.beam.beam_dag_runner import BeamDagRunner

# 导入自定义数据漂移监控组件
from components.data_drift_monitor import DataDriftMonitor


def create_drift_monitoring_pipeline(
    pipeline_name: str,
    pipeline_root: str,
    baseline_data_root: str,
    current_data_root: str,
    metadata_path: str,
    beam_pipeline_args: List[str]
) -> pipeline.Pipeline:
    """
    创建包含数据漂移监控的 TFX Pipeline
    
    Args:
        pipeline_name: Pipeline 名称
        pipeline_root: Pipeline 根目录
        baseline_data_root: 基线数据路径
        current_data_root: 当前数据路径
        metadata_path: 元数据路径
        beam_pipeline_args: Beam 参数
    
    Returns:
        TFX Pipeline 实例
    """
    
    # 1. 基线数据摄取
    baseline_example_gen = CsvExampleGen(
        input_base=baseline_data_root
    ).with_id('baseline_example_gen')
    
    # 2. 当前数据摄取
    current_example_gen = CsvExampleGen(
        input_base=current_data_root
    ).with_id('current_example_gen')
    
    # 3. 基线数据统计
    baseline_statistics_gen = StatisticsGen(
        examples=baseline_example_gen.outputs['examples']
    ).with_id('baseline_statistics_gen')
    
    # 4. 当前数据统计
    current_statistics_gen = StatisticsGen(
        examples=current_example_gen.outputs['examples']
    ).with_id('current_statistics_gen')
    
    # 5. 生成数据模式（基于基线数据）
    schema_gen = SchemaGen(
        statistics=baseline_statistics_gen.outputs['statistics'],
        infer_feature_shape=True
    )
    
    # 6. 验证当前数据
    example_validator = ExampleValidator(
        statistics=current_statistics_gen.outputs['statistics'],
        schema=schema_gen.outputs['schema']
    )
    
    # 7. 数据漂移监控（核心组件）
    data_drift_monitor = DataDriftMonitor(
        baseline_examples=baseline_example_gen.outputs['examples'],
        current_examples=current_example_gen.outputs['examples'],
        schema=schema_gen.outputs['schema'],
        drift_threshold=0.1,  # 漂移阈值
        feature_allowlist=[
            'trip_miles', 'fare', 'trip_seconds',
            'pickup_latitude', 'pickup_longitude',
            'dropoff_latitude', 'dropoff_longitude',
            'payment_type', 'company'
        ]
    )
    
    # 组装 Pipeline
    components = [
        baseline_example_gen,
        current_example_gen,
        baseline_statistics_gen,
        current_statistics_gen,
        schema_gen,
        example_validator,
        data_drift_monitor,
    ]
    
    return pipeline.Pipeline(
        pipeline_name=pipeline_name,
        pipeline_root=pipeline_root,
        components=components,
        enable_cache=True,
        metadata_connection_config=metadata.sqlite_metadata_connection_config(
            metadata_path
        ),
        beam_pipeline_args=beam_pipeline_args
    )


def run_drift_monitoring_example():
    """运行数据漂移监控示例"""
    
    # 配置参数
    pipeline_name = 'chicago_taxi_drift_monitoring'
    
    # 路径配置
    project_root = os.path.dirname(os.path.dirname(__file__))
    pipeline_root = os.path.join(project_root, 'pipelines', pipeline_name)
    metadata_path = os.path.join(project_root, 'metadata', pipeline_name, 'metadata.db')
    
    # 数据路径（需要准备基线数据和当前数据）
    baseline_data_root = os.path.join(project_root, 'data', 'baseline')
    current_data_root = os.path.join(project_root, 'data', 'current')
    
    # Beam 参数
    beam_pipeline_args = [
        '--direct_running_mode=multi_processing',
        '--direct_num_workers=0',
    ]
    
    # 创建 Pipeline
    drift_pipeline = create_drift_monitoring_pipeline(
        pipeline_name=pipeline_name,
        pipeline_root=pipeline_root,
        baseline_data_root=baseline_data_root,
        current_data_root=current_data_root,
        metadata_path=metadata_path,
        beam_pipeline_args=beam_pipeline_args
    )
    
    # 运行 Pipeline
    BeamDagRunner().run(drift_pipeline)
    
    print(f"数据漂移监控 Pipeline 已完成！")
    print(f"查看结果: {pipeline_root}")


if __name__ == '__main__':
    run_drift_monitoring_example()
