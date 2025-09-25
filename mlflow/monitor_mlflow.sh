#!/bin/bash

# MLflow 服务监控脚本

MLFLOW_URL="http://localhost:5000"

echo "🔍 MLflow 服务监控"
echo "===================="

# 检查服务状态
echo "📊 检查 MLflow 服务状态..."
if curl -s "$MLFLOW_URL/health" > /dev/null 2>&1; then
    echo "✅ MLflow 服务正常运行"
    echo "🌐 UI 地址: $MLFLOW_URL"
else
    echo "❌ MLflow 服务不可访问"
    echo "💡 请检查服务是否启动: ./start_mlflow.sh"
    exit 1
fi

# 检查进程
echo ""
echo "🔍 MLflow 进程信息:"
ps aux | grep "mlflow server" | grep -v grep || echo "❌ 未发现 MLflow 进程"

# 检查端口
echo ""
echo "🔍 端口使用情况:"
lsof -i :5000 || echo "❌ 端口 5000 未被占用"

# 检查数据库
echo ""
echo "🔍 数据库文件:"
if [ -f "mlflow.db" ]; then
    echo "✅ 数据库文件存在: mlflow.db"
    echo "📊 文件大小: $(ls -lh mlflow.db | awk '{print $5}')"
else
    echo "❌ 数据库文件不存在"
fi

# 检查工件目录
echo ""
echo "🔍 工件存储:"
if [ -d "artifacts" ]; then
    echo "✅ 工件目录存在: artifacts/"
    echo "📁 目录大小: $(du -sh artifacts/ | awk '{print $1}')"
    echo "📊 文件数量: $(find artifacts/ -type f | wc -l)"
else
    echo "❌ 工件目录不存在"
fi

echo ""
echo "✅ 监控检查完成"
