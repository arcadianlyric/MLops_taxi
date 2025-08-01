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
        
        st.header("🍽️ Feast 特征存储")
        
        # 创建标签页
        tabs = st.tabs([
            "📊 存储概览", 
            "🔍 特征视图", 
            "⚙️ 特征服务", 
            "🌐 在线特征", 
            "📈 历史特征",
            "📋 特征详情"
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
        
        st.subheader("📊 特征存储概览")
        
        try:
            # 获取存储信息
            response = requests.get(f"{self.api_base_url}/feast/info")
            
            if response.status_code == 200:
                data = response.json()["data"]
                
                # 显示连接状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    feast_status = "🟢 已连接" if data.get("store_connected", False) else "🔴 未连接"
                    st.metric("Feast 存储", feast_status)
                
                with col2:
                    redis_status = "🟢 已连接" if data.get("redis_connected", False) else "🔴 未连接"
                    st.metric("Redis 在线存储", redis_status)
                
                with col3:
                    st.metric("特征视图数量", data.get("feature_views_count", 0))
                
                with col4:
                    st.metric("特征服务数量", data.get("feature_services_count", 0))
                
                # 显示详细信息
                st.subheader("📋 存储详细信息")
                
                info_data = {
                    "Feast 可用": data.get("feast_available", False),
                    "Redis 可用": data.get("redis_available", False),
                    "存储已连接": data.get("store_connected", False),
                    "Redis 已连接": data.get("redis_connected", False),
                    "仓库路径": data.get("repo_path", "未知")
                }
                
                info_df = pd.DataFrame(list(info_data.items()), columns=["项目", "状态"])
                st.dataframe(info_df, use_container_width=True)
                
            else:
                st.error("无法获取存储信息")
                
        except Exception as e:
            st.error(f"获取存储概览失败: {e}")
    
    def _render_feature_views(self):
        """渲染特征视图"""
        
        st.subheader("🔍 特征视图")
        
        try:
            response = requests.get(f"{self.api_base_url}/feast/feature-views")
            
            if response.status_code == 200:
                feature_views = response.json()["data"]
                
                if feature_views:
                    # 创建特征视图表格
                    fv_data = []
                    for fv in feature_views:
                        fv_data.append({
                            "名称": fv.get("name", ""),
                            "实体": ", ".join(fv.get("entities", [])),
                            "特征数量": len(fv.get("features", [])),
                            "TTL (秒)": fv.get("ttl_seconds", "无限制"),
                            "标签": str(fv.get("tags", {}))
                        })
                    
                    fv_df = pd.DataFrame(fv_data)
                    st.dataframe(fv_df, use_container_width=True)
                    
                    # 特征视图详情
                    st.subheader("📋 特征视图详情")
                    
                    selected_fv = st.selectbox(
                        "选择特征视图查看详情",
                        options=[fv["name"] for fv in feature_views],
                        key="fv_selector"
                    )
                    
                    if selected_fv:
                        selected_data = next(fv for fv in feature_views if fv["name"] == selected_fv)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**实体:**")
                            for entity in selected_data.get("entities", []):
                                st.write(f"- {entity}")
                        
                        with col2:
                            st.write("**特征:**")
                            for feature in selected_data.get("features", []):
                                st.write(f"- {feature}")
                        
                        if selected_data.get("tags"):
                            st.write("**标签:**")
                            st.json(selected_data["tags"])
                
                else:
                    st.info("暂无特征视图")
                    
            else:
                st.error("无法获取特征视图")
                
        except Exception as e:
            st.error(f"获取特征视图失败: {e}")
    
    def _render_feature_services(self):
        """渲染特征服务"""
        
        st.subheader("⚙️ 特征服务")
        
        try:
            response = requests.get(f"{self.api_base_url}/feast/feature-services")
            
            if response.status_code == 200:
                feature_services = response.json()["data"]
                
                if feature_services:
                    # 创建特征服务表格
                    fs_data = []
                    for fs in feature_services:
                        fs_data.append({
                            "名称": fs.get("name", ""),
                            "特征数量": len(fs.get("features", [])),
                            "标签": str(fs.get("tags", {}))
                        })
                    
                    fs_df = pd.DataFrame(fs_data)
                    st.dataframe(fs_df, use_container_width=True)
                    
                    # 特征服务详情
                    st.subheader("📋 特征服务详情")
                    
                    selected_fs = st.selectbox(
                        "选择特征服务查看详情",
                        options=[fs["name"] for fs in feature_services],
                        key="fs_selector"
                    )
                    
                    if selected_fs:
                        selected_data = next(fs for fs in feature_services if fs["name"] == selected_fs)
                        
                        st.write("**包含的特征:**")
                        for feature in selected_data.get("features", []):
                            st.write(f"- {feature}")
                        
                        if selected_data.get("tags"):
                            st.write("**标签:**")
                            st.json(selected_data["tags"])
                
                else:
                    st.info("暂无特征服务")
                    
            else:
                st.error("无法获取特征服务")
                
        except Exception as e:
            st.error(f"获取特征服务失败: {e}")
    
    def _render_online_features(self):
        """渲染在线特征查询"""
        
        st.subheader("🌐 在线特征查询")
        
        col1, col2 = st.columns(2)
        
        with col1:
            entity_ids = st.text_area(
                "实体ID列表 (每行一个)",
                value="trip_000001\ntrip_000002\ntrip_000003",
                height=100
            )
        
        with col2:
            feature_service = st.selectbox(
                "特征服务",
                options=["model_inference_v1", "realtime_inference_v1", "monitoring_v1"],
                index=0
            )
        
        if st.button("🔍 查询在线特征", key="query_online"):
            try:
                entity_list = [id.strip() for id in entity_ids.split('\n') if id.strip()]
                
                if not entity_list:
                    st.warning("请输入至少一个实体ID")
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
                    
                    st.success(f"成功获取 {len(entity_list)} 个实体的在线特征")
                    
                    # 显示特征数据
                    if "features" in data:
                        features_data = data["features"]
                        
                        # 转换为表格格式
                        if features_data:
                            rows = []
                            for entity_id, features in features_data.items():
                                if isinstance(features, dict):
                                    row = {"实体ID": entity_id}
                                    row.update(features)
                                    rows.append(row)
                            
                            if rows:
                                features_df = pd.DataFrame(rows)
                                st.dataframe(features_df, use_container_width=True)
                                
                                # 下载按钮
                                csv = features_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 下载特征数据",
                                    data=csv,
                                    file_name=f"online_features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            else:
                                st.info("未获取到特征数据")
                        else:
                            st.info("特征数据为空")
                    else:
                        st.json(data)
                
                else:
                    st.error(f"查询失败: {response.text}")
                    
            except Exception as e:
                st.error(f"查询在线特征失败: {e}")
    
    def _render_historical_features(self):
        """渲染历史特征查询"""
        
        st.subheader("📈 历史特征查询")
        
        st.info("历史特征查询用于模型训练和批量推理场景")
        
        # 实体数据输入
        st.write("**实体数据 (JSON 格式):**")
        entity_data_json = st.text_area(
            "实体数据",
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
            "特征列表 (每行一个)",
            value="trip_features:trip_miles\ntrip_features:trip_seconds\ntrip_features:fare",
            height=100
        )
        
        if st.button("🔍 查询历史特征", key="query_historical"):
            try:
                # 解析输入
                entity_data = json.loads(entity_data_json)
                features = [f.strip() for f in features_list.split('\n') if f.strip()]
                
                if not features:
                    st.warning("请输入至少一个特征")
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
                    
                    st.success("历史特征查询成功")
                    
                    if "features" in data and data["features"]:
                        # 显示特征数据
                        features_df = pd.DataFrame(data["features"])
                        st.dataframe(features_df, use_container_width=True)
                        
                        # 显示统计信息
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("数据行数", data.get("shape", [0])[0])
                        with col2:
                            st.metric("特征列数", data.get("shape", [0, 0])[1])
                        with col3:
                            st.metric("请求特征数", len(features))
                        
                        # 下载按钮
                        csv = features_df.to_csv(index=False)
                        st.download_button(
                            label="📥 下载历史特征数据",
                            data=csv,
                            file_name=f"historical_features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("未获取到历史特征数据")
                        st.json(data)
                
                else:
                    st.error(f"查询失败: {response.text}")
                    
            except json.JSONDecodeError:
                st.error("实体数据 JSON 格式错误")
            except Exception as e:
                st.error(f"查询历史特征失败: {e}")
    
    def _render_feature_details(self):
        """渲染特征详情和统计"""
        
        st.subheader("📋 特征详情和统计")
        
        try:
            response = requests.get(f"{self.api_base_url}/feast/stats")
            
            if response.status_code == 200:
                stats = response.json()["data"]
                
                # 显示统计概览
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("特征视图", stats.get("feature_views_count", 0))
                
                with col2:
                    st.metric("特征服务", stats.get("feature_services_count", 0))
                
                with col3:
                    status_color = "🟢" if stats.get("status") == "healthy" else "🔴"
                    st.metric("存储状态", f"{status_color} {stats.get('status', 'unknown')}")
                
                # 显示特征视图列表
                if stats.get("feature_views"):
                    st.subheader("📊 特征视图列表")
                    fv_df = pd.DataFrame({
                        "特征视图": stats["feature_views"]
                    })
                    st.dataframe(fv_df, use_container_width=True)
                
                # 显示特征服务列表
                if stats.get("feature_services"):
                    st.subheader("⚙️ 特征服务列表")
                    fs_df = pd.DataFrame({
                        "特征服务": stats["feature_services"]
                    })
                    st.dataframe(fs_df, use_container_width=True)
                
                # 显示存储信息
                st.subheader("🏪 存储信息")
                store_info = stats.get("feature_store_info", {})
                
                info_items = []
                for key, value in store_info.items():
                    info_items.append({"属性": key, "值": str(value)})
                
                if info_items:
                    info_df = pd.DataFrame(info_items)
                    st.dataframe(info_df, use_container_width=True)
            
            else:
                st.error("无法获取特征统计信息")
                
        except Exception as e:
            st.error(f"获取特征详情失败: {e}")
    
    def render_feature_monitoring(self):
        """渲染特征监控面板"""
        
        st.subheader("📊 特征监控")
        
        # 模拟特征监控数据
        monitoring_data = self._generate_monitoring_data()
        
        # 特征使用统计
        col1, col2 = st.columns(2)
        
        with col1:
            # 特征访问频次
            fig_access = px.bar(
                monitoring_data["feature_access"],
                x="特征名称",
                y="访问次数",
                title="特征访问频次"
            )
            st.plotly_chart(fig_access, use_container_width=True)
        
        with col2:
            # 特征响应时间
            fig_latency = px.line(
                monitoring_data["response_time"],
                x="时间",
                y="响应时间(ms)",
                title="特征查询响应时间"
            )
            st.plotly_chart(fig_latency, use_container_width=True)
        
        # 特征质量监控
        st.subheader("🔍 特征质量监控")
        
        quality_metrics = monitoring_data["quality_metrics"]
        quality_df = pd.DataFrame(quality_metrics)
        
        st.dataframe(quality_df, use_container_width=True)
    
    def _generate_monitoring_data(self) -> Dict[str, Any]:
        """生成模拟监控数据"""
        
        # 特征访问统计
        feature_names = ["trip_miles", "trip_seconds", "fare", "pickup_hour", "passenger_count"]
        access_counts = np.random.randint(100, 1000, len(feature_names))
        
        feature_access = pd.DataFrame({
            "特征名称": feature_names,
            "访问次数": access_counts
        })
        
        # 响应时间数据
        time_points = pd.date_range(start=datetime.now() - timedelta(hours=24), 
                                  end=datetime.now(), freq='H')
        response_times = np.random.normal(50, 15, len(time_points))
        
        response_time = pd.DataFrame({
            "时间": time_points,
            "响应时间(ms)": response_times
        })
        
        # 特征质量指标
        quality_metrics = []
        for feature in feature_names:
            quality_metrics.append({
                "特征名称": feature,
                "完整性": f"{np.random.uniform(0.95, 1.0):.3f}",
                "准确性": f"{np.random.uniform(0.90, 1.0):.3f}",
                "一致性": f"{np.random.uniform(0.85, 1.0):.3f}",
                "及时性": f"{np.random.uniform(0.90, 1.0):.3f}"
            })
        
        return {
            "feature_access": feature_access,
            "response_time": response_time,
            "quality_metrics": quality_metrics
        }


# 全局实例
feast_ui = FeastUIIntegration()
