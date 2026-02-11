#!/usr/bin/env python3
"""
Streamlit UI Kafka 流处理集成模块
为 Streamlit 应用提供 Kafka 流处理的可视化和管理功能
"""

import os
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
        
        st.header("🚀 Kafka stream system")
        
        # 创建标签页
        tabs = st.tabs([
            "📊 cluster overview", 
            "📋 topic management", 
            "🌊 stream processors", 
            "📤 message sender",
            "🧪 data generator",
            "📈 realtime monitoring"
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
        
        st.subheader("📊 Kafka cluster overview")
        
        try:
            response = requests.get(f"{self.api_base_url}/kafka/info")
            
            if response.status_code == 200:
                cluster_info = response.json()["data"]
                
                # 显示连接状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    kafka_status = "🟢 connected" if cluster_info.get("client_connected", False) else "🔴 disconnected"
                    st.metric("Kafka status", kafka_status)
                
                with col2:
                    availability = "🟢 available" if cluster_info.get("kafka_available", False) else "🔴 unavailable"
                    st.metric("Kafka availability", availability)
                
                with col3:
                    servers = ", ".join(cluster_info.get("bootstrap_servers", []))
                    st.metric("Bootstrap server", servers)
                
                with col4:
                    status = cluster_info.get("status", "unknown")
                    status_icon = "🟢" if status == "connected" else "🔴"
                    st.metric("overall status", f"{status_icon} {status}")
                
                # 显示详细信息
                st.subheader("📋 cluster details")
                
                cluster_details = pd.DataFrame([
                    {"attribute": "Kafka available", "value": str(cluster_info.get("kafka_available", False))},
                    {"attribute": "client connected", "value": str(cluster_info.get("client_connected", False))},
                    {"attribute": "Bootstrap server", "value": ", ".join(cluster_info.get("bootstrap_servers", []))},
                    {"attribute": "connection status", "value": cluster_info.get("status", "unknown")}
                ])
                
                st.dataframe(cluster_details, use_container_width=True)
                
            else:
                st.error("unable to collect cluster info")
                
        except Exception as e:
            st.error(f"failed to collect cluster info: {e}")
    
    def _render_topic_management(self):
        """渲染主题管理"""
        
        st.subheader("📋 Kafka topic management")
        
        try:
            response = requests.get(f"{self.api_base_url}/kafka/topics")
            
            if response.status_code == 200:
                topics = response.json()["data"]
                
                if topics:
                    # 创建主题表格
                    topic_data = []
                    for topic in topics:
                        topic_data.append({
                            "topic name": topic.get("name", ""),
                            "partitions": topic.get("partitions", 0),
                            "replication factor": topic.get("replication_factor", 0),
                            "status": topic.get("status", "unknown"),
                            "compression type": topic.get("config", {}).get("compression.type", "none")
                        })
                    
                    topics_df = pd.DataFrame(topic_data)
                    st.dataframe(topics_df, use_container_width=True)
                    
                    # topic details
                    st.subheader("📊 topic details")
                    
                    selected_topic = st.selectbox(
                        "select topic to view details",
                        options=[topic["name"] for topic in topics],
                        key="topic_selector"
                    )
                    
                    if selected_topic:
                        self._show_topic_details(selected_topic)
                
                else:
                    st.info("no topics found")
                    
            else:
                st.error("failed to collect topic list")
                
        except Exception as e:
            st.error(f"failed to collect topic list: {e}")
    
    def _show_topic_details(self, topic_name: str):
        """显示主题详情"""
        try:
            response = requests.get(f"{self.api_base_url}/kafka/topics/{topic_name}")
            
            if response.status_code == 200:
                topic_info = response.json()["data"]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**basic information:**")
                    st.write(f"- topic name: {topic_info.get('name', 'N/A')}")
                    st.write(f"- partitions: {topic_info.get('partitions', 'N/A')}")
                    st.write(f"- replication factor: {topic_info.get('replication_factor', 'N/A')}")
                    st.write(f"- status: {topic_info.get('status', 'N/A')}")
                
                with col2:
                    st.write("**configuration:**")
                    config = topic_info.get("config", {})
                    for key, value in config.items():
                        if key in ["cleanup.policy", "retention.ms", "compression.type"]:
                            st.write(f"- {key}: {value}")
            
            else:
                st.error(f"failed to collect topic details: {topic_name}")
                
        except Exception as e:
            st.error(f"failed to collect topic details: {e}")
    
    def _render_stream_processors(self):
        """渲染流处理器状态"""
        
        st.subheader("🌊 stream processor status")
        
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
                        st.metric("total processors", total_processors)
                    
                    with col2:
                        st.metric("running", running_processors)
                    
                    with col3:
                        st.metric("total messages processed", f"{total_messages:,}")
                    
                    with col4:
                        st.metric("average processing rate", f"{avg_rate:.1f} msg/s")
                    
                    # processor details table
                    st.subheader("📊 processor details")
                    
                    processor_data = []
                    for proc in processors:
                        processor_data.append({
                            "processor name": proc.get("processor_name", ""),
                            "status": proc.get("status", ""),
                            "messages processed": f"{proc.get('messages_processed', 0):,}",
                            "processing rate": f"{proc.get('processing_rate', 0):.1f} msg/s",
                            "error count": proc.get("error_count", 0)
                        })
                    
                    processors_df = pd.DataFrame(processor_data)
                    st.dataframe(processors_df, use_container_width=True)
                
                else:
                    st.info("no stream processors found")
                    
            else:
                st.error("failed to collect stream processor status")
                
        except Exception as e:
            st.error(f"failed to collect stream processor status: {e}")
    
    def _render_message_sender(self):
        """渲染消息发送界面"""
        
        st.subheader("📤 message sender")
        
        # 出租车数据发送
        st.write("**send taxi trip data**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trip_id = st.text_input("trip id", value=f"trip_{int(time.time())}", key="taxi_trip_id")
            pickup_lat = st.number_input("pickup latitude", value=41.88, format="%.6f", key="taxi_pickup_lat")
            pickup_lon = st.number_input("pickup longitude", value=-87.63, format="%.6f", key="taxi_pickup_lon")
            passenger_count = st.number_input("passenger count", value=2, min_value=1, max_value=6, key="taxi_passengers")
        
        with col2:
            trip_distance = st.number_input("trip distance", value=3.5, min_value=0.1, format="%.2f", key="taxi_distance")
            fare_amount = st.number_input("fare amount", value=12.50, min_value=2.25, format="%.2f", key="taxi_fare")
            payment_type = st.selectbox("payment type", ["Credit Card", "Cash", "No Charge"], key="taxi_payment")
            company = st.selectbox("taxi company", ["Flash Cab", "Yellow Cab", "Blue Diamond"], key="taxi_company")
        
        if st.button("🚕 send taxi data", key="send_taxi"):
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
                    st.success("✅ taxi data sent successfully!")
                    st.json(response.json())
                else:
                    st.error(f"❌ send failed: {response.text}")
                    
            except Exception as e:
                st.error(f"❌ send failed: {e}")
    
    def _render_data_generator(self):
        """渲染数据生成器"""
        
        st.subheader("🧪 test data generator")
        
        col1, col2 = st.columns(2)
        
        with col1:
            count = st.number_input("count", value=50, min_value=1, max_value=1000, key="gen_count")
            
        with col2:
            rate = st.number_input("rate (count/second)", value=2.0, min_value=0.1, max_value=100.0, key="gen_rate")
        
        estimated_time = count / rate
        st.info(f"estimated time: {estimated_time:.1f} seconds")
        
        if st.button("🎲 start test data generation", key="start_generator"):
            try:
                response = requests.post(
                    f"{self.api_base_url}/kafka/generate-test-data",
                    params={"count": count, "rate": rate}
                )
                
                if response.status_code == 200:
                    result = response.json()["data"]
                    st.success("✅ test data generation started!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("count", result["count"])
                    with col2:
                        st.metric("rate (count/second)", f"{result['rate']} 条/秒")
                    with col3:
                        st.metric("estimated duration", f"{result['estimated_duration']:.1f} seconds")
                    
                    st.info("data is being generated and sent to taxi-raw-data topic in the background")
                else:
                    st.error(f"❌ failed: {response.text}")
                    
            except Exception as e:
                st.error(f"❌ failed: {e}")
    
    def _render_realtime_monitoring(self):
        """渲染实时监控"""
        
        st.subheader("📈 realtime stream processing monitoring")
        
        # 自动刷新控制
        auto_refresh = st.checkbox("auto refresh (30 seconds)", value=False, key="auto_refresh")
        
        if auto_refresh:
            time.sleep(30)
            st.rerun()
        
        # 刷新按钮
        if st.button("🔄 manual refresh", key="manual_refresh"):
            st.rerun()
        
        # 模拟实时数据
        monitoring_data = self._generate_monitoring_data()
        
        # 实时指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("total messages", f"{monitoring_data['total_messages']:,}")
        
        with col2:
            st.metric("processing rate", f"{monitoring_data['processing_rate']:.1f} msg/s")
        
        with col3:
            st.metric("error rate", f"{monitoring_data['error_rate']:.2%}")
        
        with col4:
            st.metric("latency", f"{monitoring_data['latency']:.1f} ms")
        
        # 实时图表
        col1, col2 = st.columns(2)
        
        with col1:
            # 消息吞吐量图表
            fig_throughput = go.Figure()
            fig_throughput.add_trace(go.Scatter(
                x=monitoring_data['timeline'],
                y=monitoring_data['throughput'],
                mode='lines+markers',
                name='throughput',
                line=dict(color='blue')
            ))
            fig_throughput.update_layout(
                title="message throughput trend",
                xaxis_title="time",
                yaxis_title="messages per second"
            )
            st.plotly_chart(fig_throughput, use_container_width=True)
        
        with col2:
            # 延迟图表
            fig_latency = go.Figure()
            fig_latency.add_trace(go.Scatter(
                x=monitoring_data['timeline'],
                y=monitoring_data['latency_trend'],
                mode='lines+markers',
                name='latency',
                line=dict(color='red')
            ))
            fig_latency.update_layout(
                title="processing latency trend",
                xaxis_title="time",
                yaxis_title="latency (ms)"
            )
            st.plotly_chart(fig_latency, use_container_width=True)
    
    def _generate_monitoring_data(self) -> Dict[str, Any]:
        """generate mock monitoring data"""
        
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
kafka_ui = KafkaUIIntegration(api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"))
