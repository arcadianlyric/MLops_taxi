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
