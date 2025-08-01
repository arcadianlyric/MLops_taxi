#!/bin/bash

# MLflow 模型注册中心部署脚本
# Chicago Taxi MLOps 平台 MLflow 服务自动化部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MLFLOW_DIR="${PROJECT_ROOT}/mlflow"
VENV_PATH="${PROJECT_ROOT}/venv"

echo -e "${BLUE}🎯 开始部署 MLflow 模型注册中心...${NC}"

# 1. 检查虚拟环境
echo -e "${YELLOW}📋 步骤 1: 检查虚拟环境...${NC}"
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ 虚拟环境不存在，请先运行 setup_environment.sh${NC}"
    exit 1
fi

# 激活虚拟环境
source "$VENV_PATH/bin/activate"
echo -e "${GREEN}✅ 虚拟环境已激活${NC}"

# 2. 安装 MLflow 依赖
echo -e "${YELLOW}📋 步骤 2: 安装 MLflow 依赖...${NC}"
pip install mlflow==2.8.1 --quiet
pip install boto3 --quiet  # 用于 S3 存储支持
pip install psycopg2-binary --quiet  # 用于 PostgreSQL 支持
echo -e "${GREEN}✅ MLflow 依赖安装完成${NC}"

# 3. 创建 MLflow 目录结构
echo -e "${YELLOW}📋 步骤 3: 创建 MLflow 目录结构...${NC}"
mkdir -p "$MLFLOW_DIR"
mkdir -p "$MLFLOW_DIR/artifacts"
mkdir -p "$MLFLOW_DIR/models"
mkdir -p "$MLFLOW_DIR/experiments"
mkdir -p "$MLFLOW_DIR/logs"
echo -e "${GREEN}✅ MLflow 目录结构创建完成${NC}"

# 4. 初始化 MLflow 数据库
echo -e "${YELLOW}📋 步骤 4: 初始化 MLflow 数据库...${NC}"
cd "$MLFLOW_DIR"

# 设置环境变量
export MLFLOW_BACKEND_STORE_URI="sqlite:///mlflow.db"
export MLFLOW_DEFAULT_ARTIFACT_ROOT="./artifacts"

# 初始化数据库
mlflow db upgrade "$MLFLOW_BACKEND_STORE_URI" || true
echo -e "${GREEN}✅ MLflow 数据库初始化完成${NC}"

# 5. 创建启动脚本
echo -e "${YELLOW}📋 步骤 5: 创建 MLflow 启动脚本...${NC}"
cat > "$MLFLOW_DIR/start_mlflow.sh" << 'EOF'
#!/bin/bash

# MLflow 服务启动脚本

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
MLFLOW_DIR="${PROJECT_ROOT}/mlflow"

# 激活虚拟环境
source "$VENV_PATH/bin/activate"

# 切换到 MLflow 目录
cd "$MLFLOW_DIR"

# 设置环境变量
export MLFLOW_BACKEND_STORE_URI="sqlite:///mlflow.db"
export MLFLOW_DEFAULT_ARTIFACT_ROOT="./artifacts"

echo "🚀 启动 MLflow 服务..."
echo "📊 Tracking UI: http://localhost:5000"
echo "📁 Backend Store: $MLFLOW_BACKEND_STORE_URI"
echo "📦 Artifact Root: $MLFLOW_DEFAULT_ARTIFACT_ROOT"
echo ""

# 启动 MLflow 服务
mlflow server \
    --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" \
    --default-artifact-root "$MLFLOW_DEFAULT_ARTIFACT_ROOT" \
    --host 0.0.0.0 \
    --port 5000 \
    --serve-artifacts \
    --workers 1
EOF

chmod +x "$MLFLOW_DIR/start_mlflow.sh"
echo -e "${GREEN}✅ MLflow 启动脚本创建完成${NC}"

