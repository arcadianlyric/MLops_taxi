#!/bin/bash
# 数据漂移监控快速启动脚本

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

echo -e "${BLUE}🚀 启动 Chicago Taxi 数据漂移监控系统${NC}"
echo "================================================"

# 检查虚拟环境
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️  未检测到虚拟环境，尝试激活...${NC}"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
    else
        echo -e "${RED}❌ 未找到虚拟环境，请先运行: python -m venv venv && source venv/bin/activate${NC}"
        exit 1
    fi
fi

# 检查依赖
echo -e "${BLUE}📦 检查 Python 依赖...${NC}"
python -c "import streamlit, plotly, pandas, numpy" 2>/dev/null || {
    echo -e "${YELLOW}⚠️  安装缺失的依赖...${NC}"
    pip install streamlit plotly pandas numpy
}

# 创建必要的目录
echo -e "${BLUE}📁 创建目录结构...${NC}"
mkdir -p data/baseline data/current ui/drift_results pipelines metadata

# 生成模拟数据（如果不存在）
if [ ! -f "data/baseline/taxi_data.csv" ]; then
    echo -e "${BLUE}📊 生成模拟数据...${NC}"
    python -c "
import pandas as pd
import numpy as np
import os

# 生成基线数据
n_samples = 1000
baseline_data = {
    'trip_miles': np.random.exponential(3, n_samples),
    'fare': np.random.exponential(8, n_samples),
    'trip_seconds': np.random.exponential(600, n_samples),
    'pickup_latitude': np.random.normal(41.88, 0.1, n_samples),
    'pickup_longitude': np.random.normal(-87.63, 0.1, n_samples),
    'dropoff_latitude': np.random.normal(41.89, 0.1, n_samples),
    'dropoff_longitude': np.random.normal(-87.62, 0.1, n_samples),
    'payment_type': np.random.choice(['Credit Card', 'Cash', 'No Charge'], n_samples, p=[0.7, 0.25, 0.05]),
    'company': np.random.choice(['Flash Cab', 'Taxi Affiliation Services', 'Yellow Cab'], n_samples, p=[0.4, 0.35, 0.25]),
    'trip_start_hour': np.random.randint(0, 24, n_samples)
}

df_baseline = pd.DataFrame(baseline_data)
df_baseline.to_csv('data/baseline/taxi_data.csv', index=False)

# 生成当前数据（添加漂移）
current_data = baseline_data.copy()
current_data['trip_miles'] = np.random.exponential(3.5, n_samples)  # 漂移
current_data['fare'] = np.random.exponential(9, n_samples)  # 漂移
current_data['payment_type'] = np.random.choice(['Credit Card', 'Cash', 'No Charge'], n_samples, p=[0.8, 0.15, 0.05])  # 漂移

df_current = pd.DataFrame(current_data)
df_current.to_csv('data/current/taxi_data.csv', index=False)

print('✅ 模拟数据已生成')
"
    echo -e "${GREEN}✅ 模拟数据生成完成${NC}"
fi

# 生成模拟漂移监控结果
echo -e "${BLUE}🔍 生成模拟漂移监控结果...${NC}"
python -c "
import json
import os
from datetime import datetime
import numpy as np

# 创建模拟漂移结果
features = ['trip_miles', 'fare', 'trip_seconds', 'pickup_latitude', 'pickup_longitude', 
           'dropoff_latitude', 'dropoff_longitude', 'payment_type', 'company', 'trip_start_hour']

feature_details = {}
overall_drift = False

for feature in features:
    drift_score = np.random.uniform(0.0, 0.8)
    is_drifted = drift_score > 0.1
    
    if is_drifted:
        overall_drift = True
    
    if drift_score < 0.1:
        drift_type = '无漂移'
    elif drift_score < 0.3:
        drift_type = '轻微漂移'
    elif drift_score < 0.5:
        drift_type = '中等漂移'
    else:
        drift_type = '严重漂移'
    
    feature_details[feature] = {
        'drift_score': round(drift_score, 3),
        'is_drifted': is_drifted,
        'drift_type': drift_type,
        'baseline_stats': {'name': feature, 'type': 'FLOAT' if feature not in ['payment_type', 'company'] else 'BYTES'},
        'current_stats': {'name': feature, 'type': 'FLOAT' if feature not in ['payment_type', 'company'] else 'BYTES'}
    }

drift_data = {
    'summary': {
        'timestamp': datetime.now().isoformat(),
        'overall_drift_detected': overall_drift,
        'threshold': 0.1,
        'total_features_checked': len(features),
        'drifted_features_count': sum(1 for f in feature_details.values() if f['is_drifted'])
    },
    'feature_details': feature_details,
    'recommendations': [
        '检测到数据漂移，建议进行以下操作：' if overall_drift else '未检测到显著数据漂移，模型可以继续使用',
        '1. 检查数据收集流程是否有变化',
        '2. 考虑重新训练模型',
        '3. 更新数据预处理逻辑'
    ] if overall_drift else ['未检测到显著数据漂移，模型可以继续使用']
}

# 保存结果
os.makedirs('ui/drift_results', exist_ok=True)
with open('ui/drift_results/latest_drift_report.json', 'w', encoding='utf-8') as f:
    json.dump(drift_data, f, ensure_ascii=False, indent=2)

# 生成配置文件
config = {
    'last_update': datetime.now().isoformat(),
    'drift_report_path': os.path.abspath('ui/drift_results/latest_drift_report.json'),
    'drift_metrics_path': os.path.abspath('ui/drift_results/latest_drift_metrics.json'),
    'pipeline_root': os.path.abspath('pipelines')
}

with open('ui/drift_results/config.json', 'w') as f:
    json.dump(config, f, indent=2)

print('✅ 模拟漂移监控结果已生成')
"

# 启动 Streamlit UI
echo -e "${BLUE}🌐 启动 Streamlit UI...${NC}"
echo -e "${GREEN}🎯 访问地址: http://localhost:8501${NC}"
echo -e "${GREEN}📊 数据漂移监控标签页已就绪！${NC}"
echo ""
echo -e "${YELLOW}💡 使用说明:${NC}"
echo "1. 打开浏览器访问 http://localhost:8501"
echo "2. 点击 '🔍 数据漂移监控' 标签页"
echo "3. 查看特征漂移图表、热力图和详细分析"
echo "4. 导出漂移报告或触发告警"
echo ""
echo -e "${BLUE}按 Ctrl+C 停止服务${NC}"
echo "================================================"

# 启动 Streamlit
python -m streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true
