#!/bin/bash

# 启动服务端口转发（后台运行）
set -e

MINIKUBE=/opt/homebrew/bin/minikube

echo "🚀 启动服务端口转发..."

# 启动FastAPI服务转发（后台）
echo "启动FastAPI服务转发..."
$MINIKUBE service fastapi-service -n taxi-app > /tmp/fastapi-url.txt 2>&1 &
FASTAPI_PID=$!
echo "FastAPI PID: $FASTAPI_PID"

# 启动Streamlit服务转发（后台）
echo "启动Streamlit服务转发..."
$MINIKUBE service streamlit-service -n taxi-app > /tmp/streamlit-url.txt 2>&1 &
STREAMLIT_PID=$!
echo "Streamlit PID: $STREAMLIT_PID"

# 等待服务启动
sleep 5

# 获取URL
FASTAPI_URL=$(kubectl get svc fastapi-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')
STREAMLIT_URL=$(kubectl get svc streamlit-service -n taxi-app -o jsonpath='{.spec.ports[0].nodePort}')

echo ""
echo "✅ 服务已启动！"
echo ""
echo "访问地址:"
echo "  FastAPI:    http://127.0.0.1:$FASTAPI_URL"
echo "  Streamlit:  http://127.0.0.1:$STREAMLIT_URL"
echo ""
echo "进程ID:"
echo "  FastAPI PID:    $FASTAPI_PID"
echo "  Streamlit PID:  $STREAMLIT_PID"
echo ""
echo "停止服务: kill $FASTAPI_PID $STREAMLIT_PID"
echo ""

# 保存PID到文件
echo "$FASTAPI_PID" > /tmp/fastapi-service.pid
echo "$STREAMLIT_PID" > /tmp/streamlit-service.pid

echo "服务正在后台运行..."
