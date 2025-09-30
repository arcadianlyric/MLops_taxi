"""Simplified Chicago taxi pipeline for TFX 0.21 - training only."""

import logging
import os

from tfx.components.example_gen.csv_example_gen.component import CsvExampleGen
from tfx.components.schema_gen.component import SchemaGen
from tfx.components.statistics_gen.component import StatisticsGen
from tfx.components.trainer.component import Trainer
from tfx.components.transform.component import Transform
from tfx.orchestration import metadata
from tfx.orchestration.beam.beam_dag_runner import BeamDagRunner
from tfx.orchestration.pipeline import Pipeline
from tfx.proto import trainer_pb2
from tfx.utils.dsl_utils import external_input


def create_simple_pipeline(pipeline_name,
                           pipeline_root,
                           data_root,
                           module_file,
                           serving_model_dir,
                           metadata_path,
                           beam_pipeline_args):
  """Creates a simplified taxi pipeline with only training components."""
  examples = external_input(data_root)

  # Brings data into the pipeline
  example_gen = CsvExampleGen(input_base=examples)

  # Computes statistics over data
  statistics_gen = StatisticsGen(input_data=example_gen.outputs.examples)

  # Generates schema based on statistics files
  infer_schema = SchemaGen(stats=statistics_gen.outputs.statistics)

  # Performs transformations and feature engineering
  transform = Transform(
      input_data=example_gen.outputs.examples,
      schema=infer_schema.outputs.schema,
      module_file=module_file)

  # Trains the model
  trainer = Trainer(
      module_file=module_file,
      transformed_examples=transform.outputs.transformed_examples,
      schema=infer_schema.outputs.schema,
      transform_output=transform.outputs.transform_output,
      train_args=trainer_pb2.TrainArgs(num_steps=100),  # Reduced for testing
      eval_args=trainer_pb2.EvalArgs(num_steps=50))

  return Pipeline(
      pipeline_name=pipeline_name,
      pipeline_root=pipeline_root,
      components=[
          example_gen,
          statistics_gen,
          infer_schema,
          transform,
          trainer,
      ],
      enable_cache=True,
      metadata_connection_config=metadata.sqlite_metadata_connection_config(
          metadata_path),
      beam_pipeline_args=beam_pipeline_args)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)

  # Use the project's root directory
  _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

  # Define pipeline name and root directories
  _pipeline_name = 'chicago_taxi_simple'
  _tfx_root = os.path.join(_project_root, 'tfx_pipeline')
  _pipeline_root = os.path.join(_tfx_root, 'pipelines', _pipeline_name)

  # Data root for the pipeline
  _data_root = os.path.join(_tfx_root, 'data', 'simple')

  # Module file to inject customized logic into the TFX components
  _module_file = os.path.join(_tfx_root, 'taxi_utils.py')

  # Output directory to push trainer model to
  _serving_model_dir = os.path.join(_tfx_root, 'serving_model', _pipeline_name)

  # Metadata path for MLMD record keeping
  _metadata_path = os.path.join(_tfx_root, 'metadata', _pipeline_name, 'metadata.db')

  # Empty beam args for single-process execution
  _beam_pipeline_args = []

  logging.info('Starting simplified TFX pipeline...')
  
  BeamDagRunner().run(
      create_simple_pipeline(
          pipeline_name=_pipeline_name,
          pipeline_root=_pipeline_root,
          data_root=_data_root,
          module_file=_module_file,
          serving_model_dir=_serving_model_dir,
          metadata_path=_metadata_path,
          beam_pipeline_args=_beam_pipeline_args))
  
  logging.info('Pipeline completed!')
