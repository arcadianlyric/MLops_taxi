#!/usr/bin/env python3
"""
完整 MLOps 平台系统验证脚本
验证 Kubernetes、监控堆栈、Kubeflow、本地服务的完整功能
"""

import requests
import json
import time
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple

# 配置
SERVICES = {
    "本地服务": {
        "FastAPI": "http://localhost:8000",
        "Streamlit": "http://localhost:8501"
    },
    "监控服务": {
        "Prometheus": "http://localhost:9090",
        "Grafana": "http://localhost:3000",
        "Loki": "http://localhost:3100"
    },
    "MLOps 平台": {
        "Kubeflow UI": "http://localhost:8080",
        "Kubeflow API": "http://localhost:8888",
        "MinIO": "http://localhost:9000"
    }
}

def check_kubernetes_cluster() -> bool:
    """检查 Kubernetes 集群状态"""
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ Kubernetes 集群连接正常")
            return True
        else:
            print("❌ Kubernetes 集群连接失败")
            return False
    except Exception as e:
        print(f"❌ Kubernetes 集群检查失败: {str(e)}")
        return False

def check_kubernetes_pods() -> Dict[str, int]:
    """检查 Kubernetes Pod 状态"""
    namespaces = ["monitoring", "kubeflow", "mlops-system"]
    results = {}
    
    for ns in namespaces:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", ns, "--no-headers"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines and lines[0]:  # 有 Pod 存在
                    running_pods = sum(1 for line in lines if 'Running' in line)
                    total_pods = len(lines)
                    results[ns] = {"running": running_pods, "total": total_pods}
                    print(f"✅ 命名空间 {ns}: {running_pods}/{total_pods} Pod 运行中")
                else:
                    results[ns] = {"running": 0, "total": 0}
                    print(f"⚠️  命名空间 {ns}: 没有 Pod")
            else:
                results[ns] = {"running": 0, "total": 0}
                print(f"❌ 无法获取命名空间 {ns} 的 Pod 状态")
                
        except Exception as e:
            results[ns] = {"running": 0, "total": 0}
            print(f"❌ 检查命名空间 {ns} 失败: {str(e)}")
    
    return results

def check_service_health(name: str, url: str, timeout: int = 5) -> bool:
    """检查服务健康状态"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            print(f"✅ {name}: 服务正常 ({url})")
            return True
        else:
            print(f"❌ {name}: HTTP {response.status_code} ({url})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ {name}: 连接失败 ({url})")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ {name}: 连接超时 ({url})")
        return False
    except Exception as e:
        print(f"❌ {name}: 检查失败 - {str(e)} ({url})")
        return False

def test_fastapi_functionality() -> bool:
    """测试 FastAPI 功能"""
    try:
        # 健康检查
        health_response = requests.get("http://localhost:8000/health", timeout=5)
        if health_response.status_code != 200:
            print("❌ FastAPI 健康检查失败")
            return False
        
        # 预测测试
        predict_payload = {
            "features": {"trip_distance": 5.2, "pickup_hour": 14},
            "model_name": "taxi_model"
        }
        
        predict_response = requests.post(
            "http://localhost:8000/predict",
            json=predict_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if predict_response.status_code == 200:
            data = predict_response.json()
            print(f"✅ FastAPI 预测功能正常: 预测值={data['prediction']}")
            return True
        else:
            print(f"❌ FastAPI 预测功能失败: HTTP {predict_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ FastAPI 功能测试失败: {str(e)}")
        return False

def check_prometheus_metrics() -> bool:
    """检查 Prometheus 指标"""
    try:
        response = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                print("✅ Prometheus 指标查询正常")
                return True
        print("❌ Prometheus 指标查询失败")
        return False
    except Exception as e:
        print(f"❌ Prometheus 指标检查失败: {str(e)}")
        return False

def check_grafana_api() -> bool:
    """检查 Grafana API"""
    try:
        response = requests.get("http://localhost:3000/api/health", timeout=10)
        if response.status_code == 200:
            print("✅ Grafana API 正常")
            return True
        print(f"❌ Grafana API 失败: HTTP {response.status_code}")
        return False
    except Exception as e:
        print(f"❌ Grafana API 检查失败: {str(e)}")
        return False

def main():
    """主验证函数"""
    print("🚀 开始完整 MLOps 平台系统验证")
    print(f"⏰ 验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 统计结果
    total_tests = 0
    passed_tests = 0
    
    # 1. Kubernetes 集群检查
    print("\n🔍 1. Kubernetes 集群检查")
    print("-" * 30)
    if check_kubernetes_cluster():
        passed_tests += 1
    total_tests += 1
    
    # 2. Kubernetes Pod 状态检查
    print("\n📦 2. Kubernetes Pod 状态检查")
    print("-" * 30)
    pod_results = check_kubernetes_pods()
    for ns, result in pod_results.items():
        if result["running"] > 0:
            passed_tests += 1
        total_tests += 1
    
    # 3. 服务健康检查
    print("\n🌐 3. 服务健康检查")
    print("-" * 30)
    for category, services in SERVICES.items():
        print(f"\n{category}:")
        for service_name, service_url in services.items():
            if check_service_health(service_name, service_url):
                passed_tests += 1
            total_tests += 1
    
    # 4. FastAPI 功能测试
    print("\n🧪 4. FastAPI 功能测试")
    print("-" * 30)
    if test_fastapi_functionality():
        passed_tests += 1
    total_tests += 1
    
    # 5. Prometheus 指标测试
    print("\n📊 5. Prometheus 指标测试")
    print("-" * 30)
    if check_prometheus_metrics():
        passed_tests += 1
    total_tests += 1
    
    # 6. Grafana API 测试
    print("\n📈 6. Grafana API 测试")
    print("-" * 30)
    if check_grafana_api():
        passed_tests += 1
    total_tests += 1
    
    # 结果总结
    print("\n" + "=" * 60)
    print(f"📊 验证结果: {passed_tests}/{total_tests} 通过")
    
    success_rate = (passed_tests / total_tests) * 100
    
    if success_rate >= 90:
        print("🎉 系统状态优秀！MLOps 平台运行正常")
        return 0
    elif success_rate >= 70:
        print("⚠️  系统状态良好，但有部分服务需要检查")
        return 1
    else:
        print("❌ 系统状态需要改善，多个服务存在问题")
        return 2

if __name__ == "__main__":
    sys.exit(main())
