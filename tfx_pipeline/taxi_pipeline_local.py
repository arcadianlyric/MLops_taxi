"""Chicago taxi pipeline using LocalDagRunner for TFX 0.21."""

import logging
import os

from tfx.components.example_gen.csv_example_gen.component import CsvExampleGen
from tfx.components.schema_gen.component import SchemaGen
from tfx.components.statistics_gen.component import StatisticsGen
from tfx.components.trainer.component import Trainer
from tfx.components.transform.component import Transform
from tfx.orchestration import metadata
from tfx.orchestration.local.local_dag_runner import LocalDagRunner
from tfx.orchestration.pipeline import Pipeline
from tfx.proto import trainer_pb2
from tfx.utils.dsl_utils import external_input


def create_pipeline(pipeline_name,
                   pipeline_root,
                   data_root,
                   module_file,
                   metadata_path):
  """Creates a taxi pipeline using LocalDagRunner."""
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
      train_args=trainer_pb2.TrainArgs(num_steps=1000),
      eval_args=trainer_pb2.EvalArgs(num_steps=500))

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
          metadata_path))


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)

  # Use the project's root directory
  _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

  # Define pipeline name and root directories
  _pipeline_name = 'chicago_taxi_local'
  _tfx_root = os.path.join(_project_root, 'tfx_pipeline')
  _pipeline_root = os.path.join(_tfx_root, 'pipelines', _pipeline_name)

  # Data root for the pipeline
  _data_root = os.path.join(_tfx_root, 'data', 'simple')

  # Module file
  _module_file = os.path.join(_tfx_root, 'taxi_utils.py')

  # Metadata path
  _metadata_path = os.path.join(_tfx_root, 'metadata', _pipeline_name, 'metadata.db')

  logging.info('Starting TFX pipeline with LocalDagRunner...')
  
  LocalDagRunner().run(
      create_pipeline(
          pipeline_name=_pipeline_name,
          pipeline_root=_pipeline_root,
          data_root=_data_root,
          module_file=_module_file,
          metadata_path=_metadata_path))
  
  logging.info('Pipeline completed!')
