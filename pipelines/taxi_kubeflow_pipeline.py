#!/usr/bin/env python3
"""
基于现有 tfx_pipeline 的 Kubeflow 集成版本
将 taxi_pipeline_native_keras.py 改造为企业级 Kubeflow Pipeline
"""

import os
from typing import List, Dict, Any, Optional
from absl import logging
import tensorflow_model_analysis as tfma

# TFX 核心组件
from tfx.components import CsvExampleGen, StatisticsGen, SchemaGen, ExampleValidator
from tfx.components import Transform, Trainer, Evaluator, Pusher
from tfx.dsl.components.common import resolver
from tfx.dsl.experimental import latest_blessed_model_resolver
from tfx.orchestration import metadata, pipeline
from tfx.orchestration.kubeflow.v2 import kubeflow_v2_dag_runner
from tfx.proto import pusher_pb2, trainer_pb2
from tfx.types import Channel
from tfx.types.standard_artifacts import Model, ModelBlessing

# Kubeflow 相关
import kfp
from kfp.v2 import compiler

class TaxiKubeflowPipeline:
    """
    基于 tfx_pipeline/taxi_pipeline_native_keras.py 的企业级 Kubeflow Pipeline
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化 Pipeline 配置"""
        self.config = config
        self.pipeline_name = config.get('pipeline_name', 'taxi-kubeflow-pipeline')
        self.pipeline_root = config.get('pipeline_root', 'gs://mlops-taxi-pipeline')
        
        # 基于现有 tfx_pipeline 的路径配置
        self.data_root = config.get('data_root', './tfx_pipeline/data/simple')
        self.module_file = config.get('module_file', './tfx_pipeline/taxi_utils_native_keras.py')
        
        # 模型服务配置
        self.serving_model_dir = config.get('serving_model_dir', 'gs://mlops-taxi-models')
        
        # Feast 配置
        self.feast_repo_path = config.get('feast_repo_path', './feast/feature_repo')
        
        # Metadata 配置
        self.metadata_connection_config = self._get_metadata_config()
    
    def _get_metadata_config(self):
        """获取 Metadata 存储配置"""
        metadata_path = self.config.get('metadata_path', 'gs://mlops-taxi-metadata')
        return metadata.mysql_metadata_connection_config(
            host='mysql.kubeflow.svc.cluster.local',
            port=3306,
            database='mlops_metadata',
            username='root',
            password='password'
        ) if 'mysql' in self.config else metadata.sqlite_metadata_connection_config(
            '/tmp/taxi_metadata.db'
        )
    
    def _get_eval_config(self):
        """获取模型评估配置 - 基于原始 taxi pipeline"""
        return tfma.EvalConfig(
            model_specs=[tfma.ModelSpec(label_key='tips')],
            slicing_specs=[
                tfma.SlicingSpec(),
                tfma.SlicingSpec(feature_keys=['trip_start_hour']),
                tfma.SlicingSpec(feature_keys=['trip_start_day']),
                tfma.SlicingSpec(feature_keys=['pickup_community_area'])
            ],
            metrics_specs=[
                tfma.MetricsSpec(
                    metrics=[
                        tfma.MetricConfig(class_name='BinaryAccuracy'),
                        tfma.MetricConfig(class_name='Precision'),
                        tfma.MetricConfig(class_name='Recall'),
                        tfma.MetricConfig(class_name='AUC'),
                        tfma.MetricConfig(class_name='MeanSquaredError'),
                        tfma.MetricConfig(
                            class_name='FairnessIndicators',
                            config='{"thresholds": [0.5]}'
                        )
                    ]
                )
            ]
        )
    
    def create_pipeline(self) -> pipeline.Pipeline:
        """
        创建完整的 TFX Pipeline - 基于 taxi_pipeline_native_keras.py
        """
        logging.info(f"创建 Taxi Kubeflow Pipeline: {self.pipeline_name}")
        
        # 1. 数据摄取 - 使用 tfx_pipeline/data 中的数据
        example_gen = CsvExampleGen(input_base=self.data_root)
        
        # 2. 数据统计分析
        statistics_gen = StatisticsGen(examples=example_gen.outputs['examples'])
        
        # 3. 数据模式推断
        schema_gen = SchemaGen(
            statistics=statistics_gen.outputs['statistics'],
            infer_feature_shape=True
        )
        
        # 4. 数据验证
        example_validator = ExampleValidator(
            statistics=statistics_gen.outputs['statistics'],
            schema=schema_gen.outputs['schema']
        )
        
        # 5. 特征工程 - 使用 taxi_utils_native_keras.py 中的 preprocessing_fn
        transform = Transform(
            examples=example_gen.outputs['examples'],
            schema=schema_gen.outputs['schema'],
            module_file=self.module_file
        )
        
        # 6. 模型训练 - 使用 taxi_utils_native_keras.py 中的 run_fn
        trainer = Trainer(
            module_file=self.module_file,
            examples=example_gen.outputs['examples'],
            transform_graph=transform.outputs['transform_graph'],
            schema=schema_gen.outputs['schema'],
            train_args=trainer_pb2.TrainArgs(num_steps=2000),
            eval_args=trainer_pb2.EvalArgs(num_steps=500)
        )
        
        # 7. 模型解析器 - 获取最新的已验证模型
        model_resolver = resolver.Resolver(
            strategy_class=latest_blessed_model_resolver.LatestBlessedModelResolver,
            model=Channel(type=Model),
            model_blessing=Channel(type=ModelBlessing)
        ).with_id('latest_blessed_model_resolver')
        
        # 8. 模型评估
        evaluator = Evaluator(
            examples=example_gen.outputs['examples'],
            model=trainer.outputs['model'],
            baseline_model=model_resolver.outputs['model'],
            eval_config=self._get_eval_config()
        )
        
        # 9. 模型推送到服务目录
        pusher = Pusher(
            model=trainer.outputs['model'],
            model_blessing=evaluator.outputs['blessing'],
            push_destination=pusher_pb2.PushDestination(
                filesystem=pusher_pb2.PushDestination.Filesystem(
                    base_directory=self.serving_model_dir
                )
            )
        )
        
        # 组装 Pipeline
        components = [
            example_gen,
            statistics_gen,
            schema_gen,
            example_validator,
            transform,
            trainer,
            model_resolver,
            evaluator,
            pusher
        ]
        
        return pipeline.Pipeline(
            pipeline_name=self.pipeline_name,
            pipeline_root=self.pipeline_root,
            components=components,
            metadata_connection_config=self.metadata_connection_config,
            beam_pipeline_args=[
                '--runner=DataflowRunner',
                '--project=your-gcp-project',
                '--region=us-central1',
                '--temp_location=gs://mlops-taxi-temp',
            ] if 'dataflow' in self.config else None
        )

