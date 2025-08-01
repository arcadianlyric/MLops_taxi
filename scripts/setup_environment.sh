#!/bin/bash

# 基础环境设置脚本
# Chicago Taxi MLOps 平台环境初始化

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"

echo -e "${BLUE}🚀 开始设置 MLOps 平台环境...${NC}"

# 1. 检查 Python 版本
echo -e "${YELLOW}📋 步骤 1: 检查 Python 版本...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✅ Python 版本: ${PYTHON_VERSION}${NC}"

# 2. 创建虚拟环境
echo -e "${YELLOW}📋 步骤 2: 创建虚拟环境...${NC}"
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
    echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
else
    echo -e "${GREEN}✅ 虚拟环境已存在${NC}"
fi

# 3. 激活虚拟环境并安装基础依赖
echo -e "${YELLOW}📋 步骤 3: 安装基础依赖...${NC}"
source "$VENV_PATH/bin/activate"

# 升级 pip
pip install --upgrade pip --quiet

# 安装核心依赖
pip install fastapi==0.104.1 --quiet
pip install uvicorn==0.24.0 --quiet
pip install streamlit==1.28.1 --quiet
pip install pandas==2.1.3 --quiet
pip install numpy==1.24.3 --quiet
pip install plotly==5.17.0 --quiet
pip install requests==2.31.0 --quiet

echo -e "${GREEN}✅ 基础依赖安装完成${NC}"

# 4. 创建目录结构
echo -e "${YELLOW}📋 步骤 4: 创建目录结构...${NC}"
mkdir -p "${PROJECT_ROOT}/logs"
mkdir -p "${PROJECT_ROOT}/data"
mkdir -p "${PROJECT_ROOT}/models"
mkdir -p "${PROJECT_ROOT}/artifacts"

echo -e "${GREEN}✅ 目录结构创建完成${NC}"

# 5. 显示环境信息
echo -e "\n${BLUE}🎉 环境设置完成!${NC}"
echo -e "${BLUE}==================${NC}"
echo -e "📁 项目根目录: ${PROJECT_ROOT}"
echo -e "🐍 虚拟环境: ${VENV_PATH}"
echo -e "📦 Python 版本: ${PYTHON_VERSION}"
echo -e ""
echo -e "${YELLOW}💡 激活虚拟环境:${NC}"
echo -e "   source ${VENV_PATH}/bin/activate"
echo -e ""
echo -e "${GREEN}✅ 环境设置成功完成!${NC}"

exit 0
