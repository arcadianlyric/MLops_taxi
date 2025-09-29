#!/bin/bash

# Cleanup TFX pipeline Kubernetes resources
set -e

echo "Cleaning up TFX Pipeline Kubernetes resources..."

# Navigate to the k8s directory
cd "$(dirname "$0")/../k8s"

# Delete resources in reverse order
echo "Deleting TFX pipeline job..."
kubectl delete -f tfx-pipeline-job.yaml --ignore-not-found=true

echo "Deleting configmap..."
kubectl delete -f configmap.yaml --ignore-not-found=true

echo "Deleting persistent volume..."
kubectl delete -f persistent-volume.yaml --ignore-not-found=true

echo "Deleting namespace..."
kubectl delete -f namespace.yaml --ignore-not-found=true

echo "Cleanup completed!"

# Verify cleanup
echo "Verifying cleanup..."
kubectl get namespaces | grep tfx-pipeline || echo "Namespace successfully deleted"
