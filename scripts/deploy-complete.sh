#!/bin/bash

# Complete TFX Pipeline Deployment Script with Debugging
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    print_success "Docker is running"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check Kubernetes cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        print_status "Make sure your kubectl is configured and cluster is accessible"
        exit 1
    fi
    print_success "Kubernetes cluster is accessible"
    
    # Check available resources
    print_status "Checking cluster resources..."
    kubectl top nodes 2>/dev/null || print_warning "Cannot get node metrics (metrics-server might not be installed)"
}

# Function to build Docker image
build_docker_image() {
    print_status "Building Docker image..."
    
    # Navigate to tfx_pipeline directory
    cd "$(dirname "$0")/../tfx_pipeline"
    
    # Check if required files exist
    if [[ ! -f "taxi_pipeline_k8s.py" ]]; then
        print_error "taxi_pipeline_k8s.py not found in tfx_pipeline directory"
        exit 1
    fi
    
    if [[ ! -f "taxi_utils_native_keras.py" ]]; then
        print_error "taxi_utils_native_keras.py not found in tfx_pipeline directory"
        exit 1
    fi
    
    if [[ ! -d "data/simple" ]]; then
        print_error "data/simple directory not found in tfx_pipeline directory"
        exit 1
    fi
    
    # Build the image
    print_status "Building tfx-taxi-pipeline:latest..."
    if docker build -t tfx-taxi-pipeline:latest .; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
    
    # Verify the image
    docker images | grep tfx-taxi-pipeline
    
    # Get image size
    IMAGE_SIZE=$(docker images tfx-taxi-pipeline:latest --format "table {{.Size}}" | tail -n 1)
    print_status "Image size: $IMAGE_SIZE"
}

# Function to deploy to Kubernetes
deploy_to_kubernetes() {
    print_status "Deploying to Kubernetes..."
    
    # Navigate to k8s directory
    cd "$(dirname "$0")/../k8s"
    
    # Check if required manifests exist
    for file in namespace.yaml persistent-volume.yaml configmap.yaml tfx-pipeline-job.yaml; do
        if [[ ! -f "$file" ]]; then
            print_error "$file not found in k8s directory"
            exit 1
        fi
    done
    
    # Clean up any existing deployment
    print_status "Cleaning up existing deployment..."
    kubectl delete job tfx-pipeline-job -n tfx-pipeline --ignore-not-found=true
    
    # Apply manifests in order
    print_status "Creating namespace..."
    kubectl apply -f namespace.yaml
    
    print_status "Creating persistent volume..."
    kubectl apply -f persistent-volume.yaml
    
    print_status "Creating configmap..."
    kubectl apply -f configmap.yaml
    
    print_status "Deploying TFX pipeline job..."
    kubectl apply -f tfx-pipeline-job.yaml
    
    print_success "Deployment completed!"
}

# Function to monitor deployment
monitor_deployment() {
    print_status "Monitoring deployment..."
    
    # Wait for pod to be created
    print_status "Waiting for pod to be created..."
    timeout=60
    while [[ $timeout -gt 0 ]]; do
        if kubectl get pods -n tfx-pipeline -l job-name=tfx-pipeline-job 2>/dev/null | grep -q tfx-pipeline-job; then
            break
        fi
        sleep 2
        ((timeout-=2))
    done
    
    if [[ $timeout -le 0 ]]; then
        print_error "Timeout waiting for pod creation"
        kubectl describe job tfx-pipeline-job -n tfx-pipeline
        exit 1
    fi
    
    # Get pod name
    POD_NAME=$(kubectl get pods -n tfx-pipeline -l job-name=tfx-pipeline-job -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    print_status "Pod created: $POD_NAME"
    
    # Show pod status
    print_status "Pod status:"
    kubectl get pod $POD_NAME -n tfx-pipeline
    
    # Show events
    print_status "Recent events:"
    kubectl get events -n tfx-pipeline --sort-by='.lastTimestamp' | tail -10
    
    # Follow logs
    print_status "Following pipeline logs (Ctrl+C to stop)..."
    kubectl logs -f $POD_NAME -n tfx-pipeline || true
}

# Function to show deployment status
show_status() {
    print_status "Deployment Status:"
    echo "===================="
    
    print_status "Namespace resources:"
    kubectl get all -n tfx-pipeline
    
    echo ""
    print_status "Job status:"
    kubectl describe job tfx-pipeline-job -n tfx-pipeline
    
    echo ""
    print_status "Pod logs (last 20 lines):"
    POD_NAME=$(kubectl get pods -n tfx-pipeline -l job-name=tfx-pipeline-job -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -n "$POD_NAME" ]]; then
        kubectl logs $POD_NAME -n tfx-pipeline --tail=20
    else
        print_warning "No pod found"
    fi
}

# Main execution
main() {
    print_status "Starting TFX Pipeline Deployment"
    echo "=================================="
    
    # Step 1: Check prerequisites
    check_prerequisites
    
    # Step 2: Build Docker image
    build_docker_image
    
    # Step 3: Deploy to Kubernetes
    deploy_to_kubernetes
    
    # Step 4: Monitor deployment
    echo ""
    print_status "Deployment commands completed. Choose next action:"
    echo "1. Monitor logs (m)"
    echo "2. Show status (s)"
    echo "3. Exit (e)"
    
    read -p "Enter choice [m/s/e]: " choice
    case $choice in
        m|M) monitor_deployment ;;
        s|S) show_status ;;
        e|E) print_success "Deployment script completed" ;;
        *) show_status ;;
    esac
}

# Run main function
main "$@"
