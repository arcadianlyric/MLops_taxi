# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Chicago taxi example using TFX."""

import logging
import os

from tfx.components.evaluator.component import Evaluator
from tfx.components.example_gen.csv_example_gen.component import CsvExampleGen
from tfx.components.example_validator.component import ExampleValidator
from tfx.components.model_validator.component import ModelValidator
from tfx.components.pusher.component import Pusher
from tfx.components.schema_gen.component import SchemaGen
from tfx.components.statistics_gen.component import StatisticsGen
from tfx.components.trainer.component import Trainer
from tfx.components.transform.component import Transform
from tfx.orchestration import metadata
from tfx.orchestration.beam.beam_dag_runner import BeamDagRunner
from tfx.orchestration.pipeline import Pipeline
from tfx.proto import evaluator_pb2
from tfx.proto import pusher_pb2
from tfx.proto import trainer_pb2
from tfx.utils.dsl_utils import external_input


def create_pipeline(pipeline_name,
                    pipeline_root,
                    data_root,
                    module_file,
                    serving_model_dir,
                    metadata_path,
                    beam_pipeline_args):
  """Implements the chicago taxi pipeline with TFX."""
  examples = external_input(data_root)

  # Brings data into the pipeline or otherwise joins/converts training data.
  example_gen = CsvExampleGen(input_base=examples)

  # Computes statistics over data for visualization and example validation.
  statistics_gen = StatisticsGen(input_data=example_gen.outputs.examples)

  # Generates schema based on statistics files.
  infer_schema = SchemaGen(stats=statistics_gen.outputs.statistics)

  # Performs anomaly detection based on statistics and data schema.
  validate_stats = ExampleValidator(
      stats=statistics_gen.outputs.statistics,
      schema=infer_schema.outputs.schema)

  # Performs transformations and feature engineering in training and serving.
  transform = Transform(
      input_data=example_gen.outputs.examples,
      schema=infer_schema.outputs.schema,
      module_file=module_file)

  # Uses user-provided Python function that implements a model.
  trainer = Trainer(
      module_file=module_file,
      transformed_examples=transform.outputs.transformed_examples,
      schema=infer_schema.outputs.schema,
      transform_output=transform.outputs.transform_output,
      train_args=trainer_pb2.TrainArgs(num_steps=10000),
      eval_args=trainer_pb2.EvalArgs(num_steps=5000))

  # Uses TFMA to compute a evaluation statistics over features of a model.
  model_analyzer = Evaluator(
      examples=example_gen.outputs.examples,
      model_exports=trainer.outputs.output,
      feature_slicing_spec=evaluator_pb2.FeatureSlicingSpec(
          specs=[
              evaluator_pb2.SingleSlicingSpec(
                  column_for_slicing=['trip_start_hour'])
          ]))

  # Performs quality validation of a candidate model (compared to a baseline).
  model_validator = ModelValidator(
      examples=example_gen.outputs.examples, model=trainer.outputs.output)

  # Checks whether the model passed the validation steps and pushes the model
  # to a file destination if check passed.
  pusher = Pusher(
      model_export=trainer.outputs.output,
      model_blessing=model_validator.outputs.blessing,
      push_destination=pusher_pb2.PushDestination(
          filesystem=pusher_pb2.PushDestination.Filesystem(
              base_directory=serving_model_dir)))

  return Pipeline(
      pipeline_name=pipeline_name,
      pipeline_root=pipeline_root,
      components=[
          example_gen, statistics_gen, infer_schema, validate_stats, transform,
          trainer, model_analyzer, model_validator, pusher
      ],
      enable_cache=True,
      metadata_connection_config=metadata.sqlite_metadata_connection_config(
          metadata_path),
      beam_pipeline_args=beam_pipeline_args)

if __name__ == '__main__':
  # This is a TFX local runner example, so it needs to be run from the top-level
  # directory of the repository.

  # Set up logging.
  logging.basicConfig(level=logging.INFO)

  # Use the project's root directory.
  _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

  # Define pipeline name and root directories.
  _pipeline_name = 'chicago_taxi_beam'
  _tfx_root = os.path.join(_project_root, 'tfx_pipeline')
  _pipeline_root = os.path.join(_tfx_root, 'pipelines', _pipeline_name)

  # Data root for the pipeline.
  _data_root = os.path.join(_tfx_root, 'data', 'simple')

  # Module file to inject customized logic into the TFX components.
  _module_file = os.path.join(_tfx_root, 'taxi_utils.py')

  # Output directory to push trainer model to.
  _serving_model_dir = os.path.join(_tfx_root, 'serving_model', _pipeline_name)

  # Metadata path for MLMD record keeping.
  _metadata_path = os.path.join(_tfx_root, 'metadata', _pipeline_name, 'metadata.db')

  # The rate at which to sample rows from the data table. Leave as 1 to include
  # all records.
  _query_sample_rate = 1

  # Beam args to use in this pipeline - use single process for Docker compatibility
  _beam_pipeline_args = []

  BeamDagRunner().run(
      create_pipeline(
          pipeline_name=_pipeline_name,
          pipeline_root=_pipeline_root,
          data_root=_data_root,
          module_file=_module_file,
          serving_model_dir=_serving_model_dir,
          metadata_path=_metadata_path,
          beam_pipeline_args=_beam_pipeline_args))
