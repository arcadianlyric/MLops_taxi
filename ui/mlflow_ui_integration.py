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
        """渲染 MLflow 模型注册中心仪表板"""
        
        st.header("🎯 MLflow 模型注册中心")
        
        # 创建标签页
        tabs = st.tabs([
            "📊 服务概览",
            "🧪 实验管理", 
            "📦 模型注册",
            "🔄 模型版本",
            "📈 模型指标",
            "🚀 模型预测"
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
        """渲染服务概览"""
        
        st.subheader("📊 MLflow 服务概览")
        
        try:
            # 获取服务信息
            response = requests.get(f"{self.api_base_url}/mlflow/info")
            
            if response.status_code == 200:
                service_info = response.json()["data"]
                
                # 显示服务状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    mlflow_status = "🟢 可用" if service_info.get("mlflow_available", False) else "🔴 不可用"
                    st.metric("MLflow 可用性", mlflow_status)
                
                with col2:
                    client_status = "🟢 已连接" if service_info.get("client_connected", False) else "🔴 未连接"
                    st.metric("客户端状态", client_status)
                
                with col3:
                    tracking_uri = service_info.get("tracking_uri", "N/A")
                    st.metric("Tracking URI", tracking_uri)
                
                with col4:
                    status = service_info.get("status", "unknown")
                    status_icon = "🟢" if status == "connected" else "🔴"
                    st.metric("整体状态", f"{status_icon} {status}")
                
                # 显示详细信息
                st.subheader("📋 服务详细信息")
                
                service_details = pd.DataFrame([
                    {"属性": "MLflow 可用", "值": str(service_info.get("mlflow_available", False))},
                    {"属性": "客户端连接", "值": str(service_info.get("client_connected", False))},
                    {"属性": "Tracking URI", "值": service_info.get("tracking_uri", "N/A")},
                    {"属性": "服务状态", "值": service_info.get("status", "unknown")}
                ])
                
                st.dataframe(service_details, use_container_width=True)
                
            else:
                st.error("无法获取服务信息")
                
        except Exception as e:
            st.error(f"获取服务概览失败: {e}")
    
    def _render_experiment_management(self):
        """渲染实验管理"""
        
        st.subheader("🧪 实验管理")
        
        # 获取实验列表
        try:
            response = requests.get(f"{self.api_base_url}/mlflow/experiments")
            
            if response.status_code == 200:
                experiments = response.json()["data"]
                
                if experiments:
                    # 实验概览
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("总实验数", len(experiments))
                    
                    with col2:
                        active_experiments = len([e for e in experiments if e.get("lifecycle_stage") == "active"])
                        st.metric("活跃实验", active_experiments)
                    
                    with col3:
                        # 计算最近更新时间
                        if experiments:
                            latest_update = max(e.get("last_update_time", 0) for e in experiments)
                            latest_date = datetime.fromtimestamp(latest_update / 1000).strftime("%Y-%m-%d")
                            st.metric("最近更新", latest_date)
                    
                    # 实验列表
                    st.subheader("📋 实验列表")
                    
                    experiment_data = []
                    for exp in experiments:
                        creation_time = datetime.fromtimestamp(exp.get("creation_time", 0) / 1000)
                        last_update = datetime.fromtimestamp(exp.get("last_update_time", 0) / 1000)
                        
                        experiment_data.append({
                            "实验ID": exp.get("experiment_id", ""),
                            "实验名称": exp.get("name", ""),
                            "生命周期": exp.get("lifecycle_stage", ""),
                            "创建时间": creation_time.strftime("%Y-%m-%d %H:%M"),
                            "最后更新": last_update.strftime("%Y-%m-%d %H:%M"),
                            "标签数": len(exp.get("tags", {}))
                        })
                    
                    experiments_df = pd.DataFrame(experiment_data)
                    st.dataframe(experiments_df, use_container_width=True)
                    
                    # 实验详情
                    selected_exp = st.selectbox(
                        "选择实验查看详情",
                        options=[exp["name"] for exp in experiments],
                        key="exp_selector"
                    )
                    
                    if selected_exp:
                        exp_info = next(e for e in experiments if e["name"] == selected_exp)
                        self._show_experiment_details(exp_info)
                
                else:
                    st.info("暂无实验")
                    
            else:
                st.error("无法获取实验列表")
                
        except Exception as e:
            st.error(f"获取实验管理信息失败: {e}")
        
        # 创建新实验
        self._render_create_experiment_form()
    
    def _show_experiment_details(self, experiment: Dict[str, Any]):
        """显示实验详情"""
        
        st.subheader(f"📊 实验详情: {experiment['name']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**基本信息:**")
            st.write(f"- 实验ID: {experiment.get('experiment_id', 'N/A')}")
            st.write(f"- 生命周期: {experiment.get('lifecycle_stage', 'N/A')}")
            st.write(f"- 存储位置: {experiment.get('artifact_location', 'N/A')}")
        
        with col2:
            st.write("**标签信息:**")
            tags = experiment.get("tags", {})
            if tags:
                for key, value in tags.items():
                    st.write(f"- {key}: {value}")
            else:
                st.write("- 无标签")
    
    def _render_create_experiment_form(self):
        """渲染创建实验表单"""
        
        st.subheader("➕ 创建新实验")
        
        with st.form("create_experiment_form"):
            exp_name = st.text_input("实验名称", placeholder="例如: taxi-model-v2")
            exp_description = st.text_area("实验描述", placeholder="描述实验目的和内容")
            
            # 标签输入
            st.write("**实验标签:**")
            col1, col2 = st.columns(2)
            with col1:
                tag_key = st.text_input("标签键", placeholder="例如: model_type")
            with col2:
                tag_value = st.text_input("标签值", placeholder="例如: regression")
            
            submitted = st.form_submit_button("🚀 创建实验")
            
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
                        st.success(f"✅ 实验 '{exp_name}' 创建成功！")
                        st.rerun()
                    else:
                        st.error(f"❌ 创建失败: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ 创建实验失败: {e}")
    
    def _render_model_registry(self):
        """渲染模型注册"""
        
        st.subheader("📦 模型注册中心")
        
        try:
            response = requests.get(f"{self.api_base_url}/mlflow/models")
            
            if response.status_code == 200:
                models = response.json()["data"]
                
                if models:
                    # 模型概览
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("注册模型数", len(models))
                    
                    with col2:
                        production_models = sum(
                            1 for model in models 
                            for version in model.get("latest_versions", [])
                            if version.get("stage") == "Production"
                        )
                        st.metric("生产模型", production_models)
                    
                    with col3:
                        staging_models = sum(
                            1 for model in models 
                            for version in model.get("latest_versions", [])
                            if version.get("stage") == "Staging"
                        )
                        st.metric("测试模型", staging_models)
                    
                    with col4:
                        total_versions = sum(len(model.get("latest_versions", [])) for model in models)
                        st.metric("总版本数", total_versions)
                    
                    # 模型列表
                    st.subheader("📋 注册模型列表")
                    
                    model_data = []
                    for model in models:
                        latest_versions = model.get("latest_versions", [])
                        production_version = next(
                            (v["version"] for v in latest_versions if v["stage"] == "Production"),
                            "无"
                        )
                        staging_version = next(
                            (v["version"] for v in latest_versions if v["stage"] == "Staging"),
                            "无"
                        )
                        
                        creation_time = datetime.fromtimestamp(
                            model.get("creation_timestamp", 0) / 1000
                        ).strftime("%Y-%m-%d")
                        
                        model_data.append({
                            "模型名称": model.get("name", ""),
                            "描述": model.get("description", "")[:50] + "..." if len(model.get("description", "")) > 50 else model.get("description", ""),
                            "生产版本": production_version,
                            "测试版本": staging_version,
                            "总版本数": len(latest_versions),
                            "创建时间": creation_time
                        })
                    
                    models_df = pd.DataFrame(model_data)
                    st.dataframe(models_df, use_container_width=True)
                    
                    # 模型详情
                    selected_model = st.selectbox(
                        "选择模型查看详情",
                        options=[model["name"] for model in models],
                        key="model_selector"
                    )
                    
                    if selected_model:
                        model_info = next(m for m in models if m["name"] == selected_model)
                        self._show_model_details(model_info)
                
                else:
                    st.info("暂无注册模型")
                    
            else:
                st.error("无法获取模型列表")
                
        except Exception as e:
            st.error(f"获取模型注册信息失败: {e}")
    
    def _show_model_details(self, model: Dict[str, Any]):
        """显示模型详情"""
        
        st.subheader(f"📊 模型详情: {model['name']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**基本信息:**")
            st.write(f"- 模型名称: {model.get('name', 'N/A')}")
            st.write(f"- 描述: {model.get('description', 'N/A')}")
            creation_time = datetime.fromtimestamp(model.get('creation_timestamp', 0) / 1000)
            st.write(f"- 创建时间: {creation_time.strftime('%Y-%m-%d %H:%M')}")
        
        with col2:
            st.write("**标签信息:**")
            tags = model.get("tags", {})
            if tags:
                for key, value in tags.items():
                    st.write(f"- {key}: {value}")
            else:
                st.write("- 无标签")
        
        # 版本信息
        st.write("**版本信息:**")
        versions = model.get("latest_versions", [])
        if versions:
            version_data = []
            for version in versions:
                creation_time = datetime.fromtimestamp(version.get('creation_timestamp', 0) / 1000)
                version_data.append({
                    "版本": version.get("version", ""),
                    "阶段": version.get("stage", ""),
                    "描述": version.get("description", ""),
                    "创建时间": creation_time.strftime("%Y-%m-%d %H:%M"),
                    "运行ID": version.get("run_id", "")[:8] + "..." if version.get("run_id") else ""
                })
            
            versions_df = pd.DataFrame(version_data)
            st.dataframe(versions_df, use_container_width=True)
        else:
            st.write("- 无版本信息")
    
    def _render_model_versions(self):
        """渲染模型版本管理"""
        
        st.subheader("🔄 模型版本管理")
        
        # 获取模型列表
        try:
            response = requests.get(f"{self.api_base_url}/mlflow/models")
            
            if response.status_code == 200:
                models = response.json()["data"]
                
                if models:
                    selected_model = st.selectbox(
                        "选择模型",
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
                                # 版本统计
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("总版本数", len(versions))
                                
                                with col2:
                                    production_count = len([v for v in versions if v["stage"] == "Production"])
                                    st.metric("生产版本", production_count)
                                
                                with col3:
                                    staging_count = len([v for v in versions if v["stage"] == "Staging"])
                                    st.metric("测试版本", staging_count)
                                
                                with col4:
                                    archived_count = len([v for v in versions if v["stage"] == "Archived"])
                                    st.metric("归档版本", archived_count)
                                
                                # 版本列表
                                st.subheader("📋 版本列表")
                                
                                version_data = []
                                for version in versions:
                                    creation_time = datetime.fromtimestamp(
                                        version.get("creation_timestamp", 0) / 1000
                                    ).strftime("%Y-%m-%d %H:%M")
                                    
                                    version_data.append({
                                        "版本": version.get("version", ""),
                                        "阶段": version.get("stage", ""),
                                        "描述": version.get("description", ""),
                                        "创建时间": creation_time,
                                        "运行ID": version.get("run_id", "")[:12] + "..." if version.get("run_id") else "",
                                        "标签数": len(version.get("tags", {}))
                                    })
                                
                                versions_df = pd.DataFrame(version_data)
                                st.dataframe(versions_df, use_container_width=True)
                                
                                # 阶段更新
                                self._render_stage_update_form(selected_model, versions)
                                
                                # 版本趋势图
                                self._render_version_trends(versions)
                            
                            else:
                                st.info(f"模型 {selected_model} 暂无版本")
                        else:
                            st.error("无法获取模型版本")
                
                else:
                    st.info("暂无注册模型")
                    
            else:
                st.error("无法获取模型列表")
                
        except Exception as e:
            st.error(f"获取模型版本信息失败: {e}")
    
    def _render_stage_update_form(self, model_name: str, versions: List[Dict]):
        """渲染阶段更新表单"""
        
        st.subheader("🔄 更新模型阶段")
        
        with st.form("update_stage_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                selected_version = st.selectbox(
                    "选择版本",
                    options=[v["version"] for v in versions],
                    key="stage_version_selector"
                )
            
            with col2:
                new_stage = st.selectbox(
                    "新阶段",
                    options=["None", "Staging", "Production", "Archived"],
                    key="new_stage_selector"
                )
            
            submitted = st.form_submit_button("🚀 更新阶段")
            
            if submitted and selected_version and new_stage:
                try:
                    response = requests.post(
                        f"{self.api_base_url}/mlflow/models/{model_name}/versions/{selected_version}/stage",
                        params={"stage": new_stage}
                    )
                    
                    if response.status_code == 200:
                        st.success(f"✅ 模型 {model_name} 版本 {selected_version} 阶段更新为 {new_stage}！")
                        st.rerun()
                    else:
                        st.error(f"❌ 更新失败: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ 更新阶段失败: {e}")
    
    def _render_version_trends(self, versions: List[Dict]):
        """渲染版本趋势图"""
        
        st.subheader("📈 版本趋势")
        
        # 按阶段统计
        stage_counts = {}
        for version in versions:
            stage = version.get("stage", "None")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        if stage_counts:
            fig_stages = px.pie(
                values=list(stage_counts.values()),
                names=list(stage_counts.keys()),
                title="版本阶段分布"
            )
            st.plotly_chart(fig_stages, use_container_width=True)
        
        # 时间趋势
        if len(versions) > 1:
            version_times = []
            for version in versions:
                creation_time = datetime.fromtimestamp(version.get("creation_timestamp", 0) / 1000)
                version_times.append({
                    "版本": version.get("version", ""),
                    "创建时间": creation_time,
                    "阶段": version.get("stage", "None")
                })
            
            version_times_df = pd.DataFrame(version_times)
            version_times_df = version_times_df.sort_values("创建时间")
            
            fig_timeline = px.scatter(
                version_times_df,
                x="创建时间",
                y="版本",
                color="阶段",
                title="版本创建时间线",
                hover_data=["阶段"]
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
    
    def _render_model_metrics(self):
        """渲染模型指标"""
        
        st.subheader("📈 模型指标管理")
        
        # 指标记录表单
        st.subheader("📝 记录模型指标")
        
        with st.form("log_metrics_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                model_name = st.text_input("模型名称", placeholder="chicago-taxi-fare-predictor")
                model_version = st.text_input("模型版本", placeholder="1")
            
            with col2:
                metric_name = st.text_input("指标名称", placeholder="rmse")
                metric_value = st.number_input("指标值", value=0.0, format="%.4f")
            
            submitted = st.form_submit_button("📊 记录指标")
            
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
                        st.success(f"✅ 指标记录成功！")
                        st.json(response.json())
                    else:
                        st.error(f"❌ 记录失败: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ 记录指标失败: {e}")
        
        # 模拟指标可视化
        self._render_metrics_visualization()
    
    def _render_metrics_visualization(self):
        """渲染指标可视化"""
        
        st.subheader("📊 模型性能指标")
        
        # 生成模拟指标数据
        metrics_data = self._generate_mock_metrics()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # RMSE 趋势
            fig_rmse = px.line(
                metrics_data,
                x="版本",
                y="RMSE",
                title="RMSE 趋势",
                markers=True
            )
            st.plotly_chart(fig_rmse, use_container_width=True)
        
        with col2:
            # 准确率趋势
            fig_accuracy = px.line(
                metrics_data,
                x="版本",
                y="准确率",
                title="准确率趋势",
                markers=True
            )
            st.plotly_chart(fig_accuracy, use_container_width=True)
        
        # 指标对比
        st.subheader("📈 版本指标对比")
        
        fig_comparison = make_subplots(
            rows=1, cols=2,
            subplot_titles=("RMSE 对比", "准确率对比"),
            specs=[[{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        fig_comparison.add_trace(
            go.Bar(x=metrics_data["版本"], y=metrics_data["RMSE"], name="RMSE"),
            row=1, col=1
        )
        
        fig_comparison.add_trace(
            go.Bar(x=metrics_data["版本"], y=metrics_data["准确率"], name="准确率"),
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
            "版本": versions,
            "RMSE": rmse_values,
            "准确率": accuracy_values
        })
    
    def _render_model_prediction(self):
        """渲染模型预测"""
        
        st.subheader("🚀 模型预测测试")
        
        # 预测表单
        with st.form("model_prediction_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                model_name = st.text_input("模型名称", value="chicago-taxi-fare-predictor")
                model_version = st.text_input("模型版本", value="latest")
                model_stage = st.selectbox("模型阶段", ["Production", "Staging", "None"])
            
            with col2:
                st.write("**输入特征:**")
                trip_distance = st.number_input("行程距离", value=3.5, min_value=0.1)
                passenger_count = st.number_input("乘客数", value=2, min_value=1, max_value=6)
                pickup_hour = st.number_input("上车小时", value=14, min_value=0, max_value=23)
            
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
                        
                        st.success("✅ 预测成功！")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("预测费用", f"${result['prediction']:.2f}")
                        
                        with col2:
                            st.metric("置信度", f"{result['confidence']:.2%}")
                        
                        with col3:
                            st.metric("模型版本", result['model_version'])
                        
                        # 显示详细结果
                        st.subheader("📊 预测详情")
                        st.json(result)
                        
                    else:
                        st.error(f"❌ 预测失败: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ 预测失败: {e}")


# 全局实例
mlflow_ui = MLflowUIIntegration()
