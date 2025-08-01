#!/bin/bash
# Kafka Kraft 流处理部署脚本
# 在 macOS 上快速部署 Chicago Taxi 实时流处理系统

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}🌊 部署 Kafka Kraft 实时流处理系统${NC}"
echo "================================================"

# 检查 Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${RED}❌ 未安装 Homebrew，请先安装: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
    exit 1
fi

# 安装 Kafka
echo -e "${BLUE}📦 安装 Kafka...${NC}"
if ! command -v kafka-server-start &> /dev/null; then
    brew install kafka
    echo -e "${GREEN}✅ Kafka 安装完成${NC}"
else
    echo -e "${GREEN}✅ Kafka 已安装${NC}"
fi

# 创建 Kafka 配置目录
KAFKA_CONFIG_DIR="$PROJECT_ROOT/config/kafka"
mkdir -p "$KAFKA_CONFIG_DIR"

# 生成 Kafka Kraft 配置文件
echo -e "${BLUE}⚙️ 生成 Kafka Kraft 配置...${NC}"

cat > "$KAFKA_CONFIG_DIR/kraft-server.properties" << 'EOF'
# Kafka Kraft 模式配置
process.roles=broker,controller
node.id=1
controller.quorum.voters=1@localhost:9093
listeners=PLAINTEXT://localhost:9092,CONTROLLER://localhost:9093
inter.broker.listener.name=PLAINTEXT
advertised.listeners=PLAINTEXT://localhost:9092
controller.listener.names=CONTROLLER
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT

# 日志目录
log.dirs=/tmp/kafka-kraft-logs

# Topic 配置
num.network.threads=3
num.io.threads=8
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# 日志保留策略
log.retention.hours=168
log.retention.check.interval.ms=300000
log.segment.bytes=1073741824

# Zookeeper 连接（Kraft 模式不需要）
# zookeeper.connect=localhost:2181
# zookeeper.connection.timeout.ms=18000

# 其他配置
group.initial.rebalance.delay.ms=0
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
EOF

# 生成集群 UUID
echo -e "${BLUE}🔑 生成集群 UUID...${NC}"
CLUSTER_UUID=$(kafka-storage random-uuid)
echo "集群 UUID: $CLUSTER_UUID"

# 格式化存储目录
echo -e "${BLUE}💾 格式化存储目录...${NC}"
kafka-storage format -t "$CLUSTER_UUID" -c "$KAFKA_CONFIG_DIR/kraft-server.properties"

# 创建启动脚本
cat > "$PROJECT_ROOT/scripts/start_kafka.sh" << EOF
#!/bin/bash
# 启动 Kafka Kraft 服务器

cd "$PROJECT_ROOT"
echo "🚀 启动 Kafka Kraft 服务器..."
kafka-server-start config/kafka/kraft-server.properties
EOF

chmod +x "$PROJECT_ROOT/scripts/start_kafka.sh"

# 创建停止脚本
cat > "$PROJECT_ROOT/scripts/stop_kafka.sh" << EOF
#!/bin/bash
# 停止 Kafka 服务器

echo "⏹️ 停止 Kafka 服务器..."
kafka-server-stop
echo "✅ Kafka 服务器已停止"
EOF

chmod +x "$PROJECT_ROOT/scripts/stop_kafka.sh"

# 创建 Topic 创建脚本
cat > "$PROJECT_ROOT/scripts/create_kafka_topics.sh" << 'EOF'
#!/bin/bash
# 创建 Kafka Topics

KAFKA_SERVER="localhost:9092"

echo "📋 创建 Kafka Topics..."

# 原始数据 Topics
kafka-topics --create --topic taxi-rides-raw --bootstrap-server $KAFKA_SERVER --partitions 6 --replication-factor 1 --if-not-exists
kafka-topics --create --topic taxi-gps-stream --bootstrap-server $KAFKA_SERVER --partitions 12 --replication-factor 1 --if-not-exists

# 特征数据 Topics
kafka-topics --create --topic taxi-features-realtime --bootstrap-server $KAFKA_SERVER --partitions 6 --replication-factor 1 --if-not-exists
kafka-topics --create --topic taxi-features-aggregated --bootstrap-server $KAFKA_SERVER --partitions 3 --replication-factor 1 --if-not-exists

