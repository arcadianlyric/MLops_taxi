#!/bin/bash

# Build Docker image for TFX pipeline
set -e

echo "Building TFX Pipeline Docker image..."

# Navigate to the tfx_pipeline directory
cd "$(dirname "$0")/../tfx_pipeline"

# Build the Docker image
docker build -t tfx-taxi-pipeline:latest .

echo "Docker image built successfully: tfx-taxi-pipeline:latest"

# Verify the image
docker images | grep tfx-taxi-pipeline

echo "Build completed!"
