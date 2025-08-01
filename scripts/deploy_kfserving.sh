#!/bin/bash
# KFServing 部署脚本 - 实现在线推理服务
# 适用于 macOS 本地 Kubernetes 环境

set -e

echo "🚀 开始部署 KFServing 在线推理服务..."

# 检查 kubectl 连接
echo "🔍 检查 Kubernetes 集群连接..."
kubectl cluster-info

# 创建命名空间
echo "📦 创建 KFServing 命名空间..."
kubectl create namespace kfserving-system --dry-run=client -o yaml | kubectl apply -f -

# 安装 Istio (KFServing 依赖)
echo "🌐 安装 Istio 服务网格..."
if ! kubectl get namespace istio-system &> /dev/null; then
    # 下载并安装 Istio
    curl -L https://istio.io/downloadIstio | sh -
    cd istio-*
    export PATH=$PWD/bin:$PATH
    istioctl install --set values.defaultRevision=default -y
    kubectl label namespace default istio-injection=enabled
    cd ..
else
    echo "✅ Istio 已安装"
fi

# 安装 Knative Serving (KFServing 依赖)
echo "⚡ 安装 Knative Serving..."
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.8.0/serving-crds.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.8.0/serving-core.yaml

# 配置 Knative 网络
kubectl apply -f https://github.com/knative/net-istio/releases/download/knative-v1.8.0/net-istio.yaml

# 等待 Knative 就绪
echo "⏳ 等待 Knative Serving 就绪..."
kubectl wait --for=condition=Ready pod --all -n knative-serving --timeout=300s

# 安装 KFServing
echo "🤖 安装 KFServing..."
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.10.0/kserve.yaml

# 等待 KFServing 就绪
echo "⏳ 等待 KFServing 就绪..."
kubectl wait --for=condition=Ready pod --all -n kserve-system --timeout=300s

# 创建推理服务配置
echo "📋 创建推理服务配置..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: inferenceservice-config
  namespace: kserve-system
data:
  predictors: |
    {
        "tensorflow": {
            "image": "tensorflow/serving",
            "defaultImageVersion": "2.8.0",
            "defaultGpuImageVersion": "2.8.0-gpu",
            "allowedImageVersions": [
               "1.14.0",
               "1.14.0-gpu",
               "2.8.0",
               "2.8.0-gpu"
            ]
        },
        "sklearn": {
            "image": "kserve/sklearnserver",
            "defaultImageVersion": "v0.10.0"
        },
        "xgboost": {
            "image": "kserve/xgbserver",
            "defaultImageVersion": "v0.10.0"
        }
    }
EOF

echo "✅ KFServing 部署完成！"
echo ""
echo "🎯 验证部署："
echo "kubectl get pods -n kserve-system"
echo "kubectl get pods -n knative-serving"
echo "kubectl get pods -n istio-system"
echo ""
echo "📚 下一步："
echo "1. 部署模型推理服务: kubectl apply -f k8s/inference-service.yaml"
echo "2. 测试推理接口: python scripts/test_inference.py"
echo "3. 查看服务状态: kubectl get inferenceservices"
