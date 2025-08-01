#!/bin/bash
set -e

# Kubeflow 部署脚本
# 部署 Kubeflow Pipelines 和相关组件

echo "🚀 开始部署 Kubeflow"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Kubeflow 版本
KUBEFLOW_VERSION="1.8.0"
KFP_VERSION="2.0.5"

# 检查 Kubernetes 集群
check_cluster() {
    echo -e "${BLUE}🔍 检查 Kubernetes 集群...${NC}"
    
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ 无法连接到 Kubernetes 集群${NC}"
        echo "请先运行: ./scripts/setup_kubernetes.sh"
        exit 1
    fi
    
    # 检查集群资源
    echo -e "${BLUE}📊 检查集群资源...${NC}"
    kubectl top nodes 2>/dev/null || echo -e "${YELLOW}⚠️  Metrics Server 未启用，某些功能可能受限${NC}"
    
    echo -e "${GREEN}✅ Kubernetes 集群连接正常${NC}"
}

# 部署 Kubeflow Pipelines
deploy_kubeflow_pipelines() {
    echo -e "${BLUE}🔧 部署 Kubeflow Pipelines...${NC}"
    
    # 下载 Kubeflow Pipelines 清单
    echo -e "${BLUE}📥 下载 Kubeflow Pipelines 清单...${NC}"
    
    # 创建临时目录
    mkdir -p /tmp/kubeflow
    cd /tmp/kubeflow
    
    # 下载 KFP 清单文件
    curl -L -o kfp-standalone.yaml "https://github.com/kubeflow/pipelines/releases/download/${KFP_VERSION}/kubeflow-pipelines-standalone.yaml"
    
    # 应用清单
    echo -e "${BLUE}🚀 应用 Kubeflow Pipelines 清单...${NC}"
    kubectl apply -f kfp-standalone.yaml
    
    echo -e "${GREEN}✅ Kubeflow Pipelines 部署完成${NC}"
}

# 部署 KFServing (KServe)
deploy_kfserving() {
    echo -e "${BLUE}🤖 部署 KFServing (KServe)...${NC}"
    
    # 安装 Istio (KServe 依赖)
    echo -e "${BLUE}🌐 安装 Istio...${NC}"
    
    # 下载 Istio
    curl -L https://istio.io/downloadIstio | sh -
    export PATH="$PWD/istio-*/bin:$PATH"
    
    # 安装 Istio
    istioctl install --set values.defaultRevision=default -y
    kubectl label namespace default istio-injection=enabled --overwrite
    
    # 安装 Knative Serving
    echo -e "${BLUE}🔧 安装 Knative Serving...${NC}"
    kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.11.0/serving-crds.yaml
    kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.11.0/serving-core.yaml
    kubectl apply -f https://github.com/knative/net-istio/releases/download/knative-v1.11.0/net-istio.yaml
    
    # 安装 KServe
    echo -e "${BLUE}🤖 安装 KServe...${NC}"
    kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml
    
    echo -e "${GREEN}✅ KFServing (KServe) 部署完成${NC}"
}

# 创建 MLOps 相关的 Kubernetes 资源
create_mlops_resources() {
    echo -e "${BLUE}🔧 创建 MLOps 相关资源...${NC}"
    
    # 创建 ConfigMap 用于 TFX Pipeline 配置
    cat > /tmp/tfx-config.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: tfx-pipeline-config
  namespace: kubeflow
data:
  pipeline_name: "taxi_kubeflow_pipeline"
  pipeline_root: "/tmp/tfx"
  data_root: "/tmp/taxi_data"
  module_file: "/tmp/taxi_utils_native_keras.py"
  serving_model_dir: "/tmp/serving_model/taxi_model"
  metadata_path: "/tmp/tfx/metadata.db"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tfx-pipeline-pvc
  namespace: kubeflow
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF

    kubectl apply -f /tmp/tfx-config.yaml
    
    # 创建 MLOps API 部署
    cat > /tmp/mlops-api-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlops-api
  namespace: mlops-system
  labels:
    app: mlops-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mlops-api
  template:
    metadata:
      labels:
        app: mlops-api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: mlops-api
        image: python:3.9-slim
        ports:
        - containerPort: 8000
        env:
        - name: PYTHONPATH
          value: "/app"
        command: ["/bin/bash"]
        args: ["-c", "pip install fastapi uvicorn pandas numpy requests && python -m uvicorn api.test_main:app --host 0.0.0.0 --port 8000"]
        volumeMounts:
        - name: app-code
          mountPath: /app
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: app-code
        hostPath:
          path: /Users/yc/Documents/GitHub/tech_cs/projects/MLops/MLops_test
          type: Directory
---
apiVersion: v1
kind: Service
metadata:
  name: mlops-api-service
  namespace: mlops-system
  labels:
    app: mlops-api
spec:
  selector:
    app: mlops-api
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  type: ClusterIP
EOF

    kubectl apply -f /tmp/mlops-api-deployment.yaml
    
    echo -e "${GREEN}✅ MLOps 资源创建完成${NC}"
}

