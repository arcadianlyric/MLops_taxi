#!/usr/bin/env python3
"""Chicago taxi TFX pipeline optimized for Kubernetes deployment."""

import os
from typing import List

import absl
import tensorflow_model_analysis as tfma
from tfx.components import CsvExampleGen
from tfx.components import Evaluator
from tfx.components import ExampleValidator
from tfx.components import Pusher
from tfx.components import SchemaGen
from tfx.components import StatisticsGen
from tfx.components import Trainer
from tfx.components import Transform
from tfx.dsl.components.common import resolver
from tfx.dsl.experimental import latest_blessed_model_resolver
from tfx.orchestration import metadata
from tfx.orchestration import pipeline
from tfx.orchestration.beam.beam_dag_runner import BeamDagRunner
from tfx.proto import pusher_pb2
from tfx.proto import trainer_pb2
from tfx.types import Channel
from tfx.types.standard_artifacts import Model
from tfx.types.standard_artifacts import ModelBlessing

# Pipeline configuration from environment variables
_pipeline_name = os.getenv('TFX_PIPELINE_NAME', 'chicago_taxi_k8s')
_data_root = os.getenv('TFX_DATA_ROOT', '/app/data/simple')
_module_file = os.getenv('TFX_MODULE_FILE', '/app/taxi_utils_native_keras.py')
_pipeline_root = os.getenv('TFX_PIPELINE_ROOT', f'/app/pipelines/{_pipeline_name}')
_metadata_path = os.getenv('TFX_METADATA_PATH', f'/app/metadata/{_pipeline_name}/metadata.db')
_serving_model_dir = os.getenv('TFX_SERVING_MODEL_DIR', f'/app/serving_model/{_pipeline_name}')

# Beam pipeline arguments optimized for containerized environment
_beam_pipeline_args = [
    '--direct_running_mode=multi_processing',
    '--direct_num_workers=2',  # Limited for container resources
    '--runner=DirectRunner',
]

def _create_pipeline(pipeline_name: str, pipeline_root: str, data_root: str,
                     module_file: str, serving_model_dir: str,
                     metadata_path: str,
                     beam_pipeline_args: List[str]) -> pipeline.Pipeline:
    """Creates the TFX pipeline for Kubernetes deployment."""
    
    # Ensure directories exist
    os.makedirs(os.path.dirname(pipeline_root), exist_ok=True)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    os.makedirs(serving_model_dir, exist_ok=True)
    
    # Data ingestion
    example_gen = CsvExampleGen(input_base=data_root)

    # Statistics generation
    statistics_gen = StatisticsGen(examples=example_gen.outputs['examples'])

    # Schema generation
    schema_gen = SchemaGen(
        statistics=statistics_gen.outputs['statistics'],
        infer_feature_shape=True)

    # Data validation
    example_validator = ExampleValidator(
        statistics=statistics_gen.outputs['statistics'],
        schema=schema_gen.outputs['schema'])

    # Feature engineering
    transform = Transform(
        examples=example_gen.outputs['examples'],
        schema=schema_gen.outputs['schema'],
        module_file=module_file)

    # Model training
    trainer = Trainer(
        module_file=module_file,
        examples=transform.outputs['transformed_examples'],
        transform_graph=transform.outputs['transform_graph'],
        schema=schema_gen.outputs['schema'],
        train_args=trainer_pb2.TrainArgs(num_steps=500),  # Reduced for faster execution
        eval_args=trainer_pb2.EvalArgs(num_steps=100))

    # Model resolver for baseline comparison
    model_resolver = resolver.Resolver(
        strategy_class=latest_blessed_model_resolver.LatestBlessedModelResolver,
        model=Channel(type=Model),
        model_blessing=Channel(
            type=ModelBlessing)).with_id('latest_blessed_model_resolver')

    # Model evaluation configuration
    eval_config = tfma.EvalConfig(
        model_specs=[
            tfma.ModelSpec(
                signature_name='serving_default', 
                label_key='tips_xf',
                preprocessing_function_names=['transform_features'])
        ],
        slicing_specs=[tfma.SlicingSpec()],
        metrics_specs=[
            tfma.MetricsSpec(metrics=[
                tfma.MetricConfig(
                    class_name='BinaryAccuracy',
                    threshold=tfma.MetricThreshold(
                        value_threshold=tfma.GenericValueThreshold(
                            lower_bound={'value': 0.5}),  # Lowered threshold for demo
                        change_threshold=tfma.GenericChangeThreshold(
                            direction=tfma.MetricDirection.HIGHER_IS_BETTER,
                            absolute={'value': -1e-10})))
            ])
        ])
    
    # Model evaluation
    evaluator = Evaluator(
        examples=example_gen.outputs['examples'],
        model=trainer.outputs['model'],
        baseline_model=model_resolver.outputs['model'],
        eval_config=eval_config)

    # Model deployment
    pusher = Pusher(
        model=trainer.outputs['model'],
        model_blessing=evaluator.outputs['blessing'],
        push_destination=pusher_pb2.PushDestination(
            filesystem=pusher_pb2.PushDestination.Filesystem(
                base_directory=serving_model_dir)))

    return pipeline.Pipeline(
        pipeline_name=pipeline_name,
        pipeline_root=pipeline_root,
        components=[
            example_gen,
            statistics_gen,
            schema_gen,
            example_validator,
            transform,
            trainer,
            model_resolver,
            evaluator,
            pusher,
        ],
        enable_cache=True,
        metadata_connection_config=metadata.sqlite_metadata_connection_config(
            metadata_path),
        beam_pipeline_args=beam_pipeline_args)


def main():
    """Main function to run the TFX pipeline."""
    absl.logging.set_verbosity(absl.logging.INFO)
    
    # Log configuration
    absl.logging.info(f"Pipeline Name: {_pipeline_name}")
    absl.logging.info(f"Data Root: {_data_root}")
    absl.logging.info(f"Pipeline Root: {_pipeline_root}")
    absl.logging.info(f"Metadata Path: {_metadata_path}")
    absl.logging.info(f"Serving Model Dir: {_serving_model_dir}")
    
    # Create and run pipeline
    tfx_pipeline = _create_pipeline(
        pipeline_name=_pipeline_name,
        pipeline_root=_pipeline_root,
        data_root=_data_root,
        module_file=_module_file,
        metadata_path=_metadata_path,
        serving_model_dir=_serving_model_dir,
        beam_pipeline_args=_beam_pipeline_args)
    
    BeamDagRunner().run(tfx_pipeline)
    absl.logging.info("Pipeline execution completed successfully!")


if __name__ == '__main__':
    main()