# 预测结果 Topics
kafka-topics --create --topic taxi-predictions --bootstrap-server $KAFKA_SERVER --partitions 6 --replication-factor 1 --if-not-exists
kafka-topics --create --topic taxi-anomalies --bootstrap-server $KAFKA_SERVER --partitions 3 --replication-factor 1 --if-not-exists

# 监控告警 Topics
kafka-topics --create --topic model-metrics --bootstrap-server $KAFKA_SERVER --partitions 3 --replication-factor 1 --if-not-exists
kafka-topics --create --topic data-quality-alerts --bootstrap-server $KAFKA_SERVER --partitions 3 --replication-factor 1 --if-not-exists

echo "✅ 所有 Topics 创建完成"

# 列出所有 Topics
echo "📋 当前 Topics 列表:"
kafka-topics --list --bootstrap-server $KAFKA_SERVER
EOF

chmod +x "$PROJECT_ROOT/scripts/create_kafka_topics.sh"

# 安装 Python Kafka 依赖
echo -e "${BLUE}🐍 安装 Python Kafka 依赖...${NC}"
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️  未检测到虚拟环境，尝试激活...${NC}"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
    else
        echo -e "${RED}❌ 未找到虚拟环境，请先创建: python -m venv venv && source venv/bin/activate${NC}"
        exit 1
    fi
fi

pip install kafka-python requests asyncio