# 创建端口转发脚本
create_kubeflow_port_forward() {
    echo -e "${BLUE}🔗 创建 Kubeflow 端口转发脚本...${NC}"
    
    cat > scripts/port_forward_kubeflow.sh << 'EOF'
#!/bin/bash

# Kubeflow 服务端口转发脚本

echo "🚀 启动 Kubeflow 服务端口转发..."

# 等待 Kubeflow Pipelines 就绪
echo "⏳ 等待 Kubeflow Pipelines 就绪..."
kubectl wait --for=condition=ready pod -l app=ml-pipeline -n kubeflow --timeout=300s

# 后台启动端口转发
kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80 &
KFP_UI_PID=$!

kubectl port-forward -n kubeflow svc/ml-pipeline 8888:8888 &
KFP_API_PID=$!

kubectl port-forward -n mlops-system svc/mlops-api-service 8000:8000 &
MLOPS_API_PID=$!

echo "🔧 Kubeflow 服务访问地址:"
echo "  Kubeflow Pipelines UI: http://localhost:8080"
echo "  Kubeflow Pipelines API: http://localhost:8888"
echo "  MLOps API: http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止端口转发"

# 等待中断信号
trap 'kill $KFP_UI_PID $KFP_API_PID $MLOPS_API_PID; exit' INT
wait
EOF

    chmod +x scripts/port_forward_kubeflow.sh
    echo -e "${GREEN}✅ Kubeflow 端口转发脚本创建完成${NC}"
}

# 验证 Kubeflow 部署
verify_kubeflow_deployment() {
    echo -e "${BLUE}🔍 验证 Kubeflow 部署...${NC}"
    
    # 检查 Kubeflow 命名空间的 Pod
    echo -e "${BLUE}📦 检查 Kubeflow Pod 状态:${NC}"
    kubectl get pods -n kubeflow
    
    # 检查 MLOps 系统 Pod
    echo -e "${BLUE}📦 检查 MLOps 系统 Pod 状态:${NC}"
    kubectl get pods -n mlops-system
    
    # 检查服务状态
    echo -e "${BLUE}🔗 检查服务状态:${NC}"
    kubectl get svc -n kubeflow
    kubectl get svc -n mlops-system
    
    echo -e "${GREEN}✅ Kubeflow 部署验证完成${NC}"
}

# 创建 TFX Pipeline 部署脚本
create_tfx_pipeline_deploy() {
    echo -e "${BLUE}📋 创建 TFX Pipeline 部署脚本...${NC}"
    
    cat > scripts/deploy_tfx_pipeline.py << 'EOF'
#!/usr/bin/env python3
"""
TFX Pipeline 部署到 Kubeflow Pipelines
"""

import os
import sys
sys.path.append('/Users/yc/Documents/GitHub/tech_cs/projects/MLops/MLops_test')

from pipelines.taxi_kubeflow_pipeline import TaxiKubeflowPipeline
import kfp

def deploy_pipeline():
    """部署 TFX Pipeline 到 Kubeflow"""
    
    # Kubeflow Pipelines 客户端
    client = kfp.Client(host='http://localhost:8888')
    
    # 创建 Pipeline 实例
    pipeline = TaxiKubeflowPipeline(
        pipeline_name='taxi_kubeflow_pipeline',
        pipeline_root='/tmp/tfx',
        data_root='/tmp/taxi_data',
        module_file='/tmp/taxi_utils_native_keras.py',
        serving_model_dir='/tmp/serving_model/taxi_model'
    )
    
    # 编译 Pipeline
    pipeline_package_path = '/tmp/taxi_kubeflow_pipeline.yaml'
    pipeline.compile(pipeline_package_path)
    
    # 上传并创建 Pipeline
    kfp_pipeline = client.upload_pipeline(
        pipeline_package_path=pipeline_package_path,
        pipeline_name='taxi_kubeflow_pipeline'
    )
    
    print(f"✅ Pipeline 部署成功: {kfp_pipeline.id}")
    
    # 创建实验
    experiment = client.create_experiment('taxi_experiment')
    print(f"✅ 实验创建成功: {experiment.id}")
    
    # 运行 Pipeline
    run = client.run_pipeline(
        experiment_id=experiment.id,
        job_name='taxi_pipeline_run',
        pipeline_id=kfp_pipeline.id
    )
    
    print(f"✅ Pipeline 运行启动: {run.id}")
    print(f"🔗 查看运行状态: http://localhost:8080/#/runs/details/{run.id}")

if __name__ == "__main__":
    deploy_pipeline()
EOF

    chmod +x scripts/deploy_tfx_pipeline.py
    echo -e "${GREEN}✅ TFX Pipeline 部署脚本创建完成${NC}"
}

# 主函数
main() {
    echo "=" * 60
    echo -e "${BLUE}🎯 Kubeflow 部署${NC}"
    echo "=" * 60
    
    check_cluster
    deploy_kubeflow_pipelines
    # deploy_kfserving  # 可选：如果需要模型服务功能
    create_mlops_resources
    create_kubeflow_port_forward
    create_tfx_pipeline_deploy
    verify_kubeflow_deployment
    
    echo -e "${GREEN}🎉 Kubeflow 部署完成！${NC}"
    echo ""
    echo -e "${BLUE}📋 下一步操作:${NC}"
    echo "1. 启动端口转发: ./scripts/port_forward_kubeflow.sh"
    echo "2. 访问 Kubeflow UI: http://localhost:8080"
    echo "3. 部署 TFX Pipeline: ./mlops-env/bin/python scripts/deploy_tfx_pipeline.py"
    echo "4. 启动完整系统: ./scripts/deploy_complete_mlops.sh"
}

# 运行主函数
main "$@"
