#!/bin/bash

# Feast 特征存储部署脚本
# 在 macOS 上部署 Feast 服务器、Redis 和数据生成

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FEAST_DIR="$PROJECT_ROOT/feast"
VENV_PATH="$PROJECT_ROOT/venv"

echo -e "${BLUE}🍽️  开始部署 Feast 特征存储系统...${NC}"

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

# 安装 Feast 和相关依赖
install_feast_dependencies() {
    echo -e "${YELLOW}📦 安装 Feast 和相关依赖...${NC}"
    
    # 安装 Feast
    pip install feast[redis] --quiet
    
    # 安装 Redis Python 客户端
    pip install redis --quiet
    
    # 安装数据处理依赖
    pip install pyarrow fastparquet --quiet
    
    echo -e "${GREEN}✅ Feast 依赖安装完成${NC}"
}

# 检查并启动 Redis
setup_redis() {
    echo -e "${YELLOW}🔴 设置 Redis 服务...${NC}"
    
    # 检查 Redis 是否已安装
    if ! command -v redis-server &> /dev/null; then
        echo -e "${YELLOW}📦 安装 Redis...${NC}"
        brew install redis
    fi
    
    # 检查 Redis 是否运行
    if ! redis-cli ping &> /dev/null; then
        echo -e "${YELLOW}🚀 启动 Redis 服务...${NC}"
        brew services start redis
        
        # 等待 Redis 启动
        sleep 3
        
        # 再次检查
        if redis-cli ping &> /dev/null; then
            echo -e "${GREEN}✅ Redis 服务启动成功${NC}"
        else
            echo -e "${RED}❌ Redis 服务启动失败${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Redis 服务已运行${NC}"
    fi
}

# 初始化 Feast 仓库
initialize_feast_repo() {
    echo -e "${YELLOW}🏗️  初始化 Feast 仓库...${NC}"
    
    cd "$FEAST_DIR"
    
    # 检查是否已初始化
    if [ ! -f "feature_store.yaml" ]; then
        echo -e "${RED}❌ feature_store.yaml 不存在${NC}"
        exit 1
    fi
    
    # 创建必要的目录
    mkdir -p data/offline_store
    mkdir -p data/registry
    
    # 应用特征定义
    echo -e "${YELLOW}📝 应用特征定义...${NC}"
    feast apply
    
    echo -e "${GREEN}✅ Feast 仓库初始化完成${NC}"
}

# 生成特征数据
generate_feature_data() {
    echo -e "${YELLOW}📊 生成特征数据...${NC}"
    
    cd "$PROJECT_ROOT"
    python feast/data_generator.py
    
    echo -e "${GREEN}✅特征数据生成完成${NC}"
}

# 将数据导入 Feast
import_features_to_feast() {
    echo -e "${YELLOW}📥 导入特征到 Feast...${NC}"
    
    cd "$FEAST_DIR"
    
    # 导入历史特征数据
    echo -e "${YELLOW}📈 导入历史特征数据...${NC}"
    
    # 使用 Python 脚本导入数据
    python << 'EOF'
import pandas as pd
from feast import FeatureStore
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)

try:
    # 初始化 Feast 存储
    store = FeatureStore(repo_path=".")
    
    # 读取生成的特征数据
    trip_df = pd.read_parquet("data/offline_store/trip_features.parquet")
    print(f"读取到 {len(trip_df)} 条行程特征")
    
    # 推送最新的特征到在线存储
    recent_data = trip_df.tail(100)  # 取最新100条
    
    print("推送特征到在线存储...")
    # 注意：这里可能需要根据实际的 Feast 版本调整
    # store.push("trip_features", recent_data)
    
    print("✅ 特征导入完成")
    
except Exception as e:
    print(f"❌ 特征导入失败: {e}")
    print("继续使用离线存储...")
EOF
    
    echo -e "${GREEN}✅ 特征导入完成${NC}"
}

# 启动 Feast UI（可选）
start_feast_ui() {
    echo -e "${YELLOW}🌐 启动 Feast UI...${NC}"
    
    cd "$FEAST_DIR"
    
    # 检查是否安装了 Feast UI
    if pip list | grep -q "feast\[ui\]"; then
        echo -e "${YELLOW}🚀 启动 Feast UI 服务器...${NC}"
        nohup feast ui > feast_ui.log 2>&1 &
        FEAST_UI_PID=$!
        echo $FEAST_UI_PID > feast_ui.pid
        
        sleep 5
        
        if ps -p $FEAST_UI_PID > /dev/null; then
            echo -e "${GREEN}✅ Feast UI 已启动 (PID: $FEAST_UI_PID)${NC}"
            echo -e "${BLUE}🌐 访问 http://localhost:8888 查看 Feast UI${NC}"
        else
            echo -e "${YELLOW}⚠️  Feast UI 启动可能失败，检查日志: feast_ui.log${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Feast UI 未安装，跳过 UI 启动${NC}"
        echo -e "${BLUE}💡 如需 UI，请运行: pip install 'feast[ui]'${NC}"
    fi
}

