#!/bin/bash
"""
启动 Feast Feature Store 相关服务
包括 Redis 和 Feast 服务器
"""

set -e

echo "🍃 Starting Feast Feature Store Services..."

# 检查是否安装了 Redis
if ! command -v redis-server &> /dev/null; then
    echo "❌ Redis not found. Installing Redis..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install redis
        else
            echo "Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get update
        sudo apt-get install -y redis-server
    else
        echo "Unsupported OS. Please install Redis manually."
        exit 1
    fi
fi

# 启动 Redis 服务器
echo "🔴 Starting Redis server..."
if pgrep -x "redis-server" > /dev/null; then
    echo "✅ Redis is already running"
else
    redis-server --daemonize yes --port 6379
    sleep 2
    echo "✅ Redis server started on port 6379"
fi

# 检查 Redis 连接
echo "🔍 Testing Redis connection..."
if redis-cli ping | grep -q "PONG"; then
    echo "✅ Redis connection successful"
else
    echo "❌ Redis connection failed"
    exit 1
fi

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
elif [ -f "mlops-env/bin/activate" ]; then
    source mlops-env/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  No virtual environment found, using system Python"
fi

# 检查 Feast 安装
echo "🔍 Checking Feast installation..."
if python -c "import feast" 2>/dev/null; then
    echo "✅ Feast is installed"
else
    echo "📦 Installing Feast..."
    pip install feast[redis]
fi

# 进入 Feast 目录
cd feast

# 初始化 Feast 仓库（如果需要）
if [ ! -f "data/registry.db" ]; then
    echo "🏗️  Initializing Feast repository..."
    feast apply
    echo "✅ Feast repository initialized"
else
    echo "✅ Feast repository already exists"
fi

# 启动 Feast UI 服务器（可选）
echo "🌐 Starting Feast UI server..."
if pgrep -f "feast ui" > /dev/null; then
    echo "✅ Feast UI is already running"
else
    nohup feast ui --host 0.0.0.0 --port 8888 > ../logs/feast_ui.log 2>&1 &
    sleep 3
    echo "✅ Feast UI started on http://localhost:8888"
fi

# 返回项目根目录
cd ..

echo ""
echo "🎉 Feast Feature Store services started successfully!"
echo ""
echo "📊 Service Status:"
echo "   - Redis Server: ✅ Running on port 6379"
echo "   - Feast UI: ✅ Running on http://localhost:8888"
echo "   - Feature Store: ✅ Ready for use"
echo ""
echo "💡 Tips:"
echo "   - Access Feast UI at: http://localhost:8888"
echo "   - Check Redis: redis-cli ping"
echo "   - Stop Redis: redis-cli shutdown"
echo "   - View logs: tail -f logs/feast_ui.log"
echo ""