# 6. 创建停止脚本
echo -e "${YELLOW}📋 步骤 6: 创建 MLflow 停止脚本...${NC}"
cat > "$MLFLOW_DIR/stop_mlflow.sh" << 'EOF'
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
EOF

chmod +x "$MLFLOW_DIR/stop_mlflow.sh"
echo -e "${GREEN}✅ MLflow 停止脚本创建完成${NC}"

# 7. 创建示例实验和模型
echo -e "${YELLOW}📋 步骤 7: 创建示例实验和模型...${NC}"
cat > "$MLFLOW_DIR/setup_examples.py" << 'EOF'
#!/usr/bin/env python3
"""
MLflow 示例实验和模型设置脚本
"""

import mlflow
import mlflow.sklearn
import mlflow.tensorflow
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import os
from datetime import datetime

# 设置 MLflow 跟踪 URI
mlflow.set_tracking_uri("http://localhost:5000")

def create_chicago_taxi_experiment():
    """创建 Chicago Taxi 实验"""
    
    # 创建或获取实验
    experiment_name = "chicago-taxi-mlops"
    try:
        experiment_id = mlflow.create_experiment(
            experiment_name,
            tags={
                "project": "chicago-taxi",
                "team": "mlops",
                "environment": "local",
                "created_at": datetime.now().isoformat()
            }
        )
        print(f"✅ 创建实验: {experiment_name} (ID: {experiment_id})")
    except mlflow.exceptions.MlflowException:
        experiment = mlflow.get_experiment_by_name(experiment_name)
        experiment_id = experiment.experiment_id
        print(f"ℹ️  实验已存在: {experiment_name} (ID: {experiment_id})")
    
    return experiment_id

def create_sample_model(experiment_id):
    """创建示例模型"""
    
    # 设置实验
    mlflow.set_experiment(experiment_id=experiment_id)
    
    # 生成示例数据
    np.random.seed(42)
    n_samples = 1000
    
    # 特征: trip_distance, passenger_count, hour_of_day, day_of_week
    X = np.random.rand(n_samples, 4)
    X[:, 0] = X[:, 0] * 20  # trip_distance: 0-20 miles
    X[:, 1] = np.random.randint(1, 5, n_samples)  # passenger_count: 1-4
    X[:, 2] = np.random.randint(0, 24, n_samples)  # hour_of_day: 0-23
    X[:, 3] = np.random.randint(0, 7, n_samples)  # day_of_week: 0-6
    
    # 目标: fare_amount (基于特征的简单公式)
    y = (2.5 + X[:, 0] * 2.0 + X[:, 1] * 0.5 + 
         np.where(X[:, 2] > 22, 1.5, 0) +  # 夜间加价
         np.where(X[:, 3] < 2, 1.0, 0) +   # 周末加价
         np.random.normal(0, 1, n_samples))  # 噪声
    
    # 分割数据
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # 创建特征名称
    feature_names = ["trip_distance", "passenger_count", "hour_of_day", "day_of_week"]
    
    # 训练模型
    with mlflow.start_run(run_name="taxi-fare-predictor-v1") as run:
        # 记录参数
        n_estimators = 100
        max_depth = 10
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("max_depth", max_depth)
        mlflow.log_param("model_type", "RandomForestRegressor")
        
        # 训练模型
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42
        )
        model.fit(X_train, y_train)
        
        # 预测和评估
        y_pred = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        # 记录指标
        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("r2_score", r2)
        mlflow.log_metric("train_samples", len(X_train))
        mlflow.log_metric("test_samples", len(X_test))
        
        # 记录模型
        mlflow.sklearn.log_model(
            model,
            "model",
            registered_model_name="chicago-taxi-fare-predictor"
        )
        
        # 记录标签
        mlflow.set_tag("stage", "development")
        mlflow.set_tag("algorithm", "random_forest")
        mlflow.set_tag("data_version", "v1.0")
        
        print(f"✅ 模型训练完成:")
        print(f"   - Run ID: {run.info.run_id}")
        print(f"   - RMSE: {rmse:.4f}")
        print(f"   - R² Score: {r2:.4f}")
        
        return run.info.run_id