# 创建流处理启动脚本
cat > "$PROJECT_ROOT/scripts/start_stream_processing.py" << 'EOF'
#!/usr/bin/env python3
"""
启动完整的流处理系统
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def start_kafka_server():
    """启动 Kafka 服务器"""
    print("🚀 启动 Kafka 服务器...")
    kafka_start_script = project_root / "scripts" / "start_kafka.sh"
    subprocess.run([str(kafka_start_script)], check=True)

def create_topics():
    """创建 Kafka Topics"""
    print("📋 创建 Kafka Topics...")
    time.sleep(5)  # 等待 Kafka 启动
    topics_script = project_root / "scripts" / "create_kafka_topics.sh"
    subprocess.run([str(topics_script)], check=True)

def start_stream_processors():
    """启动流处理器"""
    print("⚙️ 启动流处理器...")
    
    from streaming.kafka_stream_processor import KafkaStreamProcessor
    
    processor = KafkaStreamProcessor()
    
    # 启动所有处理器
    threads = processor.start_all_processors()
    
    # 生成一些初始数据
    print("🎲 生成初始测试数据...")
    processor.simulate_taxi_rides(10)
    
    return processor, threads

def main():
    """主函数"""
    print("🌊 启动 Chicago Taxi 实时流处理系统")
    print("=" * 50)
    
    try:
        # 1. 启动 Kafka（在后台）
        kafka_thread = threading.Thread(target=start_kafka_server)
        kafka_thread.daemon = True
        kafka_thread.start()
        
        # 2. 创建 Topics
        create_topics()
        
        # 3. 启动流处理器
        processor, threads = start_stream_processors()
        
        print("✅ 流处理系统启动完成！")
        print("📊 访问 Streamlit UI: http://localhost:8501")
        print("🔗 FastAPI 文档: http://localhost:8000/docs")
        print("按 Ctrl+C 停止系统")
        
        # 保持运行
        for thread in threads:
            thread.join()
            
    except KeyboardInterrupt:
        print("\n⏹️ 停止流处理系统...")
        if 'processor' in locals():
            processor.close()
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()
EOF

chmod +x "$PROJECT_ROOT/scripts/start_stream_processing.py"

# 创建完整的一键启动脚本
cat > "$PROJECT_ROOT/scripts/start_full_streaming_system.sh" << 'EOF'
#!/bin/bash
# 一键启动完整的流处理系统

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🌊 启动完整的 Chicago Taxi 流处理系统"
echo "================================================"

# 激活虚拟环境
if [[ "$VIRTUAL_ENV" == "" ]]; then
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo "✅ 虚拟环境已激活"
    fi
fi

# 启动服务的函数
start_service() {
    local service_name=$1
    local command=$2
    local port=$3
    
    echo "🚀 启动 $service_name..."
    
    # 检查端口是否被占用
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "⚠️  端口 $port 已被占用，跳过 $service_name"
        return
    fi
    
    # 在后台启动服务
    nohup $command > logs/${service_name}.log 2>&1 &
    echo $! > pids/${service_name}.pid
    
    sleep 2
    echo "✅ $service_name 已启动"
}

# 创建日志和 PID 目录
mkdir -p logs pids

# 1. 启动 FastAPI 服务
start_service "fastapi" "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000" 8000

# 2. 启动 Kafka 服务器
echo "🚀 启动 Kafka 服务器..."
nohup ./scripts/start_kafka.sh > logs/kafka.log 2>&1 &
echo $! > pids/kafka.pid
sleep 5

# 3. 创建 Kafka Topics
./scripts/create_kafka_topics.sh

# 4. 启动流处理器
echo "⚙️ 启动流处理器..."
nohup python scripts/start_stream_processing.py > logs/stream_processing.log 2>&1 &
echo $! > pids/stream_processing.pid

# 5. 启动 Streamlit UI
start_service "streamlit" "python -m streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true" 8501

echo ""
echo "🎉 系统启动完成！"
echo "📊 Streamlit UI: http://localhost:8501"
echo "🔗 FastAPI 文档: http://localhost:8000/docs"
echo "🌊 流处理监控: 在 Streamlit UI 中查看实时数据流"
echo ""
echo "📋 管理命令:"
echo "  停止系统: ./scripts/stop_full_streaming_system.sh"
echo "  查看日志: tail -f logs/*.log"
echo "  查看进程: ps -p \$(cat pids/*.pid)"
echo ""
echo "按 Ctrl+C 或运行停止脚本来停止系统"

# 等待用户中断
trap 'echo "正在停止系统..."; ./scripts/stop_full_streaming_system.sh; exit' INT
while true; do
    sleep 1
done
EOF

chmod +x "$PROJECT_ROOT/scripts/start_full_streaming_system.sh"

# 创建停止脚本
cat > "$PROJECT_ROOT/scripts/stop_full_streaming_system.sh" << 'EOF'
#!/bin/bash
# 停止完整的流处理系统

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "⏹️ 停止 Chicago Taxi 流处理系统"
echo "================================================"

# 停止所有服务
if [ -d "pids" ]; then
    for pid_file in pids/*.pid; do
        if [ -f "$pid_file" ]; then
            service_name=$(basename "$pid_file" .pid)
            pid=$(cat "$pid_file")
            
            if ps -p $pid > /dev/null; then
                echo "⏹️ 停止 $service_name (PID: $pid)..."
                kill $pid
                sleep 2
                
                # 强制杀死如果还在运行
                if ps -p $pid > /dev/null; then
                    kill -9 $pid
                fi
            fi
            
            rm "$pid_file"
        fi
    done
fi

# 停止 Kafka
./scripts/stop_kafka.sh

# 清理
pkill -f "streamlit"
pkill -f "uvicorn"
pkill -f "kafka"

echo "✅ 所有服务已停止"
EOF

chmod +x "$PROJECT_ROOT/scripts/stop_full_streaming_system.sh"

echo -e "${GREEN}✅ Kafka Kraft 流处理系统部署完成！${NC}"
echo ""
echo -e "${BLUE}🚀 快速启动命令:${NC}"
echo "  完整系统: ./scripts/start_full_streaming_system.sh"
echo "  仅 Kafka: ./scripts/start_kafka.sh"
echo "  创建 Topics: ./scripts/create_kafka_topics.sh"
echo ""
echo -e "${BLUE}⏹️ 停止命令:${NC}"
echo "  停止系统: ./scripts/stop_full_streaming_system.sh"
echo "  停止 Kafka: ./scripts/stop_kafka.sh"
echo ""
echo -e "${YELLOW}📋 下一步:${NC}"
echo "1. 运行: ./scripts/start_full_streaming_system.sh"
echo "2. 访问: http://localhost:8501 查看实时流处理"
echo "3. 在 Streamlit UI 中生成模拟数据测试流处理"
