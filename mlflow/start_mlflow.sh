#!/bin/bash

# MLflow 服务启动脚本

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
MLFLOW_DIR="${PROJECT_ROOT}/mlflow"

# 激活虚拟环境
source "$VENV_PATH/bin/activate"

# 切换到 MLflow 目录
cd "$MLFLOW_DIR"

# 设置环境变量
export MLFLOW_BACKEND_STORE_URI="sqlite:///mlflow.db"
export MLFLOW_DEFAULT_ARTIFACT_ROOT="./artifacts"

echo "🚀 启动 MLflow 服务..."
echo "📊 Tracking UI: http://localhost:5000"
echo "📁 Backend Store: $MLFLOW_BACKEND_STORE_URI"
echo "📦 Artifact Root: $MLFLOW_DEFAULT_ARTIFACT_ROOT"
echo ""

# 启动 MLflow 服务
mlflow server \
    --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" \
    --default-artifact-root "$MLFLOW_DEFAULT_ARTIFACT_ROOT" \
    --host 0.0.0.0 \
    --port 5000 \
    --serve-artifacts \
    --workers 1