def register_model_versions():
    """注册模型版本到不同阶段"""
    
    client = mlflow.tracking.MlflowClient()
    model_name = "chicago-taxi-fare-predictor"
    
    try:
        # 获取最新版本
        latest_version = client.get_latest_versions(model_name, stages=["None"])[0]
        version = latest_version.version
        
        # 将版本 1 设置为 Staging
        if version == "1":
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Staging"
            )
            print(f"✅ 模型版本 {version} 已设置为 Staging 阶段")
        
    except Exception as e:
        print(f"⚠️  注册模型版本时出错: {e}")

def main():
    """主函数"""
    print("🎯 设置 MLflow 示例实验和模型...")
    
    try:
        # 创建实验
        experiment_id = create_chicago_taxi_experiment()
        
        # 创建示例模型
        run_id = create_sample_model(experiment_id)
        
        # 注册模型版本
        register_model_versions()
        
        print("\n🎉 MLflow 示例设置完成!")
        print("📊 访问 MLflow UI: http://localhost:5000")
        print("🔍 查看实验: chicago-taxi-mlops")
        print("📦 查看模型: chicago-taxi-fare-predictor")
        
    except Exception as e:
        print(f"❌ 设置过程中出错: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
EOF

echo -e "${GREEN}✅ 示例设置脚本创建完成${NC}"

# 8. 创建监控脚本
echo -e "${YELLOW}📋 步骤 8: 创建 MLflow 监控脚本...${NC}"
cat > "$MLFLOW_DIR/monitor_mlflow.sh" << 'EOF'
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
EOF

chmod +x "$MLFLOW_DIR/monitor_mlflow.sh"
echo -e "${GREEN}✅ MLflow 监控脚本创建完成${NC}"

# 9. 验证部署
echo -e "${YELLOW}📋 步骤 9: 验证 MLflow 部署...${NC}"

# 检查配置文件
if [ -f "$MLFLOW_DIR/../mlflow/mlflow_config.yaml" ]; then
    echo -e "${GREEN}✅ MLflow 配置文件存在${NC}"
else
    echo -e "${YELLOW}⚠️  MLflow 配置文件不存在，将使用默认配置${NC}"
fi

# 检查 Python 模块
python -c "import mlflow; print(f'MLflow 版本: {mlflow.__version__}')" 2>/dev/null && \
    echo -e "${GREEN}✅ MLflow Python 模块可用${NC}" || \
    echo -e "${RED}❌ MLflow Python 模块不可用${NC}"

# 10. 显示部署总结
echo -e "\n${BLUE}🎉 MLflow 模型注册中心部署完成!${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "📁 MLflow 目录: ${MLFLOW_DIR}"
echo -e "🗄️  数据库: ${MLFLOW_DIR}/mlflow.db"
echo -e "📦 工件存储: ${MLFLOW_DIR}/artifacts"
echo -e ""
echo -e "${YELLOW}🚀 启动服务:${NC}"
echo -e "   cd ${MLFLOW_DIR} && ./start_mlflow.sh"
echo -e ""
echo -e "${YELLOW}🛑 停止服务:${NC}"
echo -e "   cd ${MLFLOW_DIR} && ./stop_mlflow.sh"
echo -e ""
echo -e "${YELLOW}🔍 监控服务:${NC}"
echo -e "   cd ${MLFLOW_DIR} && ./monitor_mlflow.sh"
echo -e ""
echo -e "${YELLOW}📊 设置示例:${NC}"
echo -e "   cd ${MLFLOW_DIR} && python setup_examples.py"
echo -e ""
echo -e "${YELLOW}🌐 访问 UI:${NC}"
echo -e "   http://localhost:5000"
echo -e ""
echo -e "${GREEN}✅ 部署成功完成!${NC}"

exit 0
