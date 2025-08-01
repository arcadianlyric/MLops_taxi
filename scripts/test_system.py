#!/usr/bin/env python3
"""
MLOps 系统验证脚本
测试 FastAPI 和 Streamlit 服务的基本功能
"""

import requests
import json
import time
import sys
from datetime import datetime

# 配置
FASTAPI_URL = "http://localhost:8000"
STREAMLIT_URL = "http://localhost:8501"

def test_fastapi_health():
    """测试 FastAPI 健康检查"""
    try:
        response = requests.get(f"{FASTAPI_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ FastAPI 健康检查通过: {data['status']}")
            return True
        else:
            print(f"❌ FastAPI 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FastAPI 连接失败: {str(e)}")
        return False

def test_prediction():
    """测试预测功能"""
    try:
        payload = {
            "features": {
                "trip_distance": 5.2,
                "pickup_hour": 14
            },
            "model_name": "taxi_model"
        }
        
        response = requests.post(
            f"{FASTAPI_URL}/predict",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 单次预测成功: 预测值={data['prediction']}, 置信度={data['confidence']}")
            return True
        else:
            print(f"❌ 预测失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 预测请求失败: {str(e)}")
        return False

def test_batch_prediction():
    """测试批量预测"""
    try:
        payload = [
            {
                "features": {"trip_distance": 2.1, "pickup_hour": 8},
                "model_name": "taxi_model"
            },
            {
                "features": {"trip_distance": 7.5, "pickup_hour": 18},
                "model_name": "taxi_model"
            }
        ]
        
        response = requests.post(
            f"{FASTAPI_URL}/predict/batch",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 批量预测成功: 处理了 {data['count']} 个请求")
            return True
        else:
            print(f"❌ 批量预测失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 批量预测请求失败: {str(e)}")
        return False

def test_models_list():
    """测试模型列表"""
    try:
        response = requests.get(f"{FASTAPI_URL}/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 模型列表获取成功: 发现 {len(data['models'])} 个模型")
            return True
        else:
            print(f"❌ 模型列表获取失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 模型列表请求失败: {str(e)}")
        return False

def test_metrics():
    """测试服务指标"""
    try:
        response = requests.get(f"{FASTAPI_URL}/metrics", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务指标获取成功: 准确率={data['model_accuracy']}")
            return True
        else:
            print(f"❌ 服务指标获取失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 服务指标请求失败: {str(e)}")
        return False

def test_streamlit_availability():
    """测试 Streamlit 可用性"""
    try:
        response = requests.get(STREAMLIT_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Streamlit UI 可访问")
            return True
        else:
            print(f"❌ Streamlit UI 访问失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Streamlit UI 连接失败: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始 MLOps 系统验证测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    tests = [
        ("FastAPI 健康检查", test_fastapi_health),
        ("单次预测", test_prediction),
        ("批量预测", test_batch_prediction),
        ("模型列表", test_models_list),
        ("服务指标", test_metrics),
        ("Streamlit UI", test_streamlit_availability),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 测试: {test_name}")
        if test_func():
            passed += 1
        time.sleep(1)  # 避免请求过快
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！MLOps 系统运行正常")
        return 0
    else:
        print("⚠️  部分测试失败，请检查服务状态")
        return 1

if __name__ == "__main__":
    sys.exit(main())
