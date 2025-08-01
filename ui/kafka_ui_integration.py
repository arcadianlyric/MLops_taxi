#!/usr/bin/env python3
"""
Streamlit UI Kafka 流处理集成模块
为 Streamlit 应用提供 Kafka 流处理的可视化和管理功能
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging


class KafkaUIIntegration:
    """Kafka UI 集成类"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(__name__)
    
    def render_kafka_dashboard(self):
        """渲染 Kafka 流处理仪表板"""
        
        st.header("🚀 Kafka 流处理系统")
        
        # 创建标签页
        tabs = st.tabs([
            "📊 集群概览", 
            "📋 主题管理", 
            "🌊 流处理器", 
            "📤 消息发送",
            "🧪 数据生成",
            "📈 实时监控"
        ])
        
        with tabs[0]:
            self._render_cluster_overview()
        
        with tabs[1]:
            self._render_topic_management()
        
        with tabs[2]:
            self._render_stream_processors()
        
        with tabs[3]:
            self._render_message_sender()
        
        with tabs[4]:
            self._render_data_generator()
        
        with tabs[5]:
            self._render_realtime_monitoring()
    
    def _render_cluster_overview(self):
        """渲染集群概览"""
        
        st.subheader("📊 Kafka 集群概览")
        
        try:
            response = requests.get(f"{self.api_base_url}/kafka/info")
            
            if response.status_code == 200:
                cluster_info = response.json()["data"]
                
                # 显示连接状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    kafka_status = "🟢 已连接" if cluster_info.get("client_connected", False) else "🔴 未连接"
                    st.metric("Kafka 状态", kafka_status)
                
                with col2:
                    availability = "🟢 可用" if cluster_info.get("kafka_available", False) else "🔴 不可用"
                    st.metric("Kafka 可用性", availability)
                
                with col3:
                    servers = ", ".join(cluster_info.get("bootstrap_servers", []))
                    st.metric("Bootstrap 服务器", servers)
                
                with col4:
                    status = cluster_info.get("status", "unknown")
                    status_icon = "🟢" if status == "connected" else "🔴"
                    st.metric("整体状态", f"{status_icon} {status}")
                
                # 显示详细信息
                st.subheader("📋 集群详细信息")
                
                cluster_details = pd.DataFrame([
                    {"属性": "Kafka 可用", "值": str(cluster_info.get("kafka_available", False))},
                    {"属性": "客户端连接", "值": str(cluster_info.get("client_connected", False))},
                    {"属性": "Bootstrap 服务器", "值": ", ".join(cluster_info.get("bootstrap_servers", []))},
                    {"属性": "连接状态", "值": cluster_info.get("status", "unknown")}
                ])
                
                st.dataframe(cluster_details, use_container_width=True)
                
            else:
                st.error("无法获取集群信息")
                
        except Exception as e:
            st.error(f"获取集群概览失败: {e}")
    
    def _render_topic_management(self):
        """渲染主题管理"""
        
        st.subheader("📋 Kafka 主题管理")
        
        try:
            response = requests.get(f"{self.api_base_url}/kafka/topics")
            
            if response.status_code == 200:
                topics = response.json()["data"]
                
                if topics:
                    # 创建主题表格
                    topic_data = []
                    for topic in topics:
                        topic_data.append({
                            "主题名称": topic.get("name", ""),
                            "分区数": topic.get("partitions", 0),
                            "副本因子": topic.get("replication_factor", 0),
                            "状态": topic.get("status", "unknown"),
                            "压缩类型": topic.get("config", {}).get("compression.type", "none")
                        })
                    
                    topics_df = pd.DataFrame(topic_data)
                    st.dataframe(topics_df, use_container_width=True)
                    
                    # 主题详情
                    st.subheader("📊 主题详情")
                    
                    selected_topic = st.selectbox(
                        "选择主题查看详情",
                        options=[topic["name"] for topic in topics],
                        key="topic_selector"
                    )
                    
                    if selected_topic:
                        self._show_topic_details(selected_topic)
                
                else:
                    st.info("暂无主题")
                    
            else:
                st.error("无法获取主题列表")
                
        except Exception as e:
            st.error(f"获取主题管理信息失败: {e}")
    
    def _show_topic_details(self, topic_name: str):
        """显示主题详情"""
        try:
            response = requests.get(f"{self.api_base_url}/kafka/topics/{topic_name}")
            
            if response.status_code == 200:
                topic_info = response.json()["data"]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**基本信息:**")
                    st.write(f"- 主题名称: {topic_info.get('name', 'N/A')}")
                    st.write(f"- 分区数: {topic_info.get('partitions', 'N/A')}")
                    st.write(f"- 副本因子: {topic_info.get('replication_factor', 'N/A')}")
                    st.write(f"- 状态: {topic_info.get('status', 'N/A')}")
                
                with col2:
                    st.write("**配置信息:**")
                    config = topic_info.get("config", {})
                    for key, value in config.items():
                        if key in ["cleanup.policy", "retention.ms", "compression.type"]:
                            st.write(f"- {key}: {value}")
            
            else:
                st.error(f"无法获取主题 {topic_name} 的详情")
                
        except Exception as e:
            st.error(f"获取主题详情失败: {e}")
    
    def _render_stream_processors(self):
        """渲染流处理器状态"""
        
        st.subheader("🌊 流处理器状态")
        
        try:
            response = requests.get(f"{self.api_base_url}/kafka/stream-processors")
            
            if response.status_code == 200:
                processors = response.json()["data"]
                
                if processors:
                    # 处理器状态概览
                    col1, col2, col3, col4 = st.columns(4)
                    
                    total_processors = len(processors)
                    running_processors = len([p for p in processors if p["status"] == "running"])
                    total_messages = sum(p["messages_processed"] for p in processors)
                    avg_rate = np.mean([p["processing_rate"] for p in processors])
                    
                    with col1:
                        st.metric("总处理器数", total_processors)
                    
                    with col2:
                        st.metric("运行中", running_processors)
                    
                    with col3:
                        st.metric("总处理消息", f"{total_messages:,}")
                    
                    with col4:
                        st.metric("平均处理速率", f"{avg_rate:.1f} msg/s")
                    
                    # 处理器详情表格
                    st.subheader("📊 处理器详情")
                    
                    processor_data = []
                    for proc in processors:
                        processor_data.append({
                            "处理器名称": proc.get("processor_name", ""),
                            "状态": proc.get("status", ""),
                            "已处理消息": f"{proc.get('messages_processed', 0):,}",
                            "处理速率": f"{proc.get('processing_rate', 0):.1f} msg/s",
                            "错误数": proc.get("error_count", 0)
                        })
                    
                    processors_df = pd.DataFrame(processor_data)
                    st.dataframe(processors_df, use_container_width=True)
                
                else:
                    st.info("暂无流处理器")
                    
            else:
                st.error("无法获取流处理器状态")
                
        except Exception as e:
            st.error(f"获取流处理器状态失败: {e}")
    
    def _render_message_sender(self):
        """渲染消息发送界面"""
        
        st.subheader("📤 消息发送")
        
        # 出租车数据发送
        st.write("**发送出租车行程数据**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trip_id = st.text_input("行程ID", value=f"trip_{int(time.time())}", key="taxi_trip_id")
            pickup_lat = st.number_input("上车纬度", value=41.88, format="%.6f", key="taxi_pickup_lat")
            pickup_lon = st.number_input("上车经度", value=-87.63, format="%.6f", key="taxi_pickup_lon")
            passenger_count = st.number_input("乘客数", value=2, min_value=1, max_value=6, key="taxi_passengers")
        
        with col2:
            trip_distance = st.number_input("行程距离", value=3.5, min_value=0.1, format="%.2f", key="taxi_distance")
            fare_amount = st.number_input("车费", value=12.50, min_value=2.25, format="%.2f", key="taxi_fare")
            payment_type = st.selectbox("支付方式", ["Credit Card", "Cash", "No Charge"], key="taxi_payment")
            company = st.selectbox("出租车公司", ["Flash Cab", "Yellow Cab", "Blue Diamond"], key="taxi_company")
        
        if st.button("🚕 发送出租车数据", key="send_taxi"):
            try:
                pickup_time = datetime.now()
                dropoff_time = pickup_time + timedelta(minutes=np.random.randint(5, 60))
                
                taxi_data = {
                    "trip_id": trip_id,
                    "pickup_datetime": pickup_time.isoformat(),
                    "dropoff_datetime": dropoff_time.isoformat(),
                    "pickup_latitude": pickup_lat,
                    "pickup_longitude": pickup_lon,
                    "dropoff_latitude": pickup_lat + np.random.uniform(-0.01, 0.01),
                    "dropoff_longitude": pickup_lon + np.random.uniform(-0.01, 0.01),
                    "passenger_count": passenger_count,
                    "trip_distance": trip_distance,
                    "fare_amount": fare_amount,
                    "payment_type": payment_type,
                    "company": company
                }
                
                response = requests.post(
                    f"{self.api_base_url}/kafka/messages/taxi-data",
                    json=taxi_data
                )
                
                if response.status_code == 200:
                    st.success("✅ 出租车数据发送成功！")
                    st.json(response.json())
                else:
                    st.error(f"❌ 发送失败: {response.text}")
                    
            except Exception as e:
                st.error(f"❌ 发送失败: {e}")
    
    def _render_data_generator(self):
        """渲染数据生成器"""
        
        st.subheader("🧪 测试数据生成器")
        
        col1, col2 = st.columns(2)
        
        with col1:
            count = st.number_input("生成数据条数", value=50, min_value=1, max_value=1000, key="gen_count")
            
        with col2:
            rate = st.number_input("发送速率 (条/秒)", value=2.0, min_value=0.1, max_value=100.0, key="gen_rate")
        
        estimated_time = count / rate
        st.info(f"预估生成时间: {estimated_time:.1f} 秒")
        
        if st.button("🎲 开始生成测试数据", key="start_generator"):
            try:
                response = requests.post(
                    f"{self.api_base_url}/kafka/generate-test-data",
                    params={"count": count, "rate": rate}
                )
                
                if response.status_code == 200:
                    result = response.json()["data"]
                    st.success("✅ 测试数据生成已启动！")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("数据条数", result["count"])
                    with col2:
                        st.metric("发送速率", f"{result['rate']} 条/秒")
                    with col3:
                        st.metric("预计时长", f"{result['estimated_duration']:.1f} 秒")
                    
                    st.info("数据正在后台生成并发送到 taxi-raw-data 主题")
                else:
                    st.error(f"❌ 生成失败: {response.text}")
                    
            except Exception as e:
                st.error(f"❌ 生成失败: {e}")
    
    def _render_realtime_monitoring(self):
        """渲染实时监控"""
        
        st.subheader("📈 实时流处理监控")
        
        # 自动刷新控制
        auto_refresh = st.checkbox("自动刷新 (30秒)", value=False, key="auto_refresh")
        
        if auto_refresh:
            time.sleep(30)
            st.rerun()
        
        # 刷新按钮
        if st.button("🔄 手动刷新", key="manual_refresh"):
            st.rerun()
        
        # 模拟实时数据
        monitoring_data = self._generate_monitoring_data()
        
        # 实时指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("总消息数", f"{monitoring_data['total_messages']:,}")
        
        with col2:
            st.metric("处理速率", f"{monitoring_data['processing_rate']:.1f} msg/s")
        
        with col3:
            st.metric("错误率", f"{monitoring_data['error_rate']:.2%}")
        
        with col4:
            st.metric("延迟", f"{monitoring_data['latency']:.1f} ms")
        
        # 实时图表
        col1, col2 = st.columns(2)
        
        with col1:
            # 消息吞吐量图表
            fig_throughput = go.Figure()
            fig_throughput.add_trace(go.Scatter(
                x=monitoring_data['timeline'],
                y=monitoring_data['throughput'],
                mode='lines+markers',
                name='吞吐量',
                line=dict(color='blue')
            ))
            fig_throughput.update_layout(
                title="消息吞吐量趋势",
                xaxis_title="时间",
                yaxis_title="消息数/秒"
            )
            st.plotly_chart(fig_throughput, use_container_width=True)
        
        with col2:
            # 延迟图表
            fig_latency = go.Figure()
            fig_latency.add_trace(go.Scatter(
                x=monitoring_data['timeline'],
                y=monitoring_data['latency_trend'],
                mode='lines+markers',
                name='延迟',
                line=dict(color='red')
            ))
            fig_latency.update_layout(
                title="处理延迟趋势",
                xaxis_title="时间",
                yaxis_title="延迟 (ms)"
            )
            st.plotly_chart(fig_latency, use_container_width=True)
    
    def _generate_monitoring_data(self) -> Dict[str, Any]:
        """生成模拟监控数据"""
        
        # 生成时间序列
        now = datetime.now()
        timeline = [now - timedelta(minutes=i) for i in range(30, 0, -1)]
        
        # 生成模拟数据
        throughput = [np.random.uniform(10, 100) for _ in timeline]
        latency_trend = [np.random.uniform(20, 200) for _ in timeline]
        
        return {
            'total_messages': np.random.randint(10000, 100000),
            'processing_rate': np.random.uniform(50, 150),
            'error_rate': np.random.uniform(0, 0.05),
            'latency': np.random.uniform(30, 100),
            'timeline': timeline,
            'throughput': throughput,
            'latency_trend': latency_trend
        }


# 全局实例
kafka_ui = KafkaUIIntegration()
