#!/bin/bash

# Deploy TFX pipeline to Kubernetes
set -e

echo "Deploying TFX Pipeline to Kubernetes..."

# Navigate to the k8s directory
cd "$(dirname "$0")/../k8s"

# Apply Kubernetes manifests in order
echo "Creating namespace..."
kubectl apply -f namespace.yaml

echo "Creating persistent volume..."
kubectl apply -f persistent-volume.yaml

echo "Creating configmap..."
kubectl apply -f configmap.yaml

echo "Deploying TFX pipeline job..."
kubectl apply -f tfx-pipeline-job.yaml

echo "Deployment completed!"

# Show status
echo "Checking deployment status..."
kubectl get all -n tfx-pipeline

echo ""
echo "To monitor the pipeline execution:"
echo "kubectl logs -f job/tfx-pipeline-job -n tfx-pipeline"
echo ""
echo "To check pipeline status:"
echo "kubectl get jobs -n tfx-pipeline"
