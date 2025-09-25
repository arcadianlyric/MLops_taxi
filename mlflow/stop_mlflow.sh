#!/bin/bash

# MLflow 服务停止脚本

echo "🛑 停止 MLflow 服务..."

# 查找并终止 MLflow 进程
MLFLOW_PID=$(ps aux | grep "mlflow server" | grep -v grep | awk '{print $2}')

if [ -n "$MLFLOW_PID" ]; then
    echo "📋 发现 MLflow 进程: $MLFLOW_PID"
    kill -TERM $MLFLOW_PID
    sleep 2
    
    # 检查进程是否还在运行
    if ps -p $MLFLOW_PID > /dev/null; then
        echo "⚠️  进程仍在运行，强制终止..."
        kill -KILL $MLFLOW_PID
    fi
    
    echo "✅ MLflow 服务已停止"
else
    echo "ℹ️  未发现运行中的 MLflow 服务"
fi
