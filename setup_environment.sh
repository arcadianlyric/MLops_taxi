#!/bin/bash
# MLOps 平台环境设置脚本 - macOS
# 创建虚拟环境并安装所有依赖

set -e

echo "🚀 开始设置 MLOps 平台环境..."

# 检查 Python 版本
echo "📋 检查 Python 版本..."
python3 --version

# 创建虚拟环境
echo "🐍 创建虚拟环境 'mlops-env'..."
if [ -d "mlops-env" ]; then
    echo "⚠️  虚拟环境已存在，删除旧环境..."
    rm -rf mlops-env
fi

python3 -m venv mlops-env

# 激活虚拟环境
echo "✅ 激活虚拟环境..."
source mlops-env/bin/activate

# 升级 pip
echo "⬆️  升级 pip..."
pip install --upgrade pip

# 安装基础依赖
echo "📦 安装基础依赖..."
pip install wheel setuptools

# 安装主要依赖
echo "🔧 安装 MLOps 平台依赖..."
pip install -r requirements.txt

# 验证关键组件安装
echo "🔍 验证关键组件安装..."
python -c "import tfx; print(f'TFX 版本: {tfx.__version__}')"
python -c "import kfp; print(f'Kubeflow Pipelines 版本: {kfp.__version__}')"
python -c "import feast; print(f'Feast 版本: {feast.__version__}')"
python -c "import streamlit; print(f'Streamlit 版本: {streamlit.__version__}')"
python -c "import fastapi; print(f'FastAPI 版本: {fastapi.__version__}')"

echo "✅ 环境设置完成！"
echo ""
echo "🎯 使用说明："
echo "1. 激活环境: source mlops-env/bin/activate"
echo "2. 启动 Streamlit UI: streamlit run ui/streamlit_app.py"
echo "3. 启动 FastAPI 服务: uvicorn api.main:app --reload"
echo "4. 部署 Kubeflow: ./scripts/install_kubeflow.sh"
echo ""
echo "📚 下一步："
echo "- 确保 Docker Desktop 已启动并启用 Kubernetes"
echo "- 运行 ./scripts/setup_k8s_infrastructure.sh 部署基础设施"
echo "- 运行 ./scripts/deploy_kfserving.sh 部署模型服务"
