#!/usr/bin/env python3
"""
Streamlit UI MLflow 模型注册中心集成模块
为 Streamlit 应用提供 MLflow 模型管理的可视化功能
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging


class MLflowUIIntegration:
    """MLflow UI 集成类"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """
        初始化 MLflow UI 集成
        
        Args:
            api_base_url: FastAPI 服务基础URL
        """
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(__name__)
    
    def render_mlflow_dashboard(self):
        """render MLflow model registry dashboard"""
        
        st.header("🎯 MLflow model registry")
        
        # create tabs
        tabs = st.tabs([
            "📊 service overview",
            "🧪 experiment management", 
            "📦 model registry",
            "🔄 model versions",
            "📈 model metrics",
            "🚀 model prediction"
        ])
        
        with tabs[0]:
            self._render_service_overview()
        
        with tabs[1]:
            self._render_experiment_management()
        
        with tabs[2]:
            self._render_model_registry()
        
        with tabs[3]:
            self._render_model_versions()
        
        with tabs[4]:
            self._render_model_metrics()
        
        with tabs[5]:
            self._render_model_prediction()
    
    def _render_service_overview(self):
        """render service overview"""
        
        st.subheader("📊 MLflow service overview")
        
        try:
            # get service info
            response = requests.get(f"{self.api_base_url}/mlflow/info")
            
            if response.status_code == 200:
                service_info = response.json()["data"]
                
                # 显示服务状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    mlflow_status = "🟢 available" if service_info.get("mlflow_available", False) else "🔴 不可用"
                    st.metric("MLflow available", mlflow_status)
                
                with col2:
                    client_status = "🟢 connected" if service_info.get("client_connected", False) else "🔴 未连接"
                    st.metric("client status", client_status)
                
                with col3:
                    tracking_uri = service_info.get("tracking_uri", "N/A")
                    st.metric("Tracking URI", tracking_uri)
                
                with col4:
                    status = service_info.get("status", "unknown")
                    status_icon = "🟢" if status == "connected" else "🔴"
                    st.metric("status", f"{status_icon} {status}")
                
                # show service details
                st.subheader("📋 service details")
                
                service_details = pd.DataFrame([
                    {"attribute": "MLflow available", "value": str(service_info.get("mlflow_available", False))},
                    {"attribute": "client connected", "value": str(service_info.get("client_connected", False))},
                    {"attribute": "tracking uri", "value": service_info.get("tracking_uri", "N/A")},
                    {"attribute": "status", "value": service_info.get("status", "unknown")}
                ])
                
                st.dataframe(service_details, use_container_width=True)
                
            else:
                st.error("无法获取服务信息")
                
        except Exception as e:
            st.error(f"get service overview failed: {e}")
    
    def _render_experiment_management(self):
        """render experiment management"""
        
        st.subheader("🧪 experiment management")
        
        # get experiment list
        try:
            response = requests.get(f"{self.api_base_url}/mlflow/experiments")
            
            if response.status_code == 200:
                experiments = response.json()["data"]
                
                if experiments:
                    # 实验概览
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("experiments", len(experiments))
                    
                    with col2:
                        active_experiments = len([e for e in experiments if e.get("lifecycle_stage") == "active"])
                        st.metric("active experiments", active_experiments)
                    
                    with col3:
                        # 计算最近更新时间
                        if experiments:
                            latest_update = max(e.get("last_update_time", 0) for e in experiments)
                            latest_date = datetime.fromtimestamp(latest_update / 1000).strftime("%Y-%m-%d")
                            st.metric("latest date", latest_date)
                    
                    # 实验列表
                    st.subheader("📋 experiment list")
                    
                    experiment_data = []
                    for exp in experiments:
                        creation_time = datetime.fromtimestamp(exp.get("creation_time", 0) / 1000)
                        last_update = datetime.fromtimestamp(exp.get("last_update_time", 0) / 1000)
                        
                        experiment_data.append({
                            "experiment id": exp.get("experiment_id", ""),
                            "experiment name": exp.get("name", ""),
                            "lifecycle stage": exp.get("lifecycle_stage", ""),
                            "creation time": creation_time.strftime("%Y-%m-%d %H:%M"),
                            "last update": last_update.strftime("%Y-%m-%d %H:%M"),
                            "tags": len(exp.get("tags", {}))
                        })
                    
                    experiments_df = pd.DataFrame(experiment_data)
                    st.dataframe(experiments_df, use_container_width=True)
                    
                    # experiment details
                    selected_exp = st.selectbox(
                        "select experiment to view details",
                        options=[exp["name"] for exp in experiments],
                        key="exp_selector"
                    )
                    
                    if selected_exp:
                        exp_info = next(e for e in experiments if e["name"] == selected_exp)
                        self._show_experiment_details(exp_info)
                
                else:
                    st.info("no experiments")
                    
            else:
                st.error("failed to get experiment list")
                
        except Exception as e:
            st.error(f"failed to get experiment management info: {e}")
        
        # create new experiment
        self._render_create_experiment_form()
    
    def _show_experiment_details(self, experiment: Dict[str, Any]):
        """show experiment details"""
        
        st.subheader(f"📊 experiment details: {experiment['name']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**basic information:**")
            st.write(f"- experiment id: {experiment.get('experiment_id', 'N/A')}")
            st.write(f"- lifecycle stage: {experiment.get('lifecycle_stage', 'N/A')}")
            st.write(f"- artifact location: {experiment.get('artifact_location', 'N/A')}")
        
        with col2:
            st.write("**tags:**")
            tags = experiment.get("tags", {})
            if tags:
                for key, value in tags.items():
                    st.write(f"- {key}: {value}")
            else:
                st.write("- no tags")
    
    def _render_create_experiment_form(self):
        """render create experiment form"""
        
        st.subheader("➕ create new experiment")
        
        with st.form("create_experiment_form"):
            exp_name = st.text_input("experiment name", placeholder="例如: taxi-model-v2")
            exp_description = st.text_area("experiment description", placeholder="describe experiment purpose and content")
            
            # tag input
            st.write("**experiment tag:**")
            col1, col2 = st.columns(2)
            with col1:
                tag_key = st.text_input("tag key", placeholder="for example: model_type")
            with col2:
                tag_value = st.text_input("tag value", placeholder="for example: regression")
            
            submitted = st.form_submit_button("🚀 create experiment")
            
            if submitted and exp_name:
                try:
                    tags = {}
                    if tag_key and tag_value:
                        tags[tag_key] = tag_value
                    
                    payload = {
                        "name": exp_name,
                        "description": exp_description,
                        "tags": tags
                    }
                    
                    response = requests.post(
                        f"{self.api_base_url}/mlflow/experiments",
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        st.success(f"✅ experiment '{exp_name}' created successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ create experiment failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ create experiment failed: {e}")
    
    def _render_model_registry(self):
        """render model registry"""
        
        st.subheader("📦 model registry")
        
        try:
            response = requests.get(f"{self.api_base_url}/mlflow/models")
            
            if response.status_code == 200:
                models = response.json()["data"]
                
                if models:
                    # model overview
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("registered models", len(models))
                    
                    with col2:
                        production_models = sum(
                            1 for model in models 
                            for version in model.get("latest_versions", [])
                            if version.get("stage") == "Production"
                        )
                        st.metric("production models", production_models)
                    
                    with col3:
                        staging_models = sum(
                            1 for model in models 
                            for version in model.get("latest_versions", [])
                            if version.get("stage") == "Staging"
                        )
                        st.metric("staging models", staging_models)
                    
                    with col4:
                        total_versions = sum(len(model.get("latest_versions", [])) for model in models)
                        st.metric("total versions", total_versions)
                    
                    # registered model list
                    st.subheader("📋 registered model list")
                    
                    model_data = []
                    for model in models:
                        latest_versions = model.get("latest_versions", [])
                        production_version = next(
                            (v["version"] for v in latest_versions if v["stage"] == "Production"),
                            "No"
                        )
                        staging_version = next(
                            (v["version"] for v in latest_versions if v["stage"] == "Staging"),
                            "No"
                        )
                        
                        creation_time = datetime.fromtimestamp(
                            model.get("creation_timestamp", 0) / 1000
                        ).strftime("%Y-%m-%d")
                        
                        model_data.append({
                            "model name": model.get("name", ""),
                            "description": model.get("description", "")[:50] + "..." if len(model.get("description", "")) > 50 else model.get("description", ""),
                            "production version": production_version,
                            "staging version": staging_version,
                            "total versions": len(latest_versions),
                            "creation time": creation_time
                        })
                    
                    models_df = pd.DataFrame(model_data)
                    st.dataframe(models_df, use_container_width=True)
                    
                    # model details
                    selected_model = st.selectbox(
                        "select model to view details",
                        options=[model["name"] for model in models],
                        key="model_selector"
                    )
                    
                    if selected_model:
                        model_info = next(m for m in models if m["name"] == selected_model)
                        self._show_model_details(model_info)
                
                else:
                    st.info("no registered models")
                    
            else:
                st.error("failed to get model list")
                
        except Exception as e:
            st.error(f"failed to get model registry info: {e}")
    
    def _show_model_details(self, model: Dict[str, Any]):
        """show model details"""
        
        st.subheader(f"📊 model details: {model['name']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**basic information:**")
            st.write(f"- model name: {model.get('name', 'N/A')}")
            st.write(f"- description: {model.get('description', 'N/A')}")
            creation_time = datetime.fromtimestamp(model.get('creation_timestamp', 0) / 1000)
            st.write(f"- creation time: {creation_time.strftime('%Y-%m-%d %H:%M')}")
        
        with col2:
            st.write("**tags:**")
            tags = model.get("tags", {})
            if tags:
                for key, value in tags.items():
                    st.write(f"- {key}: {value}")
            else:
                st.write("- no tags")
        
        # version information
        st.write("**version information:**")
        versions = model.get("latest_versions", [])
        if versions:
            version_data = []
            for version in versions:
                creation_time = datetime.fromtimestamp(version.get('creation_timestamp', 0) / 1000)
                version_data.append({
                    "version": version.get("version", ""),
                    "stage": version.get("stage", ""),
                    "description": version.get("description", ""),
                    "creation time": creation_time.strftime("%Y-%m-%d %H:%M"),
                    "run id": version.get("run_id", "")[:8] + "..." if version.get("run_id") else ""
                })
            
            versions_df = pd.DataFrame(version_data)
            st.dataframe(versions_df, use_container_width=True)
        else:
            st.write("- no version information")
    
    def _render_model_versions(self):
        """render model versions"""
        
        st.subheader("🔄 model versions")
        
        # 获取模型列表
        try:
            response = requests.get(f"{self.api_base_url}/mlflow/models")
            
            if response.status_code == 200:
                models = response.json()["data"]
                
                if models:
                    selected_model = st.selectbox(
                        "select model",
                        options=[model["name"] for model in models],
                        key="version_model_selector"
                    )
                    
                    if selected_model:
                        # 获取模型版本
                        versions_response = requests.get(
                            f"{self.api_base_url}/mlflow/models/{selected_model}/versions"
                        )
                        
                        if versions_response.status_code == 200:
                            versions = versions_response.json()["data"]
                            
                            if versions:
                                # version statistics
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("total versions", len(versions))
                                
                                with col2:
                                    production_count = len([v for v in versions if v["stage"] == "Production"])
                                    st.metric("production versions", production_count)
                                
                                with col3:
                                    staging_count = len([v for v in versions if v["stage"] == "Staging"])
                                    st.metric("staging versions", staging_count)
                                
                                with col4:
                                    archived_count = len([v for v in versions if v["stage"] == "Archived"])
                                    st.metric("archived versions", archived_count)
                                
                                # version list
                                st.subheader("📋 version list")
                                
                                version_data = []
                                for version in versions:
                                    creation_time = datetime.fromtimestamp(
                                        version.get("creation_timestamp", 0) / 1000
                                    ).strftime("%Y-%m-%d %H:%M")
                                    
                                    version_data.append({
                                        "version": version.get("version", ""),
                                        "stage": version.get("stage", ""),
                                        "description": version.get("description", ""),
                                        "creation time": creation_time,
                                        "run id": version.get("run_id", "")[:12] + "..." if version.get("run_id") else "",
                                        "tags": len(version.get("tags", {}))
                                    })
                                
                                versions_df = pd.DataFrame(version_data)
                                st.dataframe(versions_df, use_container_width=True)
                                
                                # 阶段更新
                                self._render_stage_update_form(selected_model, versions)
                                
                                # 版本趋势图
                                self._render_version_trends(versions)
                            
                            else:
                                st.info(f"model {selected_model} has no versions")
                        else:
                            st.error("failed to get model versions")
                
                else:
                    st.info("no registered models")
                    
            else:
                st.error("failed to get model list")
                
        except Exception as e:
            st.error(f"failed to get model versions: {e}")
    
    def _render_stage_update_form(self, model_name: str, versions: List[Dict]):
        """render stage update form"""
        
        st.subheader("🔄 update model stage")
        
        with st.form("update_stage_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                selected_version = st.selectbox(
                    "select version",
                    options=[v["version"] for v in versions],
                    key="stage_version_selector"
                )
            
            with col2:
                new_stage = st.selectbox(
                    "select new stage",
                    options=["None", "Staging", "Production", "Archived"],
                    key="new_stage_selector"
                )
            
            submitted = st.form_submit_button("🚀 update stage")
            
            if submitted and selected_version and new_stage:
                try:
                    response = requests.post(
                        f"{self.api_base_url}/mlflow/models/{model_name}/versions/{selected_version}/stage",
                        params={"stage": new_stage}
                    )
                    
                    if response.status_code == 200:
                        st.success(f"✅ model {model_name} version {selected_version} stage updated to {new_stage}!")
                        st.rerun()
                    else:
                        st.error(f"❌ update failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ update stage failed: {e}")
    
    def _render_version_trends(self, versions: List[Dict]):
        """render version trends"""
        
        st.subheader("📈 version trends")
        
        # 按阶段统计
        stage_counts = {}
        for version in versions:
            stage = version.get("stage", "None")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        if stage_counts:
            fig_stages = px.pie(
                values=list(stage_counts.values()),
                names=list(stage_counts.keys()),
                title="model distribution"
            )
            st.plotly_chart(fig_stages, use_container_width=True)
        
        # 时间趋势
        if len(versions) > 1:
            version_times = []
            for version in versions:
                creation_time = datetime.fromtimestamp(version.get("creation_timestamp", 0) / 1000)
                version_times.append({
                    "version": version.get("version", ""),
                    "creation time": creation_time,
                    "stage": version.get("stage", "None")
                })
            
            version_times_df = pd.DataFrame(version_times)
            version_times_df = version_times_df.sort_values("creation time")
            
            fig_timeline = px.scatter(
                version_times_df,
                x="creation time",
                y="version",
                color="stage",
                title="version timeline",
                hover_data=["stage"]
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
    
    def _render_model_metrics(self):
        """render model metrics"""
        
        st.subheader("📈 model metrics")
        
        # metric record form
        st.subheader("📝 record model metrics")
        
        with st.form("log_metrics_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                model_name = st.text_input("model name", placeholder="chicago-taxi-fare-predictor")
                model_version = st.text_input("model version", placeholder="1")
            
            with col2:
                metric_name = st.text_input("metric name", placeholder="rmse")
                metric_value = st.number_input("metric value", value=0.0, format="%.4f")
            
            submitted = st.form_submit_button("📊 record metrics")
            
            if submitted and model_name and model_version and metric_name:
                try:
                    payload = {
                        "model_name": model_name,
                        "model_version": model_version,
                        "metrics": {metric_name: metric_value}
                    }
                    
                    response = requests.post(
                        f"{self.api_base_url}/mlflow/models/metrics",
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        st.success(f"✅ metrics record success!")
                        st.json(response.json())
                    else:
                        st.error(f"❌ record failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ record failed: {e}")
        
        # 模拟指标可视化
        self._render_metrics_visualization()
    
    def _render_metrics_visualization(self):
        """render metrics visualization"""
        
        st.subheader("📊 model metrics visualization")
        
        # 生成模拟指标数据
        metrics_data = self._generate_mock_metrics()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # RMSE 趋势
            fig_rmse = px.line(
                metrics_data,
                x="version",
                y="rmse",
                title="RMSE trend",
                markers=True
            )
            st.plotly_chart(fig_rmse, use_container_width=True)
        
        with col2:
            # 准确率趋势
            fig_accuracy = px.line(
                metrics_data,
                x="version",
                y="accuracy",
                title="accuracy trend",
                markers=True
            )
            st.plotly_chart(fig_accuracy, use_container_width=True)
        
        # 指标对比
        st.subheader("📈 version metrics comparison")
        
        fig_comparison = make_subplots(
            rows=1, cols=2,
            subplot_titles=("RMSE comparison", "accuracy comparison"),
            specs=[[{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        fig_comparison.add_trace(
            go.Bar(x=metrics_data["version"], y=metrics_data["rmse"], name="RMSE"),
            row=1, col=1
        )
        
        fig_comparison.add_trace(
            go.Bar(x=metrics_data["version"], y=metrics_data["accuracy"], name="accuracy"),
            row=1, col=2
        )
        
        fig_comparison.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_comparison, use_container_width=True)
    
    def _generate_mock_metrics(self) -> pd.DataFrame:
        """生成模拟指标数据"""
        
        versions = ["v1", "v2", "v3", "v4"]
        rmse_values = [3.2, 2.8, 2.1, 1.9]
        accuracy_values = [0.85, 0.89, 0.92, 0.94]
        
        return pd.DataFrame({
            "version": versions,
            "rmse": rmse_values,
            "accuracy": accuracy_values
        })
    
    def _render_model_prediction(self):
        """渲染模型预测"""
        
        st.subheader("🚀 模型预测测试")
        
        # 预测表单
        with st.form("model_prediction_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                model_name = st.text_input("model name", value="chicago-taxi-fare-predictor")
                model_version = st.text_input("model version", value="latest")
                model_stage = st.selectbox("model stage", ["Production", "Staging", "None"])
            
            with col2:
                st.write("**input features:**")
                trip_distance = st.number_input("trip distance", value=3.5, min_value=0.1)
                passenger_count = st.number_input("passenger count", value=2, min_value=1, max_value=6)
                pickup_hour = st.number_input("pickup hour", value=14, min_value=0, max_value=23)
            
            submitted = st.form_submit_button("🎯 开始预测")
            
            if submitted and model_name:
                try:
                    payload = {
                        "model_name": model_name,
                        "model_version": model_version,
                        "model_stage": model_stage,
                        "input_data": {
                            "trip_distance": trip_distance,
                            "passenger_count": passenger_count,
                            "pickup_hour": pickup_hour
                        }
                    }
                    
                    response = requests.post(
                        f"{self.api_base_url}/mlflow/models/predict",
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()["data"]
                        
                        st.success("✅ prediction success!")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("prediction", f"${result['prediction']:.2f}")
                        
                        with col2:
                            st.metric("confidence", f"{result['confidence']:.2%}")
                        
                        with col3:
                            st.metric("model version", result['model_version'])
                        
                        # 显示详细结果
                        st.subheader("📊 prediction details")
                        st.json(result)
                        
                    else:
                        st.error(f"❌ prediction failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ prediction failed: {e}")


# global instance
mlflow_ui = MLflowUIIntegration()
