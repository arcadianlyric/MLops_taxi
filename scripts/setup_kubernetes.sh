#!/bin/bash
set -e

# Kubernetes 环境设置脚本
# 支持 Docker Desktop 和 Minikube

echo "🚀 开始设置 Kubernetes 环境"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查必要工具
check_prerequisites() {
    echo -e "${BLUE}📋 检查必要工具...${NC}"
    
    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl 未安装${NC}"
        echo "请安装 kubectl: https://kubernetes.io/docs/tasks/tools/"
        exit 1
    fi
    echo -e "${GREEN}✅ kubectl 已安装: $(kubectl version --client)${NC}"
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker 未安装${NC}"
        echo "请安装 Docker Desktop: https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker 已安装: $(docker --version)${NC}"
    
    # 检查 Helm
    if ! command -v helm &> /dev/null; then
        echo -e "${YELLOW}⚠️  Helm 未安装，正在安装...${NC}"
        if command -v /opt/homebrew/bin/brew &> /dev/null; then
            /opt/homebrew/bin/brew install helm
        elif command -v brew &> /dev/null; then
            brew install helm
        else
            echo -e "${RED}❌ 请手动安装 Helm: https://helm.sh/docs/intro/install/${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}✅ Helm 已安装: $(helm version --short)${NC}"
}

# 检查 Docker Desktop Kubernetes
check_docker_desktop() {
    echo -e "${BLUE}🐳 检查 Docker Desktop Kubernetes...${NC}"
    
    # 检查 Docker 是否运行
    if ! docker info &> /dev/null; then
        echo -e "${YELLOW}⚠️  Docker Desktop 未运行${NC}"
        echo "请启动 Docker Desktop 并在设置中启用 Kubernetes"
        echo "设置路径: Docker Desktop -> Settings -> Kubernetes -> Enable Kubernetes"
        return 1
    fi
    
    # 检查 Kubernetes 上下文
    if kubectl config current-context | grep -q "docker-desktop"; then
        echo -e "${GREEN}✅ Docker Desktop Kubernetes 已启用${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Docker Desktop Kubernetes 未启用${NC}"
        return 1
    fi
}

# 设置 Minikube（备选方案）
setup_minikube() {
    echo -e "${BLUE}🎯 设置 Minikube...${NC}"
    
    # 检查 Minikube 是否安装
    if ! command -v minikube &> /dev/null; then
        echo -e "${YELLOW}⚠️  Minikube 未安装，正在安装...${NC}"
        if command -v /opt/homebrew/bin/brew &> /dev/null; then
            /opt/homebrew/bin/brew install minikube
        elif command -v brew &> /dev/null; then
            brew install minikube
        else
            echo -e "${RED}❌ 请手动安装 Minikube: https://minikube.sigs.k8s.io/docs/start/${NC}"
            exit 1
        fi
    fi
    
    # 启动 Minikube
    echo -e "${BLUE}🚀 启动 Minikube...${NC}"
    minikube start --driver=docker --memory=8192 --cpus=4
    
    # 启用必要的插件
    minikube addons enable ingress
    minikube addons enable metrics-server
    
    echo -e "${GREEN}✅ Minikube 设置完成${NC}"
}

# 验证 Kubernetes 集群
verify_cluster() {
    echo -e "${BLUE}🔍 验证 Kubernetes 集群...${NC}"
    
    # 检查集群连接
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ 无法连接到 Kubernetes 集群${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Kubernetes 集群连接正常${NC}"
    kubectl cluster-info
    
    # 检查节点状态
    echo -e "${BLUE}📊 节点状态:${NC}"
    kubectl get nodes
    
    # 检查命名空间
    echo -e "${BLUE}📦 当前命名空间:${NC}"
    kubectl get namespaces
}

# 创建必要的命名空间
create_namespaces() {
    echo -e "${BLUE}📦 创建必要的命名空间...${NC}"
    
    namespaces=(
        "kubeflow"
        "monitoring" 
        "mlops-system"
        "feast-system"
    )
    
    for ns in "${namespaces[@]}"; do
        if kubectl get namespace "$ns" &> /dev/null; then
            echo -e "${GREEN}✅ 命名空间 $ns 已存在${NC}"
        else
            kubectl create namespace "$ns"
            echo -e "${GREEN}✅ 创建命名空间 $ns${NC}"
        fi
    done
}

# 主函数
main() {
    echo "=" * 50
    echo -e "${BLUE}🎯 Kubernetes 环境设置${NC}"
    echo "=" * 50
    
    check_prerequisites
    
    # 尝试使用 Docker Desktop，失败则使用 Minikube
    if check_docker_desktop; then
        echo -e "${GREEN}🎉 使用 Docker Desktop Kubernetes${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker Desktop Kubernetes 不可用，切换到 Minikube${NC}"
        read -p "是否继续使用 Minikube? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            setup_minikube
        else
            echo -e "${RED}❌ 请启动 Docker Desktop 并启用 Kubernetes${NC}"
            exit 1
        fi
    fi
    
    verify_cluster
    create_namespaces
    
    echo -e "${GREEN}🎉 Kubernetes 环境设置完成！${NC}"
    echo -e "${BLUE}下一步: 运行 ./scripts/deploy_monitoring.sh 部署监控堆栈${NC}"
}

# 运行主函数
main "$@"
