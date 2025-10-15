#!/usr/bin/env python3
"""
Streamlit UI Feast 特征存储集成模块
为 Streamlit 应用提供 Feast 特征存储的可视化和交互功能
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


class FeastUIIntegration:
    """Feast UI 集成类"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """
        初始化 Feast UI 集成
        
        Args:
            api_base_url: FastAPI 服务基础URL
        """
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(__name__)
    
    def render_feast_dashboard(self):
        """渲染 Feast 特征存储仪表板"""
        
        st.header("🍃 Feast Feature Store")
        st.markdown("Manage and access features for machine learning models")
        
        # 创建标签页
        tabs = st.tabs([
            "📊 Store Overview", 
            "🔍 Feature Views", 
            "⚙️ Feature Services", 
            "🌐 Online Features", 
            "📈 Historical Features",
            "📋 Feature Details"
        ])
        
        with tabs[0]:
            self._render_store_overview()
        
        with tabs[1]:
            self._render_feature_views()
        
        with tabs[2]:
            self._render_feature_services()
        
        with tabs[3]:
            self._render_online_features()
        
        with tabs[4]:
            self._render_historical_features()
        
        with tabs[5]:
            self._render_feature_details()
    
    def _render_store_overview(self):
        """渲染存储概览"""
        
        st.subheader("📊 Feature Store Overview")
        
        try:
            # 获取存储信息
            response = requests.get(f"{self.api_base_url}/feast/info")
            
            if response.status_code == 200:
                data = response.json()["data"]
                
                # 显示连接状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    feast_status = "🟢 Connected" if data.get("store_connected", False) else "🔴 Disconnected"
                    st.metric("Feast Store", feast_status)
                
                with col2:
                    redis_status = "🟢 Connected" if data.get("redis_connected", False) else "🔴 Disconnected"
                    st.metric("Redis Online Store", redis_status)
                
                with col3:
                    st.metric("Feature Views", data.get("feature_views_count", 0))
                
                with col4:
                    st.metric("Feature Services", data.get("feature_services_count", 0))
                
                # 显示状态信息
                status = data.get("status", "unknown")
                if status == "mock_mode":
                    st.warning("⚠️ Running in mock mode - Feast or Redis services are not running")
                    st.info("💡 To enable full functionality, run: `./scripts/start_feast_services.sh`")
                elif status == "connected":
                    st.success("✅ All services connected and running normally")
                elif status == "error":
                    st.error(f"❌ Connection error: {data.get('error', 'Unknown error')}")
                
                # 显示详细信息
                st.subheader("📋 Store Details")
                
                info_data = {
                    "Feast Available": "✅" if data.get("feast_available", False) else "❌",
                    "Redis Available": "✅" if data.get("redis_available", False) else "❌", 
                    "Store Connected": "✅" if data.get("store_connected", False) else "❌",
                    "Redis Connected": "✅" if data.get("redis_connected", False) else "❌",
                    "Repository Path": data.get("repo_path", "Unknown")
                }
                
                info_df = pd.DataFrame(list(info_data.items()), columns=["Property", "Status"])
                st.dataframe(info_df, use_container_width=True)
                
                # 服务启动指南
                if not data.get("store_connected", False) or not data.get("redis_connected", False):
                    with st.expander("🛠️ Service Setup Guide"):
                        st.markdown("""
                        **To start Feast services:**
                        
                        1. **Start Redis and Feast services:**
                           ```bash
                           ./scripts/start_feast_services.sh
                           ```
                        
                        2. **Manual setup (alternative):**
                           ```bash
                           # Start Redis
                           redis-server --daemonize yes
                           
                           # Initialize Feast (in feast/ directory)
                           cd feast
                           feast apply
                           feast ui --host 0.0.0.0 --port 8888
                           ```
                        
                        3. **Check services:**
                           - Redis: `redis-cli ping`
                           - Feast UI: http://localhost:8888
                        """)
                
            else:
                st.error("Unable to retrieve store information")
                st.info("Please ensure the FastAPI backend is running on http://localhost:8000")
                
        except Exception as e:
            st.error(f"Failed to retrieve store overview: {e}")
            st.info("Please check if the FastAPI backend is running and accessible")
    
    def _render_feature_views(self):
        """渲染特征视图"""
        
        st.subheader("🔍 Feature Views")
        
        try:
            response = requests.get(f"{self.api_base_url}/feast/feature-views")
            
            if response.status_code == 200:
                feature_views = response.json()["data"]
                
                if feature_views:
                    # 创建特征视图表格
                    fv_data = []
                    for fv in feature_views:
                        fv_data.append({
                            "name": fv.get("name", ""),
                            "entities": ", ".join(fv.get("entities", [])),
                            "feature count": len(fv.get("features", [])),
                            "ttl (seconds)": fv.get("ttl_seconds", "unlimited"),
                            "tags": str(fv.get("tags", {}))
                        })
                    
                    fv_df = pd.DataFrame(fv_data)
                    st.dataframe(fv_df, use_container_width=True)
                    
                    # 特征视图详情
                    st.subheader("📋 feature view details")
                    
                    selected_fv = st.selectbox(
                        "select feature view to view details",
                        options=[fv["name"] for fv in feature_views],
                        key="fv_selector"
                    )
                    
                    if selected_fv:
                        selected_data = next(fv for fv in feature_views if fv["name"] == selected_fv)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**entities:**")
                            for entity in selected_data.get("entities", []):
                                st.write(f"- {entity}")
                        
                        with col2:
                            st.write("**features:**")
                            for feature in selected_data.get("features", []):
                                st.write(f"- {feature}")
                        
                        if selected_data.get("tags"):
                            st.write("**tags:**")
                            st.json(selected_data["tags"])
                
                else:
                    st.info("no feature views")
                    
            else:
                st.error("failed to retrieve feature views")
                
        except Exception as e:
            st.error(f"failed to retrieve feature views: {e}")
    
    def _render_feature_services(self):
        """渲染特征服务"""
        
        st.subheader("⚙️ feature services")
        
        try:
            response = requests.get(f"{self.api_base_url}/feast/feature-services")
            
            if response.status_code == 200:
                feature_services = response.json()["data"]
                
                if feature_services:
                    # 创建特征服务表格
                    fs_data = []
                    for fs in feature_services:
                        fs_data.append({
                            "name": fs.get("name", ""),
                            "feature count": len(fs.get("features", [])),
                            "tags": str(fs.get("tags", {}))
                        })
                    
                    fs_df = pd.DataFrame(fs_data)
                    st.dataframe(fs_df, use_container_width=True)
                    
                    # 特征服务详情
                    st.subheader("📋 feature service details")
                    
                    selected_fs = st.selectbox(
                        "select feature service to view details",
                        options=[fs["name"] for fs in feature_services],
                        key="fs_selector"
                    )
                    
                    if selected_fs:
                        selected_data = next(fs for fs in feature_services if fs["name"] == selected_fs)
                        
                        st.write("**features:**")
                        for feature in selected_data.get("features", []):
                            st.write(f"- {feature}")
                        
                        if selected_data.get("tags"):
                            st.write("**tags:**")
                            st.json(selected_data["tags"])
                
                else:
                    st.info("no feature services")
                    
            else:
                st.error("failed to retrieve feature services")
                
        except Exception as e:
            st.error(f"failed to retrieve feature services: {e}")
    
    def _render_online_features(self):
        """渲染在线特征查询"""
        
        st.subheader("🌐 online features")
        
        col1, col2 = st.columns(2)
        
        with col1:
            entity_ids = st.text_area(
                "entity ids (one per line)",
                value="trip_000001\ntrip_000002\ntrip_000003",
                height=100
            )
        
        with col2:
            feature_service = st.selectbox(
                "feature service",
                options=["model_inference_v1", "realtime_inference_v1", "monitoring_v1"],
                index=0
            )
        
        if st.button("🔍 query online features", key="query_online"):
            try:
                entity_list = [id.strip() for id in entity_ids.split('\n') if id.strip()]
                
                if not entity_list:
                    st.warning("please enter at least one entity id")
                    return
                
                payload = {
                    "entity_ids": entity_list,
                    "feature_service": feature_service
                }
                
                response = requests.post(
                    f"{self.api_base_url}/feast/online-features",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()["data"]
                    
                    st.success(f"successfully retrieved online features for {len(entity_list)} entities")
                    
                    # 显示特征数据
                    if "features" in data:
                        features_data = data["features"]
                        
                        # 转换为表格格式
                        if features_data:
                            rows = []
                            for entity_id, features in features_data.items():
                                if isinstance(features, dict):
                                    row = {"entity id": entity_id}
                                    row.update(features)
                                    rows.append(row)
                            
                            if rows:
                                features_df = pd.DataFrame(rows)
                                st.dataframe(features_df, use_container_width=True)
                                
                                # 下载按钮
                                csv = features_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 download feature data",
                                    data=csv,
                                    file_name=f"online_features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            else:
                                st.info("no feature data")
                        else:
                            st.info("feature data is empty")
                    else:
                        st.json(data)
                
                else:
                    st.error(f"failed to query online features: {response.text}")
                    
            except Exception as e:
                st.error(f"failed to query online features: {e}")
    
    def _render_historical_features(self):
        """渲染历史特征查询"""
        
        st.subheader("📈 historical features")
        
        st.info("historical features query is used for model training and batch inference scenarios")
        
        # 实体数据输入
        st.write("**entity data (JSON format):**")
        entity_data_json = st.text_area(
            "entity data",
            value=json.dumps({
                "trip_id": ["trip_000001", "trip_000002", "trip_000003"],
                "event_timestamp": [
                    datetime.now().isoformat(),
                    (datetime.now() - timedelta(hours=1)).isoformat(),
                    (datetime.now() - timedelta(hours=2)).isoformat()
                ]
            }, indent=2),
            height=150
        )
        
        # 特征列表
        features_list = st.text_area(
            "features list (one per line)",
            value="trip_features:trip_miles\ntrip_features:trip_seconds\ntrip_features:fare",
            height=100
        )
        
        if st.button("🔍 query historical features", key="query_historical"):
            try:
                # 解析输入
                entity_data = json.loads(entity_data_json)
                features = [f.strip() for f in features_list.split('\n') if f.strip()]
                
                if not features:
                    st.warning("please enter at least one feature")
                    return
                
                payload = {
                    "entity_data": entity_data,
                    "features": features
                }
                
                response = requests.post(
                    f"{self.api_base_url}/feast/historical-features",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()["data"]
                    
                    st.success("successfully retrieved historical features")
                    
                    if "features" in data and data["features"]:
                        # 显示特征数据
                        features_df = pd.DataFrame(data["features"])
                        st.dataframe(features_df, use_container_width=True)
                        
                        # 显示统计信息
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("data row count", data.get("shape", [0])[0])
                        with col2:
                            st.metric("feature column count", data.get("shape", [0, 0])[1])
                        with col3:
                            st.metric("request feature count", len(features))
                        
                        # 下载按钮
                        csv = features_df.to_csv(index=False)
                        st.download_button(
                            label="📥 download historical features data",
                            data=csv,
                            file_name=f"historical_features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("no historical features data")
                        st.json(data)
                
                else:
                    st.error(f"failed to query historical features: {response.text}")
                    
            except json.JSONDecodeError:
                st.error("invalid entity data JSON format")
            except Exception as e:
                st.error(f"failed to query historical features: {e}")
    
    def _render_feature_details(self):
        """渲染特征详情和统计"""
        
        st.subheader("📋 entity details and statistics")
        
        try:
            response = requests.get(f"{self.api_base_url}/feast/stats")
            
            if response.status_code == 200:
                stats = response.json()["data"]
                
                # 显示统计概览
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("feature views count", stats.get("feature_views_count", 0))
                
                with col2:
                    st.metric("feature services count", stats.get("feature_services_count", 0))
                
                with col3:
                    status_color = "🟢" if stats.get("status") == "healthy" else "🔴"
                    st.metric("storage status", f"{status_color} {stats.get('status', 'unknown')}")
                
                # 显示特征视图列表
                if stats.get("feature_views"):
                    st.subheader("📊 feature views list")
                    fv_df = pd.DataFrame({
                        "feature views": stats["feature_views"]
                    })
                    st.dataframe(fv_df, use_container_width=True)
                
                # 显示特征服务列表
                if stats.get("feature_services"):
                    st.subheader("⚙️ feature services list")
                    fs_df = pd.DataFrame({
                        "feature services": stats["feature_services"]
                    })
                    st.dataframe(fs_df, use_container_width=True)
                
                # 显示存储信息
                st.subheader("🏪 storage info")
                store_info = stats.get("feature_store_info", {})
                
                info_items = []
                for key, value in store_info.items():
                    info_items.append({"property": key, "value": str(value)})
                
                if info_items:
                    info_df = pd.DataFrame(info_items)
                    st.dataframe(info_df, use_container_width=True)
            
            else:
                st.error("failed to retrieve feature statistics")
                
        except Exception as e:
            st.error(f"failed to retrieve feature details: {e}")
    
    def render_feature_monitoring(self):
        """渲染特征监控面板"""
        
        st.subheader("📊 feature monitoring")
        
        # 模拟特征监控数据
        monitoring_data = self._generate_monitoring_data()
        
        # 特征使用统计
        col1, col2 = st.columns(2)
        
        with col1:
            # 特征访问频次
            fig_access = px.bar(
                monitoring_data["feature_access"],
                x="feature name",
                y="access count",
                title="feature access frequency"
            )
            st.plotly_chart(fig_access, use_container_width=True)
        
        with col2:
            # 特征响应时间
            fig_latency = px.line(
                monitoring_data["response_time"],
                x="time",
                y="response time(ms)",
                title="feature query response time"
            )
            st.plotly_chart(fig_latency, use_container_width=True)
        
        # 特征质量监控
        st.subheader("🔍 feature quality monitoring")
        
        quality_metrics = monitoring_data["quality_metrics"]
        quality_df = pd.DataFrame(quality_metrics)
        
        st.dataframe(quality_df, use_container_width=True)
    
    def _generate_monitoring_data(self) -> Dict[str, Any]:
        """生成模拟监控数据"""
        
        # 特征访问统计
        feature_names = ["trip_miles", "trip_seconds", "fare", "pickup_hour", "passenger_count"]
        access_counts = np.random.randint(100, 1000, len(feature_names))
        
        feature_access = pd.DataFrame({
            "feature name": feature_names,
            "access count": access_counts
        })
        
        # 响应时间数据
        time_points = pd.date_range(start=datetime.now() - timedelta(hours=24), 
                                  end=datetime.now(), freq='H')
        response_times = np.random.normal(50, 15, len(time_points))
        
        response_time = pd.DataFrame({
            "time": time_points,
            "response time(ms)": response_times
        })
        
        # 特征质量指标
        quality_metrics = []
        for feature in feature_names:
            quality_metrics.append({
                "feature name": feature,
                "completeness": f"{np.random.uniform(0.95, 1.0):.3f}",
                "accuracy": f"{np.random.uniform(0.90, 1.0):.3f}",
                "consistency": f"{np.random.uniform(0.85, 1.0):.3f}",
                "timeliness": f"{np.random.uniform(0.90, 1.0):.3f}"
            })
        
        return {
            "feature_access": feature_access,
            "response_time": response_time,
            "quality_metrics": quality_metrics
        }


# 全局实例
feast_ui = FeastUIIntegration()
