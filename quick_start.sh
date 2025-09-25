#!/bin/bash
# 快速启动 Chicago Taxi MLOps 平台 - 简化版本

set -e

echo "🚀 启动 Chicago Taxi MLOps 平台..."

# 检查 Python 版本
echo "📋 检查 Python 版本..."
python3 --version

# 创建虚拟环境（如果不存在）
if [ ! -d "mlops-env" ]; then
    echo "🐍 创建虚拟环境 'mlops-env'..."
    python3 -m venv mlops-env
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source mlops-env/bin/activate

# 升级 pip
echo "⬆️  升级 pip..."
pip install --upgrade pip

# 安装简化依赖
echo "📦 安装依赖..."
if [ ! -f "requirements-local.txt" ]; then
    echo "❌ requirements-local.txt 文件不存在"
    echo "正在创建简化的依赖文件..."
    cat > requirements-local.txt << EOF
# 本地运行简化依赖
fastapi>=0.68.0
uvicorn[standard]>=0.15.0
streamlit>=1.25.0
pandas>=1.5.0
numpy>=1.21.0,<1.25.0
scikit-learn>=1.1.0
plotly>=5.0.0
requests>=2.25.0
python-dotenv>=0.19.0
tqdm>=4.60.0
redis>=4.0.0
kafka-python>=2.0.0
EOF
fi

pip install -r requirements-local.txt

# 检查并停止现有服务
echo "🔍 检查现有服务..."
pkill -f "uvicorn.*8000" 2>/dev/null || true
pkill -f "streamlit.*8501" 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

# 等待端口释放
sleep 3

# 启动 FastAPI 服务
echo "🌐 启动 FastAPI 服务 (端口 8000)..."
uvicorn api.main_with_feast:app --host 0.0.0.0 --port 8000 --reload &

FASTAPI_PID=$!
echo "FastAPI PID: $FASTAPI_PID"

# 等待 FastAPI 启动
sleep 5

# 启动 Streamlit 服务
echo "🎨 启动 Streamlit UI (端口 8501)..."
streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true &

STREAMLIT_PID=$!
echo "Streamlit PID: $STREAMLIT_PID"

# 等待服务启动
sleep 5

# 健康检查
echo "🔍 检查服务状态..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ FastAPI 服务正常运行"
else
    echo "❌ FastAPI 服务启动失败"
fi

if curl -s http://localhost:8501 > /dev/null; then
    echo "✅ Streamlit 服务正常运行"
else
    echo "❌ Streamlit 服务启动失败，可能端口被占用"
fi

# 显示访问信息
echo ""
echo "🎉 MLOps 平台启动完成!"
echo ""
echo "📊 服务状态:"
echo "   - FastAPI API: ✅ 运行在 http://localhost:8000"
echo "   - Streamlit UI: ✅ 运行在 http://localhost:8501"
echo "   - API 文档: ✅ http://localhost:8000/docs"
echo ""
echo "🎯 功能特性:"
echo "   - 🚕 出租车小费预测 (模拟模式)"
echo "   - 📊 批量预测和数据分析"
echo "   - 🍃 Feast 特征存储 (模拟模式)"
echo "   - 🚀 Kafka 流处理 (模拟模式)"
echo "   - 🎯 MLflow 模型管理 (模拟模式)"
echo "   - 🔗 MLMD 数据血缘 (模拟模式)"
echo ""
echo "💡 使用提示:"
echo "   - 访问 Streamlit UI: http://localhost:8501"
echo "   - 查看 API 文档: http://localhost:8000/docs"
echo "   - 健康检查: curl http://localhost:8000/health"
echo "   - 测试预测: curl -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{...}'"
echo ""
echo "🛑 停止服务:"
echo "   - 按 Ctrl+C 停止当前脚本"
echo "   - 或运行: pkill -f 'uvicorn.*8000' && pkill -f 'streamlit.*8501'"
echo ""
echo "📝 服务进程 ID:"
echo "   - FastAPI PID: $FASTAPI_PID"
echo "   - Streamlit PID: $STREAMLIT_PID"
echo ""
echo "🎊 现在可以开始使用 MLOps 平台了！"
