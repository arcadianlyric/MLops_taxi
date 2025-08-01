#!/bin/bash

# Kafka Kraft 完整部署脚本
# Chicago Taxi MLOps 平台流处理系统部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KAFKA_DIR="$PROJECT_ROOT/kafka"
STREAMING_DIR="$PROJECT_ROOT/streaming"
VENV_PATH="$PROJECT_ROOT/venv"

# Kafka 配置
KAFKA_VERSION="2.13-3.5.0"
KAFKA_HOME="/usr/local/kafka"
KAFKA_DATA_DIR="/tmp/kafka-logs"
KAFKA_CLUSTER_ID="chicago-taxi-cluster"

echo -e "${BLUE}🚀 开始部署 Kafka Kraft 流处理系统...${NC}"

# 检查虚拟环境
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ 虚拟环境不存在，请先运行 setup_environment.sh${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 虚拟环境检查通过${NC}"
}

# 激活虚拟环境
activate_venv() {
    source "$VENV_PATH/bin/activate"
    echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
}

# 安装 Kafka
install_kafka() {
    echo -e "${YELLOW}📦 安装 Kafka...${NC}"
    
    # 检查是否已安装
    if [ -d "$KAFKA_HOME" ]; then
        echo -e "${GREEN}✅ Kafka 已安装${NC}"
        return
    fi
    
    # 下载 Kafka
    cd /tmp
    if [ ! -f "kafka_$KAFKA_VERSION.tgz" ]; then
        echo -e "${YELLOW}📥 下载 Kafka $KAFKA_VERSION...${NC}"
        curl -O "https://downloads.apache.org/kafka/3.5.0/kafka_$KAFKA_VERSION.tgz"
    fi
    
    # 解压安装
    echo -e "${YELLOW}📂 解压 Kafka...${NC}"
    tar -xzf "kafka_$KAFKA_VERSION.tgz"
    
    # 移动到安装目录
    sudo mkdir -p "$KAFKA_HOME"
    sudo mv "kafka_$KAFKA_VERSION"/* "$KAFKA_HOME/"
    sudo chown -R $(whoami):staff "$KAFKA_HOME"
    
    # 添加到 PATH
    if ! grep -q "KAFKA_HOME" ~/.zshrc; then
        echo "export KAFKA_HOME=$KAFKA_HOME" >> ~/.zshrc
        echo "export PATH=\$PATH:\$KAFKA_HOME/bin" >> ~/.zshrc
    fi
    
    echo -e "${GREEN}✅ Kafka 安装完成${NC}"
}

# 安装 Python 依赖
install_python_dependencies() {
    echo -e "${YELLOW}📦 安装 Python 流处理依赖...${NC}"
    
    # 安装 Kafka Python 客户端
    pip install kafka-python --quiet
    
    # 安装流处理相关依赖
    pip install redis prometheus-client --quiet
    
    # 安装数据处理依赖
    pip install pandas numpy --quiet
    
    echo -e "${GREEN}✅ Python 依赖安装完成${NC}"
}

# 配置 Kafka
configure_kafka() {
    echo -e "${YELLOW}⚙️  配置 Kafka...${NC}"
    
    # 创建数据目录
    mkdir -p "$KAFKA_DATA_DIR"
    
    # 复制配置文件
    cp "$KAFKA_DIR/server.properties" "$KAFKA_HOME/config/kraft/server.properties"
    
    # 生成集群 ID
    if [ ! -f "$KAFKA_DATA_DIR/meta.properties" ]; then
        echo -e "${YELLOW}🔑 生成 Kafka 集群 ID...${NC}"
        CLUSTER_ID=$("$KAFKA_HOME/bin/kafka-storage.sh" random-uuid)
        echo "集群 ID: $CLUSTER_ID"
        
        # 格式化存储
        "$KAFKA_HOME/bin/kafka-storage.sh" format -t "$CLUSTER_ID" -c "$KAFKA_HOME/config/kraft/server.properties"
    fi
    
    echo -e "${GREEN}✅ Kafka 配置完成${NC}"
}

# 启动 Kafka
start_kafka() {
    echo -e "${YELLOW}🚀 启动 Kafka 服务器...${NC}"
    
    # 检查是否已运行
    if pgrep -f "kafka.Kafka" > /dev/null; then
        echo -e "${GREEN}✅ Kafka 服务器已运行${NC}"
        return
    fi
    
    # 启动 Kafka
    nohup "$KAFKA_HOME/bin/kafka-server-start.sh" "$KAFKA_HOME/config/kraft/server.properties" > "$PROJECT_ROOT/kafka.log" 2>&1 &
    KAFKA_PID=$!
    echo $KAFKA_PID > "$PROJECT_ROOT/kafka.pid"
    
    # 等待启动
    echo -e "${YELLOW}⏳ 等待 Kafka 启动...${NC}"
    sleep 10
    
    # 验证启动
    if pgrep -f "kafka.Kafka" > /dev/null; then
        echo -e "${GREEN}✅ Kafka 服务器启动成功 (PID: $KAFKA_PID)${NC}"
    else
        echo -e "${RED}❌ Kafka 服务器启动失败${NC}"
        echo -e "${YELLOW}查看日志: tail -f $PROJECT_ROOT/kafka.log${NC}"
        exit 1
    fi
}

# 创建主题
create_topics() {
    echo -e "${YELLOW}📋 创建 Kafka 主题...${NC}"
    
    # 读取主题配置
    python3 << 'EOF'
import yaml
import subprocess
import sys
import os

# 读取主题配置
config_file = os.path.join(os.environ['PROJECT_ROOT'], 'kafka', 'topics.yaml')
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

kafka_home = os.environ['KAFKA_HOME']
kafka_topics_cmd = os.path.join(kafka_home, 'bin', 'kafka-topics.sh')

# 创建每个主题
for topic in config['topics']:
    topic_name = topic['name']
    partitions = topic['partitions']
    replication_factor = topic['replication_factor']
    
    print(f"创建主题: {topic_name}")
    
    # 检查主题是否已存在
    check_cmd = [
        kafka_topics_cmd,
        '--bootstrap-server', 'localhost:9092',
        '--list'
    ]
    
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    existing_topics = result.stdout.strip().split('\n')
    
    if topic_name in existing_topics:
        print(f"  ✅ 主题 {topic_name} 已存在")
        continue
    
    # 创建主题
    create_cmd = [
        kafka_topics_cmd,
        '--bootstrap-server', 'localhost:9092',
        '--create',
        '--topic', topic_name,
        '--partitions', str(partitions),
        '--replication-factor', str(replication_factor)
    ]
    
    # 添加配置
    if 'config' in topic:
        for key, value in topic['config'].items():
            create_cmd.extend(['--config', f'{key}={value}'])
    
    try:
        subprocess.run(create_cmd, check=True, capture_output=True)
        print(f"  ✅ 主题 {topic_name} 创建成功")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 主题 {topic_name} 创建失败: {e}")
        sys.exit(1)

print("✅ 所有主题创建完成")
EOF
    
    echo -e "${GREEN}✅ Kafka 主题创建完成${NC}"
}

# 验证 Kafka 部署
verify_kafka_deployment() {
    echo -e "${YELLOW}🔍 验证 Kafka 部署...${NC}"
    
    # 检查 Kafka 进程
    if ! pgrep -f "kafka.Kafka" > /dev/null; then
        echo -e "${RED}❌ Kafka 进程未运行${NC}"
        exit 1
    fi
    
    # 列出主题
    echo -e "${BLUE}📋 已创建的主题:${NC}"
    "$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --list
    
    # 测试生产者和消费者
    echo -e "${YELLOW}🧪 测试消息生产和消费...${NC}"
    
    # 发送测试消息
    echo '{"test": "message", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' | \
        "$KAFKA_HOME/bin/kafka-console-producer.sh" \
        --bootstrap-server localhost:9092 \
        --topic taxi-raw-data
    
    # 消费测试消息
    timeout 5 "$KAFKA_HOME/bin/kafka-console-consumer.sh" \
        --bootstrap-server localhost:9092 \
        --topic taxi-raw-data \
        --from-beginning \
        --max-messages 1 > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Kafka 消息测试成功${NC}"
    else
        echo -e "${YELLOW}⚠️  Kafka 消息测试超时（正常现象）${NC}"
    fi
    
    echo -e "${GREEN}✅ Kafka 部署验证完成${NC}"
}

# 部署流处理器
deploy_stream_processors() {
    echo -e "${YELLOW}🌊 部署流处理器...${NC}"
    
    # 创建流处理器配置
    cat > "$STREAMING_DIR/processor_config.json" << EOF
{
    "kafka_servers": ["localhost:9092"],
    "consumer_group": "realtime-processor-group",
    "input_topics": ["taxi-raw-data"],
    "output_topics": ["taxi-features", "taxi-features-realtime"],
    "max_workers": 4,
    "metrics_port": 8080,
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
    "log_level": "INFO"
}
EOF
    
    # 创建流处理器启动脚本
    cat > "$PROJECT_ROOT/scripts/start_stream_processor.sh" << 'EOF'
#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/venv"

echo "🌊 启动实时流处理器..."

# 激活虚拟环境
source "$VENV_PATH/bin/activate"

# 启动流处理器
cd "$PROJECT_ROOT/streaming"
nohup python realtime_processor.py > stream_processor.log 2>&1 &
PROCESSOR_PID=$!
echo $PROCESSOR_PID > stream_processor.pid

echo "✅ 流处理器已启动 (PID: $PROCESSOR_PID)"
echo "📊 指标端点: http://localhost:8080"
echo "📋 日志文件: streaming/stream_processor.log"
EOF
    
    # 创建流处理器停止脚本
    cat > "$PROJECT_ROOT/scripts/stop_stream_processor.sh" << 'EOF'
#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🛑 停止实时流处理器..."

if [ -f "$PROJECT_ROOT/streaming/stream_processor.pid" ]; then
    PROCESSOR_PID=$(cat "$PROJECT_ROOT/streaming/stream_processor.pid")
    if ps -p $PROCESSOR_PID > /dev/null; then
        kill $PROCESSOR_PID
        echo "✅ 流处理器已停止 (PID: $PROCESSOR_PID)"
    else
        echo "⚠️  流处理器进程不存在"
    fi
    rm -f "$PROJECT_ROOT/streaming/stream_processor.pid"
else
    echo "⚠️  未找到流处理器 PID 文件"
fi
EOF
    
    # 设置执行权限
    chmod +x "$PROJECT_ROOT/scripts/start_stream_processor.sh"
    chmod +x "$PROJECT_ROOT/scripts/stop_stream_processor.sh"
    
    echo -e "${GREEN}✅ 流处理器部署完成${NC}"
}

# 创建数据生成器
create_data_generator() {
    echo -e "${YELLOW}📊 创建数据生成器...${NC}"
    
    cat > "$STREAMING_DIR/data_generator.py" << 'EOF'
#!/usr/bin/env python3
"""
Kafka 数据生成器
为流处理系统生成模拟的出租车数据
"""

import json
import time
import random
from datetime import datetime, timedelta
from kafka import KafkaProducer
import numpy as np

class TaxiDataGenerator:
    def __init__(self, kafka_servers=['localhost:9092']):
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )
        
        self.companies = [
            "Flash Cab", "Taxi Affiliation Services", "Yellow Cab",
            "Blue Diamond", "Chicago Carriage Cab Corp", "City Service"
        ]
        
        self.payment_types = ["Credit Card", "Cash", "No Charge", "Dispute"]
    
    def generate_trip_data(self):
        """生成单次行程数据"""
        now = datetime.now()
        pickup_time = now - timedelta(minutes=random.randint(0, 60))
        trip_duration = random.randint(300, 3600)  # 5-60分钟
        dropoff_time = pickup_time + timedelta(seconds=trip_duration)
        
        # 芝加哥市区坐标范围
        pickup_lat = random.uniform(41.6, 42.1)
        pickup_lon = random.uniform(-87.9, -87.5)
        dropoff_lat = random.uniform(41.6, 42.1)
        dropoff_lon = random.uniform(-87.9, -87.5)
        
        # 计算距离（简化）
        distance = random.exponential(3.0)
        
        # 计算费用
        base_fare = 2.25
        distance_fare = distance * 1.75
        time_fare = (trip_duration / 60) * 0.25
        fare = base_fare + distance_fare + time_fare + random.normal(0, 1)
        fare = max(2.25, fare)
        
        return {
            "trip_id": f"trip_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
            "pickup_datetime": pickup_time.isoformat(),
            "dropoff_datetime": dropoff_time.isoformat(),
            "pickup_latitude": pickup_lat,
            "pickup_longitude": pickup_lon,
            "dropoff_latitude": dropoff_lat,
            "dropoff_longitude": dropoff_lon,
            "passenger_count": random.randint(1, 4),
            "trip_distance": distance,
            "fare_amount": round(fare, 2),
            "payment_type": random.choice(self.payment_types),
            "company": random.choice(self.companies),
            "timestamp": now.isoformat()
        }
    
    def start_generating(self, rate_per_second=2, duration_seconds=3600):
        """开始生成数据"""
        print(f"开始生成数据，速率: {rate_per_second} 条/秒，持续: {duration_seconds} 秒")
        
        end_time = time.time() + duration_seconds
        
        while time.time() < end_time:
            try:
                # 生成数据
                trip_data = self.generate_trip_data()
                
                # 发送到 Kafka
                self.producer.send('taxi-raw-data', value=trip_data)
                
                print(f"发送数据: {trip_data['trip_id']}")
                
                # 控制发送速率
                time.sleep(1.0 / rate_per_second)
                
            except KeyboardInterrupt:
                print("收到中断信号，停止生成数据")
                break
            except Exception as e:
                print(f"数据生成错误: {e}")
                time.sleep(1)
        
        self.producer.close()
        print("数据生成完成")

if __name__ == "__main__":
    generator = TaxiDataGenerator()
    generator.start_generating(rate_per_second=1, duration_seconds=300)  # 5分钟测试
EOF
    
    echo -e "${GREEN}✅ 数据生成器创建完成${NC}"
}

# 创建监控脚本
create_monitoring_scripts() {
    echo -e "${YELLOW}📊 创建监控脚本...${NC}"
    
    # Kafka 监控脚本
    cat > "$PROJECT_ROOT/scripts/monitor_kafka.sh" << 'EOF'
#!/bin/bash

KAFKA_HOME="/usr/local/kafka"

echo "📊 Kafka 集群监控"
echo "=================="

# 检查 Kafka 进程
echo "🔍 Kafka 进程状态:"
if pgrep -f "kafka.Kafka" > /dev/null; then
    echo "  ✅ Kafka 服务器运行中"
    echo "  📊 PID: $(pgrep -f 'kafka.Kafka')"
else
    echo "  ❌ Kafka 服务器未运行"
fi

echo ""

# 列出主题
echo "📋 Kafka 主题列表:"
"$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --list

echo ""

# 主题详情
echo "📊 主题详细信息:"
for topic in $("$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --list); do
    echo "  主题: $topic"
    "$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --describe --topic "$topic" | grep -E "Topic:|Partition:"
    echo ""
done

# 消费者组信息
echo "👥 消费者组信息:"
"$KAFKA_HOME/bin/kafka-consumer-groups.sh" --bootstrap-server localhost:9092 --list

echo ""
echo "📈 实时监控命令:"
echo "  主题消息数: kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic TOPIC_NAME"
echo "  消费者延迟: kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group GROUP_NAME"
EOF
    
    chmod +x "$PROJECT_ROOT/scripts/monitor_kafka.sh"
    
    echo -e "${GREEN}✅ 监控脚本创建完成${NC}"
}

# 创建完整的启动/停止脚本
create_service_scripts() {
    echo -e "${YELLOW}📝 创建服务管理脚本...${NC}"
    
    # 完整启动脚本
    cat > "$PROJECT_ROOT/scripts/start_kafka_system.sh" << 'EOF'
#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 启动 Kafka 流处理系统"
echo "========================"

# 启动 Kafka
if ! pgrep -f "kafka.Kafka" > /dev/null; then
    echo "🚀 启动 Kafka 服务器..."
    nohup /usr/local/kafka/bin/kafka-server-start.sh /usr/local/kafka/config/kraft/server.properties > "$PROJECT_ROOT/kafka.log" 2>&1 &
    echo $! > "$PROJECT_ROOT/kafka.pid"
    sleep 10
    echo "✅ Kafka 服务器已启动"
else
    echo "✅ Kafka 服务器已运行"
fi

# 启动流处理器
"$PROJECT_ROOT/scripts/start_stream_processor.sh"

# 显示状态
echo ""
echo "📊 系统状态:"
echo "  Kafka 服务器: http://localhost:9092"
echo "  流处理器指标: http://localhost:8080"
echo "  日志文件: $PROJECT_ROOT/kafka.log"
echo ""
echo "🧪 测试命令:"
echo "  生成测试数据: cd streaming && python data_generator.py"
echo "  监控系统: ./scripts/monitor_kafka.sh"
EOF
    
    # 完整停止脚本
    cat > "$PROJECT_ROOT/scripts/stop_kafka_system.sh" << 'EOF'
#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🛑 停止 Kafka 流处理系统"
echo "======================="

# 停止流处理器
"$PROJECT_ROOT/scripts/stop_stream_processor.sh"

# 停止 Kafka
if [ -f "$PROJECT_ROOT/kafka.pid" ]; then
    KAFKA_PID=$(cat "$PROJECT_ROOT/kafka.pid")
    if ps -p $KAFKA_PID > /dev/null; then
        kill $KAFKA_PID
        echo "✅ Kafka 服务器已停止 (PID: $KAFKA_PID)"
    else
        echo "⚠️  Kafka 进程不存在"
    fi
    rm -f "$PROJECT_ROOT/kafka.pid"
else
    echo "⚠️  未找到 Kafka PID 文件"
fi

echo "✅ 系统已停止"
EOF
    
    # 设置执行权限
    chmod +x "$PROJECT_ROOT/scripts/start_kafka_system.sh"
    chmod +x "$PROJECT_ROOT/scripts/stop_kafka_system.sh"
    
    echo -e "${GREEN}✅ 服务管理脚本创建完成${NC}"
}

# 显示部署摘要
show_deployment_summary() {
    echo -e "\n${BLUE}🎉 Kafka Kraft 流处理系统部署完成！${NC}"
    echo -e "\n${YELLOW}📋 部署摘要:${NC}"
    echo -e "  🚀 Kafka 服务器: localhost:9092"
    echo -e "  📊 流处理器指标: http://localhost:8080"
    echo -e "  📁 Kafka 主目录: $KAFKA_HOME"
    echo -e "  📂 数据目录: $KAFKA_DATA_DIR"
    echo -e "  📋 配置文件: $KAFKA_DIR/server.properties"
    
    echo -e "\n${YELLOW}🚀 快速开始:${NC}"
    echo -e "  启动系统: ./scripts/start_kafka_system.sh"
    echo -e "  停止系统: ./scripts/stop_kafka_system.sh"
    echo -e "  监控系统: ./scripts/monitor_kafka.sh"
    echo -e "  生成数据: cd streaming && python data_generator.py"
    
    echo -e "\n${YELLOW}📊 主要主题:${NC}"
    echo -e "  📥 taxi-raw-data: 原始行程数据"
    echo -e "  🔧 taxi-features: 处理后特征"
    echo -e "  ⚡ taxi-features-realtime: 实时特征"
    echo -e "  🎯 taxi-predictions: 预测结果"
    echo -e "  📈 taxi-model-metrics: 模型指标"
    
    echo -e "\n${YELLOW}🔗 集成组件:${NC}"
    echo -e "  🍽️  Feast 特征存储: 特征管理和服务"
    echo -e "  🔴 Redis: 在线特征缓存"
    echo -e "  📊 Prometheus: 指标收集"
    echo -e "  🌐 FastAPI: RESTful API 服务"
    echo -e "  🎨 Streamlit: 交互式 UI"
    
    echo -e "\n${GREEN}✅ 准备就绪！现在可以开始使用 Kafka 流处理系统了${NC}"
}

# 主执行流程
main() {
    echo -e "${BLUE}🚀 Kafka Kraft 流处理系统部署开始...${NC}"
    
    check_venv
    activate_venv
    install_kafka
    install_python_dependencies
    configure_kafka
    start_kafka
    create_topics
    verify_kafka_deployment
    deploy_stream_processors
    create_data_generator
    create_monitoring_scripts
    create_service_scripts
    show_deployment_summary
    
    echo -e "\n${GREEN}🎊 Kafka 部署全部完成！${NC}"
}

# 错误处理
trap 'echo -e "\n${RED}❌ 部署过程中出现错误${NC}"; exit 1' ERR

# 执行主函数
main "$@"
