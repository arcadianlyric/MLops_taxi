#!/bin/bash

# This script builds a dedicated Docker image for the TFX pipeline
# and runs the training pipeline within it.

set -e

# --- Configuration ---
IMAGE_NAME="tfx-taxi-trainer"
PROJECT_DIR=$(dirname "$0")/..

# --- Color Codes ---
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Main Logic ---
cd "$PROJECT_DIR"

echo -e "${BLUE}Step 1: Building the TFX training Docker image (${IMAGE_NAME})...${NC}"
# Add --no-cache to ensure the latest script is always used
docker build --no-cache -f Dockerfile.tfx -t "$IMAGE_NAME" .
echo -e "${GREEN}TFX Docker image built successfully.${NC}"

echo -e "\n${BLUE}Step 2: Running the TFX pipeline inside the Docker container...${NC}"
echo "This will execute 'tfx_pipeline/taxi_pipeline_native_keras.py'."
echo "Pipeline outputs (metadata, logs, and trained model) will be saved to the 'tfx_pipeline' directory on your host machine."

# Run the container, mounting the pipeline directory to get the output back on the host.
# The pipeline script will be executed inside the container.
# Run the container, mounting the pipeline directory to get the output back on the host.
# The python command is passed directly to the container's entrypoint.
docker run --rm \
  -v "$(pwd)/tfx_pipeline:/pipeline/tfx_pipeline" \
  "$IMAGE_NAME" \
  python3 tfx_pipeline/taxi_pipeline_native_keras.py

PIPELINE_RUN_STATUS=$?

if [ $PIPELINE_RUN_STATUS -eq 0 ]; then
  echo -e "\n${GREEN}Step 3: TFX pipeline completed successfully!${NC}"
  echo -e "A new model has been trained and saved in the '${GREEN}tfx_pipeline/serving_model/chicago_taxi_native_keras/${NC}' directory."
  echo -e "\nNext steps:"
  echo "  1. Inspect the model files in the serving_model directory."
  echo "  2. Update the FastAPI application to load and use this new model."
else
  echo -e "\n${RED}Error: TFX pipeline run failed with exit code ${PIPELINE_RUN_STATUS}.${NC}"
  echo "Please check the logs above for details."
  exit 1
fi
