#!/bin/bash
# 快速启动 Chicago Taxi MLOps 平台

set -e

echo "🚀 启动 Chicago Taxi MLOps 平台..."

# 检查虚拟环境
if [ ! -d "mlops-env" ]; then
    echo "❌ 虚拟环境不存在，请先运行: ./setup_environment.sh"
    exit 1
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source mlops-env/bin/activate

# 检查并停止现有服务
echo "🔍 检查现有服务..."
pkill -f "uvicorn.*8000" 2>/dev/null || true
pkill -f "streamlit.*8501" 2>/dev/null || true

# 等待端口释放
sleep 2

# 启动 Feast Feature Store 服务
echo "🍃 启动 Feast Feature Store 服务..."
if command -v redis-server &> /dev/null; then
    # 启动 Redis 服务器
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "🔴 启动 Redis 服务器..."
        redis-server --daemonize yes --port 6379
        sleep 2
        echo "✅ Redis 服务器已启动"
    else
        echo "✅ Redis 服务器已在运行"
    fi
    
    # 检查 Redis 连接
    if redis-cli ping | grep -q "PONG"; then
        echo "✅ Redis 连接成功"
    else
        echo "⚠️  Redis 连接失败，Feast 将使用模拟模式"
    fi
    
    # 初始化 Feast 仓库（如果需要）
    if [ ! -f "feast/data/registry.db" ]; then
        echo "🏗️  初始化 Feast 仓库..."
        cd feast
        if command -v feast &> /dev/null; then
            feast apply
            echo "✅ Feast 仓库初始化完成"
        else
            echo "⚠️  Feast 未安装，将使用模拟模式"
        fi
        cd ..
    else
        echo "✅ Feast 仓库已存在"
    fi
    
    # 启动 Feast UI 服务器（后台运行）
    if command -v feast &> /dev/null && ! pgrep -f "feast ui" > /dev/null; then
        echo "🌐 启动 Feast UI 服务器 (端口 8888)..."
        cd feast
        nohup feast ui --host 0.0.0.0 --port 8888 > ../logs/feast_ui.log 2>&1 &
        cd ..
        sleep 2
        echo "✅ Feast UI 已启动: http://localhost:8888"
    fi
else
    echo "⚠️  Redis 未安装，Feast 将使用模拟模式"
    echo "💡 要安装 Redis: brew install redis (macOS) 或 apt-get install redis-server (Linux)"
fi

# 启动 FastAPI 服务
echo "🌐 启动 FastAPI 服务 (端口 8000)..."
python -c "
import uvicorn
from api.main_with_feast import app
uvicorn.run(app, host='0.0.0.0', port=8000)
" &

FASTAPI_PID=$!
echo "FastAPI PID: $FASTAPI_PID"

# 等待 FastAPI 启动
sleep 3

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
    echo "❌ Streamlit 服务启动失败"
fi

# 显示访问信息
echo ""
echo ""
echo "🎉 MLOps 平台启动完成!"
echo ""
echo "📊 服务状态:"
echo "   - FastAPI API: ✅ 运行在 http://localhost:8000"
echo "   - Streamlit UI: ✅ 运行在 http://localhost:8501"
if command -v redis-server &> /dev/null && pgrep -x "redis-server" > /dev/null; then
    echo "   - Redis 服务器: ✅ 运行在 localhost:6379"
else
    echo "   - Redis 服务器: ⚠️  未运行 (使用模拟模式)"
fi
if command -v feast &> /dev/null && pgrep -f "feast ui" > /dev/null; then
    echo "   - Feast UI: ✅ 运行在 http://localhost:8888"
else
    echo "   - Feast UI: ⚠️  未运行 (使用模拟模式)"
fi
echo ""
echo "💡 使用提示:"
echo "   - 访问 Streamlit UI: http://localhost:8501"
echo "   - 查看 API 文档: http://localhost:8000/docs"
echo "   - Feast 特征存储: http://localhost:8888"
echo "   - 健康检查: curl http://localhost:8000/health"
echo ""
echo "🛑 停止服务:"
echo "   - 按 Ctrl+C 停止"
echo "   - 或运行: pkill -f 'uvicorn.*8000' && pkill -f 'streamlit.*8501' && pkill -f 'feast ui' && redis-cli shutdown"
echo ""
echo "📝 服务进程 ID:"
echo "  FastAPI PID: $FASTAPI_PID"
echo "  Streamlit PID: $STREAMLIT_PID"