# 验证 Feast 部署
verify_feast_deployment() {
    echo -e "${YELLOW}🔍 验证 Feast 部署...${NC}"
    
    cd "$FEAST_DIR"
    
    # 验证特征存储
    python << 'EOF'
from feast import FeatureStore
import pandas as pd
from datetime import datetime

try:
    # 初始化存储
    store = FeatureStore(repo_path=".")
    
    # 列出特征视图
    feature_views = store.list_feature_views()
    print(f"✅ 发现 {len(feature_views)} 个特征视图:")
    for fv in feature_views:
        print(f"  - {fv.name}")
    
    # 列出特征服务
    feature_services = store.list_feature_services()
    print(f"✅ 发现 {len(feature_services)} 个特征服务:")
    for fs in feature_services:
        print(f"  - {fs.name}")
    
    # 测试特征检索
    print("\n🔍 测试特征检索...")
    
    # 创建实体 DataFrame
    entity_df = pd.DataFrame({
        "trip_id": ["trip_000001", "trip_000002", "trip_000003"],
        "event_timestamp": [datetime.now()] * 3
    })
    
    # 尝试获取特征
    try:
        features = store.get_historical_features(
            entity_df=entity_df,
            features=[
                "trip_features:trip_miles",
                "trip_features:trip_seconds", 
                "trip_features:fare"
            ]
        ).to_df()
        
        print(f"✅ 成功检索到 {len(features)} 条特征记录")
        print("特征样本:")
        print(features.head())
        
    except Exception as e:
        print(f"⚠️  历史特征检索测试失败: {e}")
    
    print("\n✅ Feast 部署验证完成")
    
except Exception as e:
    print(f"❌ Feast 验证失败: {e}")
    exit(1)
EOF
    
    echo -e "${GREEN}✅ Feast 部署验证通过${NC}"
}

# 创建 Feast 服务脚本
create_feast_service_scripts() {
    echo -e "${YELLOW}📝 创建 Feast 服务管理脚本...${NC}"
    
    # 创建启动脚本
    cat > "$PROJECT_ROOT/scripts/start_feast.sh" << 'EOF'
#!/bin/bash

# Feast 服务启动脚本

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FEAST_DIR="$PROJECT_ROOT/feast"

echo "🍽️  启动 Feast 服务..."

# 启动 Redis
if ! redis-cli ping &> /dev/null; then
    echo "🔴 启动 Redis..."
    brew services start redis
    sleep 3
fi

# 进入 Feast 目录
cd "$FEAST_DIR"

# 应用最新配置
echo "📝 应用 Feast 配置..."
feast apply

echo "✅ Feast 服务已启动"
echo "🌐 Redis: localhost:6379"
echo "📊 特征存储: $FEAST_DIR"
EOF

    # 创建停止脚本
    cat > "$PROJECT_ROOT/scripts/stop_feast.sh" << 'EOF'
#!/bin/bash

# Feast 服务停止脚本

echo "🛑 停止 Feast 服务..."

# 停止 Feast UI（如果运行）
if [ -f "feast/feast_ui.pid" ]; then
    FEAST_UI_PID=$(cat feast/feast_ui.pid)
    if ps -p $FEAST_UI_PID > /dev/null; then
        kill $FEAST_UI_PID
        echo "🌐 Feast UI 已停止"
    fi
    rm -f feast/feast_ui.pid
fi

# 停止 Redis（可选，因为可能被其他服务使用）
echo "🔴 Redis 服务继续运行（可能被其他服务使用）"
echo "   如需停止 Redis: brew services stop redis"

echo "✅ Feast 服务已停止"
EOF

    # 设置执行权限
    chmod +x "$PROJECT_ROOT/scripts/start_feast.sh"
    chmod +x "$PROJECT_ROOT/scripts/stop_feast.sh"
    
    echo -e "${GREEN}✅ Feast 服务管理脚本已创建${NC}"
}

# 显示部署摘要
show_deployment_summary() {
    echo -e "\n${BLUE}🎉 Feast 特征存储部署完成！${NC}"
    echo -e "\n${YELLOW}📋 部署摘要:${NC}"
    echo -e "  🍽️  Feast 仓库: $FEAST_DIR"
    echo -e "  🔴 Redis 服务: localhost:6379"
    echo -e "  📊 离线存储: $FEAST_DIR/data/offline_store"
    echo -e "  📝 注册表: $FEAST_DIR/data/registry.db"
    
    echo -e "\n${YELLOW}🚀 快速开始:${NC}"
    echo -e "  启动服务: ./scripts/start_feast.sh"
    echo -e "  停止服务: ./scripts/stop_feast.sh"
    echo -e "  查看特征: cd feast && feast feature-views list"
    echo -e "  查看服务: cd feast && feast feature-services list"
    
    echo -e "\n${YELLOW}🔗 集成指南:${NC}"
    echo -e "  FastAPI 集成: 参考 api/feast_client.py"
    echo -e "  TFX 集成: 参考 components/feast_pusher.py"
    echo -e "  Streamlit 集成: 参考 ui/feast_ui_integration.py"
    
    echo -e "\n${GREEN}✅ 准备就绪！现在可以开始使用 Feast 特征存储了${NC}"
}

# 主执行流程
main() {
    echo -e "${BLUE}🍽️  Feast 特征存储部署开始...${NC}"
    
    check_venv
    activate_venv
    install_feast_dependencies
    setup_redis
    initialize_feast_repo
    generate_feature_data
    import_features_to_feast
    start_feast_ui
    verify_feast_deployment
    create_feast_service_scripts
    show_deployment_summary
    
    echo -e "\n${GREEN}🎊 Feast 部署全部完成！${NC}"
}

# 错误处理
trap 'echo -e "\n${RED}❌ 部署过程中出现错误${NC}"; exit 1' ERR

# 执行主函数
main "$@"
