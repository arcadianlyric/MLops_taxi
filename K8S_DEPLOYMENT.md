# TFX Pipeline Kubernetes Deployment

This guide provides step-by-step instructions for deploying the Chicago Taxi TFX pipeline on Kubernetes using Docker containers.

## Prerequisites

- Docker installed and running
- Kubernetes cluster (local or remote)
- kubectl configured to access your cluster
- At least 4GB RAM and 2 CPU cores available for the pipeline

## Architecture Overview

The deployment consists of:
- **TFX Pipeline Container**: Runs the complete ML pipeline
- **Persistent Volume**: Stores pipeline artifacts, metadata, and models
- **ConfigMap**: Pipeline configuration and environment variables
- **Kubernetes Job**: Manages pipeline execution

## Quick Start

### 1. Build Docker Image

```bash
chmod +x scripts/build-docker.sh
./scripts/build-docker.sh
```

### 2. Deploy to Kubernetes

```bash
chmod +x scripts/deploy-k8s.sh
./scripts/deploy-k8s.sh
```

### 3. Monitor Pipeline Execution

```bash
# Watch job status
kubectl get jobs -n tfx-pipeline -w

# View pipeline logs
kubectl logs -f job/tfx-pipeline-job -n tfx-pipeline

# Check all resources
kubectl get all -n tfx-pipeline
```

### 4. Access Pipeline Artifacts

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n tfx-pipeline -l job-name=tfx-pipeline-job -o jsonpath='{.items[0].metadata.name}')

# Copy artifacts from pod (if still running)
kubectl cp tfx-pipeline/$POD_NAME:/shared/serving_model ./local_models/

# Or access via persistent volume on the host
ls /tmp/tfx-pipeline-data/
```

## Pipeline Components

The TFX pipeline includes the following components:

1. **CsvExampleGen**: Ingests data from CSV files
2. **StatisticsGen**: Generates data statistics
3. **SchemaGen**: Infers data schema
4. **ExampleValidator**: Validates data quality
5. **Transform**: Feature engineering
6. **Trainer**: Model training with Keras
7. **Evaluator**: Model evaluation
8. **Pusher**: Model deployment

## Configuration

### Environment Variables (ConfigMap)

- `TFX_PIPELINE_NAME`: Pipeline identifier
- `TFX_DATA_ROOT`: Input data directory
- `TFX_PIPELINE_ROOT`: Pipeline artifacts directory
- `TFX_METADATA_PATH`: ML metadata database path
- `TFX_SERVING_MODEL_DIR`: Model output directory

### Resource Allocation

- **Memory**: 2-4 GB (configurable in job manifest)
- **CPU**: 1-2 cores (configurable in job manifest)
- **Storage**: 10 GB persistent volume

## Troubleshooting

### Common Issues

1. **Image Pull Error**
   ```bash
   # Ensure image is built locally
   docker images | grep tfx-taxi-pipeline
   ```

2. **Insufficient Resources**
   ```bash
   # Check node resources
   kubectl describe nodes
   ```

3. **Pipeline Failures**
   ```bash
   # Check detailed logs
   kubectl describe job tfx-pipeline-job -n tfx-pipeline
   kubectl logs job/tfx-pipeline-job -n tfx-pipeline
   ```

### Debugging Commands

```bash
# Get pod details
kubectl describe pod -n tfx-pipeline -l job-name=tfx-pipeline-job

# Access pod shell (if running)
kubectl exec -it <pod-name> -n tfx-pipeline -- /bin/bash

# Check persistent volume
kubectl describe pv tfx-pipeline-pv

# View events
kubectl get events -n tfx-pipeline --sort-by='.lastTimestamp'
```

## Cleanup

To remove all resources:

```bash
chmod +x scripts/cleanup-k8s.sh
./scripts/cleanup-k8s.sh
```

## Customization

### Modifying Pipeline Parameters

Edit `k8s/configmap.yaml` to change pipeline configuration:

```yaml
data:
  TFX_PIPELINE_NAME: "my_custom_pipeline"
  # Add other environment variables
```

### Scaling Resources

Edit `k8s/tfx-pipeline-job.yaml` to adjust resource allocation:

```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "2000m"
  limits:
    memory: "8Gi"
    cpu: "4000m"
```

### Using Different Data

1. Mount your data as a volume in the job manifest
2. Update the `TFX_DATA_ROOT` environment variable
3. Ensure data follows the expected CSV format

## Next Steps

- Add Kafka for streaming data ingestion
- Implement ML Metadata (MLMD) server
- Set up model serving with TensorFlow Serving
- Add monitoring and alerting
- Implement CI/CD pipeline for automated deployments

## File Structure

```
├── k8s/
│   ├── namespace.yaml
│   ├── persistent-volume.yaml
│   ├── configmap.yaml
│   └── tfx-pipeline-job.yaml
├── scripts/
│   ├── build-docker.sh
│   ├── deploy-k8s.sh
│   └── cleanup-k8s.sh
├── tfx_pipeline/
│   ├── Dockerfile
│   ├── taxi_pipeline_k8s.py
│   ├── taxi_utils_native_keras.py
│   └── data/
└── K8S_DEPLOYMENT.md
```
