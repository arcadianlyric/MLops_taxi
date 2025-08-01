#!/usr/bin/env python3
"""
完整系统集成测试脚本
验证 Chicago Taxi MLOps 平台所有组件的集成
"""

import os
import sys
import time
import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class MLOpsIntegrationTester:
    """MLOps 平台集成测试器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.test_results = []
        
        # 服务端点配置
        self.endpoints = {
            "fastapi": "http://localhost:8000",
            "streamlit": "http://localhost:8501",
            "mlflow": "http://localhost:5000",
            "redis": "localhost:6379",
            "kafka": "localhost:9092"
        }
    
    def test_fastapi_service(self) -> Dict[str, Any]:
        """测试 FastAPI 服务"""
        test_name = "FastAPI 服务测试"
        
        try:
            # 1. 健康检查
            response = requests.get(f"{self.endpoints['fastapi']}/health", timeout=10)
            health_ok = response.status_code == 200
            
            # 2. 测试基础预测接口
            predict_data = {
                "features": {
                    "trip_distance": 3.5,
                    "passenger_count": 2,
                    "pickup_hour": 14
                }
            }
            
            response = requests.post(
                f"{self.endpoints['fastapi']}/predict",
                json=predict_data,
                timeout=10
            )
            predict_ok = response.status_code == 200
            
            # 3. 测试 Feast 路由
            try:
                response = requests.get(f"{self.endpoints['fastapi']}/feast/info", timeout=10)
                feast_ok = response.status_code == 200
            except:
                feast_ok = False
            
            # 4. 测试 Kafka 路由
            try:
                response = requests.get(f"{self.endpoints['fastapi']}/kafka/info", timeout=10)
                kafka_ok = response.status_code == 200
            except:
                kafka_ok = False
            
            # 5. 测试 MLflow 路由
            try:
                response = requests.get(f"{self.endpoints['fastapi']}/mlflow/info", timeout=10)
                mlflow_ok = response.status_code == 200
            except:
                mlflow_ok = False
            
            success = health_ok and predict_ok
            details = {
                "health_check": health_ok,
                "prediction": predict_ok,
                "feast_integration": feast_ok,
                "kafka_integration": kafka_ok,
                "mlflow_integration": mlflow_ok
            }
            
            return {
                "test_name": test_name,
                "success": success,
                "details": details,
                "score": sum(details.values()) / len(details)
            }
            
        except Exception as e:
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "score": 0.0
            }
    
    def test_mlflow_service(self) -> Dict[str, Any]:
        """测试 MLflow 服务"""
        test_name = "MLflow 服务测试"
        
        try:
            # 1. 健康检查
            response = requests.get(f"{self.endpoints['mlflow']}/health", timeout=10)
            health_ok = response.status_code == 200
            
            # 2. 测试 API 接口
            try:
                response = requests.get(f"{self.endpoints['mlflow']}/api/2.0/mlflow/experiments/search", timeout=10)
                api_ok = response.status_code == 200
            except:
                api_ok = False
            
            success = health_ok or api_ok  # MLflow 可能没有 /health 端点
            details = {
                "service_accessible": health_ok or api_ok,
                "api_functional": api_ok
            }
            
            return {
                "test_name": test_name,
                "success": success,
                "details": details,
                "score": 1.0 if success else 0.0
            }
            
        except Exception as e:
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "score": 0.0
            }
    
    def test_feast_integration(self) -> Dict[str, Any]:
        """测试 Feast 集成"""
        test_name = "Feast 集成测试"
        
        try:
            # 运行 Feast 集成管道
            import subprocess
            
            result = subprocess.run([
                sys.executable, "feast/feast_integration_pipeline.py"
            ], capture_output=True, text=True, timeout=30)
            
            pipeline_ok = result.returncode == 0
            
            # 检查生成的数据文件
            data_files_exist = all([
                os.path.exists("feast/data/trip_features.parquet"),
                os.path.exists("feast/data/area_features.parquet"),
                os.path.exists("feast/data/company_features.parquet"),
                os.path.exists("feast/data/time_features.parquet")
            ])
            
            success = pipeline_ok
            details = {
                "pipeline_execution": pipeline_ok,
                "data_files_generated": data_files_exist,
                "output": result.stdout[:200] if result.stdout else ""
            }
            
            return {
                "test_name": test_name,
                "success": success,
                "details": details,
                "score": 1.0 if success else 0.0
            }
            
        except Exception as e:
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "score": 0.0
            }
    
    def test_kafka_integration(self) -> Dict[str, Any]:
        """测试 Kafka 集成"""
        test_name = "Kafka 集成测试"
        
        try:
            # 测试 Kafka 连接
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', 9092))
                sock.close()
                kafka_accessible = result == 0
            except:
                kafka_accessible = False
            
            # 测试通过 FastAPI 发送消息
            try:
                taxi_data = {
                    "trip_id": "test_trip_001",
                    "pickup_datetime": datetime.now().isoformat(),
                    "dropoff_datetime": datetime.now().isoformat(),
                    "pickup_latitude": 41.88,
                    "pickup_longitude": -87.63,
                    "dropoff_latitude": 41.89,
                    "dropoff_longitude": -87.62,
                    "passenger_count": 2,
                    "trip_distance": 3.5,
                    "fare_amount": 12.50,
                    "payment_type": "Credit Card",
                    "company": "Test Cab"
                }
                
                response = requests.post(
                    f"{self.endpoints['fastapi']}/kafka/messages/taxi-data",
                    json=taxi_data,
                    timeout=10
                )
                message_send_ok = response.status_code == 200
            except:
                message_send_ok = False
            
            success = kafka_accessible or message_send_ok
            details = {
                "kafka_accessible": kafka_accessible,
                "message_sending": message_send_ok
            }
            
            return {
                "test_name": test_name,
                "success": success,
                "details": details,
                "score": sum(details.values()) / len(details)
            }
            
        except Exception as e:
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "score": 0.0
            }
    
    def test_ui_accessibility(self) -> Dict[str, Any]:
        """测试 UI 可访问性"""
        test_name = "UI 可访问性测试"
        
        try:
            # 测试 Streamlit UI
            try:
                response = requests.get(f"{self.endpoints['streamlit']}", timeout=10)
                streamlit_ok = response.status_code == 200
            except:
                streamlit_ok = False
            
            # 测试 MLflow UI
            try:
                response = requests.get(f"{self.endpoints['mlflow']}", timeout=10)
                mlflow_ui_ok = response.status_code == 200
            except:
                mlflow_ui_ok = False
            
            success = streamlit_ok or mlflow_ui_ok
            details = {
                "streamlit_ui": streamlit_ok,
                "mlflow_ui": mlflow_ui_ok
            }
            
            return {
                "test_name": test_name,
                "success": success,
                "details": details,
                "score": sum(details.values()) / len(details)
            }
            
        except Exception as e:
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "score": 0.0
            }
    
    def test_data_flow(self) -> Dict[str, Any]:
        """测试端到端数据流"""
        test_name = "端到端数据流测试"
        
        try:
            # 1. 生成测试数据
            test_data = {
                "trip_distance": 5.2,
                "passenger_count": 3,
                "pickup_hour": 16,
                "day_of_week": 2,
                "is_weekend": False
            }
            
            # 2. 测试特征获取
            try:
                response = requests.get(
                    f"{self.endpoints['fastapi']}/feast/features/online",
                    params={"entity_id": "test_trip"},
                    timeout=10
                )
                feature_retrieval_ok = response.status_code == 200
            except:
                feature_retrieval_ok = False
            
            # 3. 测试模型预测
            try:
                response = requests.post(
                    f"{self.endpoints['fastapi']}/predict",
                    json={"features": test_data},
                    timeout=10
                )
                prediction_ok = response.status_code == 200
                
                if prediction_ok:
                    result = response.json()
                    has_prediction = "predicted_fare" in result or "prediction" in result
                else:
                    has_prediction = False
            except:
                prediction_ok = False
                has_prediction = False
            
            # 4. 测试指标记录
            try:
                metrics_data = {
                    "model_name": "test-model",
                    "model_version": "1",
                    "metrics": {"rmse": 2.5, "mae": 1.8}
                }
                
                response = requests.post(
                    f"{self.endpoints['fastapi']}/mlflow/models/metrics",
                    json=metrics_data,
                    timeout=10
                )
                metrics_ok = response.status_code == 200
            except:
                metrics_ok = False
            
            success = prediction_ok and has_prediction
            details = {
                "feature_retrieval": feature_retrieval_ok,
                "model_prediction": prediction_ok,
                "prediction_content": has_prediction,
                "metrics_recording": metrics_ok
            }
            
            return {
                "test_name": test_name,
                "success": success,
                "details": details,
                "score": sum(details.values()) / len(details)
            }
            
        except Exception as e:
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "score": 0.0
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有集成测试"""
        print("🚀 开始运行 MLOps 平台集成测试...")
        print("=" * 50)
        
        # 定义测试套件
        test_suite = [
            ("FastAPI 服务", self.test_fastapi_service),
            ("MLflow 服务", self.test_mlflow_service),
            ("Feast 集成", self.test_feast_integration),
            ("Kafka 集成", self.test_kafka_integration),
            ("UI 可访问性", self.test_ui_accessibility),
            ("端到端数据流", self.test_data_flow)
        ]
        
        results = []
        total_score = 0
        
        for test_name, test_func in test_suite:
            print(f"\n🔍 运行测试: {test_name}")
            
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            result["duration"] = duration
            results.append(result)
            total_score += result.get("score", 0)
            
            # 显示测试结果
            if result["success"]:
                print(f"✅ {test_name}: 通过 (评分: {result.get('score', 0):.2f})")
            else:
                print(f"❌ {test_name}: 失败")
                if "error" in result:
                    print(f"   错误: {result['error']}")
            
            if "details" in result:
                for key, value in result["details"].items():
                    status = "✅" if value else "❌"
                    print(f"   {status} {key}: {value}")
        
        # 计算总体评分
        overall_score = total_score / len(test_suite)
        passed_tests = sum(1 for r in results if r["success"])
        
        print("\n" + "=" * 50)
        print("📊 测试总结")
        print("=" * 50)
        print(f"总测试数: {len(test_suite)}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {len(test_suite) - passed_tests}")
        print(f"总体评分: {overall_score:.2f}/1.00")
        print(f"通过率: {passed_tests/len(test_suite)*100:.1f}%")
        
        # 生成建议
        print("\n💡 建议:")
        if overall_score >= 0.8:
            print("✅ 系统集成状态良好，可以进行生产部署")
        elif overall_score >= 0.6:
            print("⚠️  系统基本可用，建议修复失败的测试项")
        else:
            print("❌ 系统存在重大问题，需要修复后再部署")
        
        # 保存测试报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_score": overall_score,
            "passed_tests": passed_tests,
            "total_tests": len(test_suite),
            "results": results
        }
        
        report_file = "logs/integration_test_report.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 详细报告已保存到: {report_file}")
        
        return report


def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    tester = MLOpsIntegrationTester()
    report = tester.run_all_tests()
    
    # 返回适当的退出码
    if report["overall_score"] >= 0.6:
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())
