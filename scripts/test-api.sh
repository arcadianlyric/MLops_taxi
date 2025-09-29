#!/bin/bash

# 测试API脚本 - 使用kubectl port-forward
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🧪 测试Taxi Tip预测API${NC}"
echo ""

# 使用kubectl port-forward
echo -e "${BLUE}启动端口转发...${NC}"
kubectl port-forward -n taxi-app svc/fastapi-service 8000:8000 > /dev/null 2>&1 &
PF_PID=$!
echo "Port-forward PID: $PF_PID"

sleep 3

API_URL="http://localhost:8000"

# 测试健康检查
echo -e "${BLUE}测试1: 健康检查${NC}"
curl -s ${API_URL}/health | python3 -m json.tool
echo ""

# 测试Tip预测
echo -e "${BLUE}测试2: Tip预测${NC}"
TEST_DATA='{
    "trip_miles": 5.2,
    "trip_seconds": 900,
    "fare": 12.5,
    "pickup_latitude": 41.8781,
    "pickup_longitude": -87.6298,
    "dropoff_latitude": 41.8881,
    "dropoff_longitude": -87.6198,
    "pickup_hour": 14,
    "pickup_day_of_week": 1,
    "trip_start_day": 15,
    "trip_start_month": 6,
    "pickup_community_area": 8,
    "dropoff_community_area": 24,
    "pickup_census_tract": 170301,
    "dropoff_census_tract": 170401,
    "payment_type": "Credit Card",
    "company": "Flash Cab",
    "passenger_count": 1
}'

RESPONSE=$(curl -s -X POST ${API_URL}/predict \
    -H "Content-Type: application/json" \
    -d "$TEST_DATA")

echo "$RESPONSE" | python3 -m json.tool
echo ""

TIP=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['predicted_tip'])" 2>/dev/null)
echo -e "${GREEN}💰 预测的Tip金额: \$${TIP}${NC}"
echo ""

# 清理
kill $PF_PID 2>/dev/null

echo -e "${GREEN}✅ 测试完成！${NC}"
echo ""
echo "访问UI: kubectl port-forward -n taxi-app svc/streamlit-service 8501:8501"
echo "然后打开: http://localhost:8501"