def create_kubeflow_pipeline(config: Dict[str, Any]):
    """创建并编译 Kubeflow Pipeline"""
    
    # 创建 TFX Pipeline
    taxi_pipeline = TaxiKubeflowPipeline(config)
    tfx_pipeline = taxi_pipeline.create_pipeline()
    
    # 编译为 Kubeflow Pipeline
    runner = kubeflow_v2_dag_runner.KubeflowV2DagRunner(
        config=kubeflow_v2_dag_runner.KubeflowV2DagRunnerConfig(
            default_image='tensorflow/tfx:1.14.0'
        )
    )
    
    # 编译 Pipeline
    pipeline_definition_file = f'{config["pipeline_name"]}.yaml'
    runner.run(
        tfx_pipeline,
        output_filename=pipeline_definition_file
    )
    
    logging.info(f"Pipeline 已编译到: {pipeline_definition_file}")
    return pipeline_definition_file

# 配置示例
DEFAULT_CONFIG = {
    'pipeline_name': 'taxi-kubeflow-pipeline',
    'pipeline_root': 'gs://mlops-taxi-pipeline',
    'data_root': './tfx_pipeline/data/simple',
    'module_file': './tfx_pipeline/taxi_utils_native_keras.py',
    'serving_model_dir': 'gs://mlops-taxi-models',
    'metadata_path': 'gs://mlops-taxi-metadata',
    'feast_repo_path': './feast/feature_repo'
}

if __name__ == '__main__':
    # 创建和编译 Pipeline
    pipeline_file = create_kubeflow_pipeline(DEFAULT_CONFIG)
    print(f"✅ Kubeflow Pipeline 创建完成: {pipeline_file}")
