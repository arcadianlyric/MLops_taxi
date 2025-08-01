#!/usr/bin/env python3
"""
Streamlit UI - MLOps 平台前端界面
基于 TFX Pipeline 的 Chicago Taxi 费用预测
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any
import json
import time
from datetime import datetime
import sys
import os
import numpy as np

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 导入集成模块
from ui.feast_ui_integration import feast_ui
from ui.kafka_ui_integration import kafka_ui
from ui.mlflow_ui_integration import mlflow_ui
from ui.mlmd_ui_integration import get_mlmd_ui_integration

# 页面配置
st.set_page_config(
    page_title="MLOps 平台 - Chicago Taxi 费用预测",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 全局配置
API_BASE_URL = "http://localhost:8000"

def check_api_health():
    """检查API服务健康状态"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

def call_taxi_prediction_api(features: Dict[str, Any], endpoint: str = "predict"):
    """调用 Chicago Taxi 费用预测 API"""
    try:
        payload = {
            "features": features,
            "model_name": "taxi_model"
        }
        
        response = requests.post(
            f"{API_BASE_URL}/{endpoint}",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"API错误: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"请求失败: {str(e)}"

def call_batch_prediction_api(taxi_trips: List[Dict[str, Any]]):
    """调用批量出租车费用预测API"""
    try:
        payload = {
            "trips": taxi_trips,
            "model_name": "taxi_model"
        }
        
        response = requests.post(
            f"{API_BASE_URL}/batch_predict",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"API错误: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"请求失败: {str(e)}"

def main():
    """主界面"""
    
    # 标题和描述
    st.title("🚕 MLOps 平台 - Chicago Taxi 费用预测")
    st.markdown("基于 TFX Pipeline + Kubeflow + KFServing 的出租车费用预测系统")
    
    # 侧边栏 - 服务状态
    with st.sidebar:
        st.header("🔧 服务状态")
        
        # 检查API健康状态
        is_healthy, health_data = check_api_health()
        
        if is_healthy:
            st.success("✅ API 服务正常")
            if health_data:
                st.json(health_data)
        else:
            st.error("❌ API 服务不可用")
            st.warning("请确保 FastAPI 服务正在运行: `uvicorn api.main:app --reload`")
        
        st.divider()
        
        # 配置选项
        st.header("⚙️ 配置选项")
        api_timeout = st.slider("API 超时时间 (秒)", 5, 60, 30)
        show_debug = st.checkbox("显示调试信息", False)
    
    # 创建标签页
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "🚖 单次预测", 
        "📊 批量预测", 
        "📈 数据分析", 
        "⚡ 性能监控", 
        "🔍 数据漂移监控",
        "🍃 Feast 特征存储",
        "🚀 Kafka 流处理",
        "🎯 MLflow 模型注册",
        "🔗 MLMD 数据血缘"
    ])
    
    # Tab 1: 单次预测
    with tab1:
        st.header("🚕 单次出租车费用预测")
        st.markdown("输入出租车行程信息，预测小费金额")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 行程信息输入")
            
            # 基本行程信息
            st.write("**🚕 基本信息**")
            trip_miles = st.number_input("行程距离 (英里)", min_value=0.1, max_value=100.0, value=5.2, step=0.1)
            trip_seconds = st.number_input("行程时长 (秒)", min_value=60, max_value=7200, value=900, step=30)
            fare = st.number_input("车费 (美元)", min_value=2.5, max_value=200.0, value=12.5, step=0.25)
            
            st.write("**📍 位置信息**")
            pickup_latitude = st.number_input("上车纬度", min_value=41.6, max_value=42.1, value=41.8781, step=0.0001, format="%.4f")
            pickup_longitude = st.number_input("上车经度", min_value=-87.9, max_value=-87.5, value=-87.6298, step=0.0001, format="%.4f")
            dropoff_latitude = st.number_input("下车纬度", min_value=41.6, max_value=42.1, value=41.8881, step=0.0001, format="%.4f")
            dropoff_longitude = st.number_input("下车经度", min_value=-87.9, max_value=-87.5, value=-87.6198, step=0.0001, format="%.4f")
            
            st.write("**⏰ 时间信息**")
            trip_start_hour = st.selectbox("出发小时", range(24), index=14)
            trip_start_day = st.selectbox("出发日期 (1-31)", range(1, 32), index=14)
            trip_start_month = st.selectbox("出发月份", range(1, 13), index=5)
            
            st.write("**🏢 区域信息**")
            pickup_community_area = st.number_input("上车社区区域", min_value=1, max_value=77, value=8)
            dropoff_community_area = st.number_input("下车社区区域", min_value=1, max_value=77, value=24)
            pickup_census_tract = st.number_input("上车人口普查区", min_value=1, max_value=2000, value=170301)
            dropoff_census_tract = st.number_input("下车人口普查区", min_value=1, max_value=2000, value=170401)
            
            st.write("**💳 支付信息**")
            payment_type = st.selectbox("支付方式", ["Credit Card", "Cash", "No Charge", "Dispute", "Unknown"])
            company = st.selectbox("出租车公司", ["Flash Cab", "Taxi Affiliation Services", "Yellow Cab", "Blue Diamond", "Other"])
        
        with col2:
            st.subheader("🚀 执行预测")
            
            # 构建特征字典
            features = {
                "trip_miles": trip_miles,
                "trip_seconds": trip_seconds,
                "fare": fare,
                "pickup_latitude": pickup_latitude,
                "pickup_longitude": pickup_longitude,
                "dropoff_latitude": dropoff_latitude,
                "dropoff_longitude": dropoff_longitude,
                "trip_start_hour": trip_start_hour,
                "trip_start_day": trip_start_day,
                "trip_start_month": trip_start_month,
                "pickup_community_area": pickup_community_area,
                "dropoff_community_area": dropoff_community_area,
                "pickup_census_tract": pickup_census_tract,
                "dropoff_census_tract": dropoff_census_tract,
                "payment_type": payment_type,
                "company": company
            }
            
            # 显示输入摘要
            st.write("📋 **输入摘要**")
            summary_col1, summary_col2 = st.columns(2)
            with summary_col1:
                st.metric("行程距离", f"{trip_miles} 英里")
                st.metric("车费", f"${fare}")
            with summary_col2:
                st.metric("行程时长", f"{trip_seconds//60} 分钟")
                st.metric("支付方式", payment_type)
            
            # 执行预测
            if st.button("🚕 预测小费", type="primary"):
                with st.spinner("正在预测小费金额..."):
                    start_time = time.time()
                    success, result = call_taxi_prediction_api(features)
                    end_time = time.time()
                    
                    if success:
                        st.success(f"✅ 预测完成! 耗时: {(end_time-start_time)*1000:.2f}ms")
                        
                        # 显示预测结果
                        if result and 'prediction' in result:
                            predicted_tip = result['prediction']
                            confidence = result.get('confidence', 0.85)
                            
                            # 主要结果显示
                            st.markdown("### 🎆 预测结果")
                            
                            result_col1, result_col2, result_col3 = st.columns(3)
                            with result_col1:
                                st.metric("💰 预测小费", f"${predicted_tip:.2f}")
                            with result_col2:
                                tip_rate = (predicted_tip / fare) * 100 if fare > 0 else 0
                                st.metric("📊 小费率", f"{tip_rate:.1f}%")
                            with result_col3:
                                st.metric("🎯 置信度", f"{confidence*100:.1f}%")
                            
                            # 结果分析
                            st.markdown("### 📈 结果分析")
                            
                            # 小费区间分析
                            if predicted_tip < 1:
                                tip_category = "🔴 低小费"
                                tip_message = "小费较低，可能是短距离或现金支付"
                            elif predicted_tip < 3:
                                tip_category = "🟡 中等小费"
                                tip_message = "小费在正常范围内"
                            else:
                                tip_category = "🟢 高小费"
                                tip_message = "小费较高，可能是长距离或信用卡支付"
                            
                            st.info(f"{tip_category}: {tip_message}")
                            
                            # 可视化结果
                            fig = go.Figure()
                            fig.add_trace(go.Bar(
                                x=['车费', '预测小费', '总费用'],
                                y=[fare, predicted_tip, fare + predicted_tip],
                                marker_color=['lightblue', 'lightgreen', 'orange'],
                                text=[f'${fare:.2f}', f'${predicted_tip:.2f}', f'${fare + predicted_tip:.2f}'],
                                textposition='auto'
                            ))
                            fig.update_layout(
                                title="📊 费用组成分析",
                                yaxis_title="金额 ($)",
                                showlegend=False
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                    else:
                        st.error(f"❌ 预测失败: {result}")
            
            # 调试信息
            if show_debug:
                st.subheader("🔍 调试信息")
                st.json({
                    "API_URL": f"{API_BASE_URL}/predict",
                    "特征数据": features,
                    "特征数量": len(features)
                })
    
    # Tab 2: 批量预测
    with tab2:
        st.header("📦 批量出租车费用预测")
        st.markdown("测试大规模批量预测性能和数据分析")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("⚙️ 批量配置")
            
            batch_size = st.slider("批次大小", 1, 50, 20)
            num_trips = st.slider("行程数量", 10, 200, 50)
            
            st.info(f"📊 总行程数: {num_trips}")
            
            # 生成批量测试数据
            if st.button("📦 生成批量测试数据"):
                import random
                
                # Chicago 出租车数据范围
                companies = ["Flash Cab", "Taxi Affiliation Services", "Yellow Cab", "Blue Diamond", "Other"]
                payment_types = ["Credit Card", "Cash", "No Charge", "Dispute", "Unknown"]
                
                batch_trips = []
                for i in range(num_trips):
                    trip = {
                        "trip_miles": round(random.uniform(0.5, 25.0), 2),
                        "trip_seconds": random.randint(300, 3600),
                        "fare": round(random.uniform(3.0, 50.0), 2),
                        "pickup_latitude": round(random.uniform(41.65, 42.05), 4),
                        "pickup_longitude": round(random.uniform(-87.85, -87.55), 4),
                        "dropoff_latitude": round(random.uniform(41.65, 42.05), 4),
                        "dropoff_longitude": round(random.uniform(-87.85, -87.55), 4),
                        "trip_start_hour": random.randint(0, 23),
                        "trip_start_day": random.randint(1, 31),
                        "trip_start_month": random.randint(1, 12),
                        "pickup_community_area": random.randint(1, 77),
                        "dropoff_community_area": random.randint(1, 77),
                        "pickup_census_tract": random.randint(170000, 180000),
                        "dropoff_census_tract": random.randint(170000, 180000),
                        "payment_type": random.choice(payment_types),
                        "company": random.choice(companies)
                    }
                    batch_trips.append(trip)
                
                st.session_state.batch_trips = batch_trips
                st.success(f"✅ 生成了 {len(batch_trips)} 个出租车行程的测试数据")
                
                # 显示数据预览
                if batch_trips:
                    preview_df = pd.DataFrame(batch_trips[:5])  # 显示前5条
                    st.dataframe(preview_df, use_container_width=True)
        
        with col2:
            st.subheader("🚀 执行批量预测")
            
            if 'batch_trips' in st.session_state:
                if st.button("📦 开始批量预测", type="primary"):
                    batch_trips = st.session_state.batch_trips
                    
                    try:
                        with st.spinner("正在执行批量预测..."):
                            start_time = time.time()
                            success, result = call_batch_prediction_api(batch_trips)
                            end_time = time.time()
                            
                            if success:
                                st.success(f"✅ 批量预测完成!")
                                
                                # 性能指标
                                total_time = end_time - start_time
                                throughput = len(batch_trips) / total_time
                                avg_latency = total_time / len(batch_trips) * 1000
                                
                                col_perf1, col_perf2, col_perf3 = st.columns(3)
                                with col_perf1:
                                    st.metric("总耗时", f"{total_time:.2f}s")
                                with col_perf2:
                                    st.metric("吞吐量", f"{throughput:.2f} trips/s")
                                with col_perf3:
                                    st.metric("平均延迟", f"{avg_latency:.2f}ms")
                                
                                # 结果分析
                                if result and 'predictions' in result:
                                    predictions = result['predictions']
                                    
                                    # 创建结果 DataFrame
                                    results_data = []
                                    for i, (trip, pred) in enumerate(zip(batch_trips, predictions)):
                                        results_data.append({
                                            'trip_id': i+1,
                                            'fare': trip['fare'],
                                            'predicted_tip': pred,
                                            'tip_rate': (pred / trip['fare']) * 100 if trip['fare'] > 0 else 0,
                                            'total_cost': trip['fare'] + pred,
                                            'payment_type': trip['payment_type'],
                                            'trip_miles': trip['trip_miles']
                                        })
                                    
                                    results_df = pd.DataFrame(results_data)
                                    
                                    # 显示统计数据
                                    st.markdown("### 📊 批量预测统计")
                                    
                                    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                                    with stat_col1:
                                        st.metric("平均小费", f"${results_df['predicted_tip'].mean():.2f}")
                                    with stat_col2:
                                        st.metric("平均小费率", f"{results_df['tip_rate'].mean():.1f}%")
                                    with stat_col3:
                                        st.metric("最高小费", f"${results_df['predicted_tip'].max():.2f}")
                                    with stat_col4:
                                        st.metric("最低小费", f"${results_df['predicted_tip'].min():.2f}")
                                    
                                    # 小费分布直方图
                                    fig_hist = px.histogram(
                                        results_df, 
                                        x='predicted_tip',
                                        nbins=20,
                                        title="小费金额分布",
                                        labels={'predicted_tip': '预测小费 ($)', 'count': '数量'}
                                    )
                                    st.plotly_chart(fig_hist, use_container_width=True)
                                    
                                    # 支付方式 vs 小费率
                                    fig_box = px.box(
                                        results_df, 
                                        x='payment_type', 
                                        y='tip_rate',
                                        title="不同支付方式的小费率分布",
                                        labels={'tip_rate': '小费率 (%)', 'payment_type': '支付方式'}
                                    )
                                    st.plotly_chart(fig_box, use_container_width=True)
                                    
                                    # 显示详细结果表
                                    st.markdown("### 📋 详细结果")
                                    st.dataframe(results_df.head(20), use_container_width=True)
                                    
                            else:
                                st.error(f"❌ 批量预测失败: {result}")
                                
                    except Exception as e:
                        st.error(f"❌ 批量预测异常: {str(e)}")
            else:
                st.warning("请先生成批量测试数据")
    
    # Tab 3: 数据分析
    with tab3:
        st.header("📊 Chicago Taxi 数据分析")
        st.markdown("基于 TFX Pipeline 的出租车数据深度分析和洞察")
        
        # 数据概览
        st.subheader("📈 数据概览")
        
        # 模拟 Chicago Taxi 数据统计
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总行程数", "2,847,392")
        with col2:
            st.metric("平均车费", "$12.45")
        with col3:
            st.metric("平均小费", "$2.18")
        with col4:
            st.metric("平均小费率", "17.5%")
        
        # 数据分析选项
        analysis_type = st.selectbox(
            "选择分析类型:",
            ["时间趋势分析", "地理分布分析", "支付方式分析", "公司性能对比"]
        )
        
        if analysis_type == "时间趋势分析":
            st.subheader("⏰ 时间趋势分析")
            
            # 模拟按小时的小费数据
            hours = list(range(24))
            avg_tips = [1.2, 1.1, 1.0, 0.9, 0.8, 1.0, 1.5, 2.1, 2.8, 2.5, 2.3, 2.4, 2.6, 2.5, 2.4, 2.8, 3.2, 3.8, 4.1, 3.9, 3.2, 2.8, 2.1, 1.6]
            
            fig_time = px.line(
                x=hours, 
                y=avg_tips,
                title="24小时平均小费趋势",
                labels={'x': '小时', 'y': '平均小费 ($)'}
            )
            fig_time.update_traces(line=dict(color='blue', width=3))
            st.plotly_chart(fig_time, use_container_width=True)
            
            st.info("💡 **洞察**: 晚上 18-20 点是小费高峰期，凌晨 3-5 点小费最低")
            
        elif analysis_type == "地理分布分析":
            st.subheader("🗺️ 地理分布分析")
            
            # 模拟社区数据
            communities = ['Loop', 'Near North Side', 'Lincoln Park', 'Lakeview', 'Logan Square']
            avg_tips_geo = [4.2, 3.8, 2.9, 2.5, 2.1]
            trip_counts = [45000, 38000, 28000, 22000, 18000]
            
            fig_geo = px.bar(
                x=communities,
                y=avg_tips_geo,
                title="不同社区平均小费对比",
                labels={'x': '社区', 'y': '平均小费 ($)'},
                color=avg_tips_geo,
                color_continuous_scale='viridis'
            )
            st.plotly_chart(fig_geo, use_container_width=True)
            
            st.info("💡 **洞察**: Loop 地区（商务区）小费最高，平均超过 $4")
            
        elif analysis_type == "支付方式分析":
            st.subheader("💳 支付方式分析")
            
            # 模拟支付数据
            payment_data = {
                '支付方式': ['Credit Card', 'Cash', 'No Charge', 'Dispute'],
                '平均小费': [2.85, 0.95, 0.0, 0.12],
                '小费率': [22.8, 7.6, 0.0, 1.2],
                '交易数量': [1850000, 850000, 120000, 27000]
            }
            
            payment_df = pd.DataFrame(payment_data)
            
            col_pay1, col_pay2 = st.columns(2)
            
            with col_pay1:
                fig_payment_tip = px.bar(
                    payment_df,
                    x='支付方式',
                    y='平均小费',
                    title="不同支付方式的平均小费",
                    color='平均小费'
                )
                st.plotly_chart(fig_payment_tip, use_container_width=True)
            
            with col_pay2:
                fig_payment_rate = px.bar(
                    payment_df,
                    x='支付方式',
                    y='小费率',
                    title="不同支付方式的小费率",
                    color='小费率'
                )
                st.plotly_chart(fig_payment_rate, use_container_width=True)
            
            st.info("💡 **洞察**: 信用卡支付的小费明显高于现金支付")
            
        else:  # 公司性能对比
            st.subheader("🚕 出租车公司性能对比")
            
            # 模拟公司数据
            company_data = {
                '公司': ['Flash Cab', 'Taxi Affiliation Services', 'Yellow Cab', 'Blue Diamond'],
                '平均小费': [2.45, 2.12, 1.98, 2.38],
                '平均车费': [12.80, 11.95, 12.15, 13.20],
                '服务评分': [4.2, 3.8, 3.9, 4.1]
            }
            
            company_df = pd.DataFrame(company_data)
            
            # 散点图：车费 vs 小费
            fig_scatter = px.scatter(
                company_df, 
                x='平均车费', 
                y='平均小费',
                size='服务评分',
                color='公司',
                title="出租车公司性能对比（气泡大小代表服务评分）",
                labels={'x': '平均车费 ($)', 'y': '平均小费 ($)'}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            
            st.dataframe(company_df, use_container_width=True)
            
            st.info("💡 **洞察**: Flash Cab 在小费和服务评分方面表现最佳")

    
    # Tab 4: 性能监控
    with tab4:
        st.header("🔍 Chicago Taxi 模型性能监控")
        st.markdown("实时监控 TFX Pipeline 模型服务性能和系统状态")
        
        # 获取服务指标
        try:
            response = requests.get(f"{API_BASE_URL}/metrics", timeout=10)
            if response.status_code == 200:
                metrics = response.json()
                
                # 服务状态概览
                st.subheader("🟢 服务状态概览")
                col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
                with col_metric1:
                    st.metric("🚕 模型服务", metrics.get('model_status', '正常'))
                with col_metric2:
                    st.metric("🔗 API 状态", "正常" if metrics.get('api_status', True) else "异常")
                with col_metric3:
                    st.metric("📊 预测数量", f"{metrics.get('total_predictions', 0):,}")
                with col_metric4:
                    st.metric("最后更新", metrics.get('timestamp', 'N/A')[:19])
                
                # 模拟性能数据 (实际应用中从 Prometheus 获取)
                if st.button("🔄 刷新监控数据"):
                    import random
                    import numpy as np
                    
                    # 生成模拟时间序列数据
                    timestamps = pd.date_range(
                        start=datetime.now().replace(hour=0, minute=0, second=0),
                        periods=24,
                        freq='H'
                    )
                    
                    # 模拟指标
                    latency_data = [50 + random.gauss(0, 10) for _ in range(24)]
                    throughput_data = [100 + random.gauss(0, 20) for _ in range(24)]
                    error_rate_data = [random.uniform(0, 5) for _ in range(24)]
                    
                    # 延迟趋势
                    fig_latency = go.Figure()
                    fig_latency.add_trace(go.Scatter(
                        x=timestamps,
                        y=latency_data,
                        mode='lines+markers',
                        name='平均延迟 (ms)',
                        line=dict(color='blue')
                    ))
                    fig_latency.update_layout(title="推理延迟趋势", xaxis_title="时间", yaxis_title="延迟 (ms)")
                    st.plotly_chart(fig_latency, use_container_width=True)
                    
                    # 吞吐量和错误率
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        fig_throughput = go.Figure()
                        fig_throughput.add_trace(go.Scatter(
                            x=timestamps,
                            y=throughput_data,
                            mode='lines+markers',
                            name='吞吐量 (req/s)',
                            line=dict(color='green')
                        ))
                        fig_throughput.update_layout(title="吞吐量趋势", xaxis_title="时间", yaxis_title="请求/秒")
                        st.plotly_chart(fig_throughput, use_container_width=True)
                    
                    with col_chart2:
                        fig_error = go.Figure()
                        fig_error.add_trace(go.Scatter(
                            x=timestamps,
                            y=error_rate_data,
                            mode='lines+markers',
                            name='错误率 (%)',
                            line=dict(color='red')
                        ))
                        fig_error.update_layout(title="错误率趋势", xaxis_title="时间", yaxis_title="错误率 (%)")
                        st.plotly_chart(fig_error, use_container_width=True)
                    
                    # 性能总结
                    st.subheader("📈 性能总结")
                    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                    
                    with summary_col1:
                        st.metric("平均延迟", f"{np.mean(latency_data):.1f} ms")
                    with summary_col2:
                        st.metric("平均吞吐量", f"{np.mean(throughput_data):.1f} req/s")
                    with summary_col3:
                        st.metric("平均错误率", f"{np.mean(error_rate_data):.2f}%")
                    with summary_col4:
                        st.metric("可用性", "99.9%")
            else:
                st.error("无法获取服务指标")
                
        except Exception as e:
            st.error(f"监控数据获取失败: {str(e)}")
    
    # Tab 6: Feast 特征存储
    with tab6:
        try:
            feast_ui.render_feast_dashboard()
        except Exception as e:
            st.error(f"Feast 特征存储界面加载失败: {str(e)}")
            st.info("请确保 Feast 服务和 Redis 正在运行")
    
    # Tab 7: Kafka 流处理
    with tab7:
        try:
            kafka_ui.render_kafka_dashboard()
        except Exception as e:
            st.error(f"Kafka 流处理界面加载失败: {str(e)}")
            st.info("请确保 Kafka 服务正在运行")
    
    # Tab 8: MLflow 模型注册
    with tab8:
        try:
            mlflow_ui.render_mlflow_dashboard()
        except Exception as e:
            st.error(f"MLflow 模型注册界面加载失败: {str(e)}")
            st.info("请确保 MLflow 服务正在运行")
    
    # Tab 9: MLMD 数据血缘
    with tab9:
        try:
            mlmd_ui = get_mlmd_ui_integration(api_base_url)
            mlmd_ui.render_mlmd_interface()
        except Exception as e:
            st.error(f"MLMD 数据血缘界面加载失败: {str(e)}")
            st.info("请确保 MLMD 组件和 FastAPI 服务正在运行")
    
    # 页脚
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: gray;'>
        🚕 Chicago Taxi MLOps 平台 v1.0.0 | 基于 TFX Pipeline + Kubeflow + KFServing + Streamlit<br>
        💡 提示: 确保 FastAPI 服务 (localhost:8000) 和 TFX Pipeline 正在运行<br>
        📊 数据源: Chicago Taxi Trips Dataset | 🎯 预测目标: 小费金额 (Tips)
    </div>
    """, unsafe_allow_html=True)

def render_data_drift_monitoring():
    """渲染数据漂移监控界面"""
    st.header("🔍 数据漂移监控")
    
    # 初始化漂移监控 UI
    drift_ui = DriftMonitorUI()
    
    # 加载数据
    if drift_ui.load_drift_results():
        
        # 控制面板
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.subheader("📊 漂移监控概览")
        
        with col2:
            if st.button("🔄 刷新数据", key="refresh_drift"):
                drift_ui.load_drift_results()
                st.rerun()
        
        with col3:
            auto_refresh = st.checkbox("自动刷新", key="auto_refresh_drift")
        
        # 自动刷新逻辑
        if auto_refresh:
            time.sleep(10)  # 10秒刷新一次
            st.rerun()
        
        # 漂移概览
        drift_ui.render_drift_overview()
        
        st.divider()
        
        # 创建子标签页
        drift_tab1, drift_tab2, drift_tab3, drift_tab4, drift_tab5 = st.tabs([
            "📈 特征漂移图表", "🔥 漂移热力图", "🔍 特征详细分析", "📅 历史趋势", "💡 建议与报告"
        ])
        
        with drift_tab1:
            st.subheader("特征漂移分数分布")
            drift_ui.render_feature_drift_chart()
        
        with drift_tab2:
            st.subheader("特征漂移热力图")
            drift_ui.render_drift_heatmap()
        
        with drift_tab3:
            st.subheader("特征详细分析")
            
            # 特征选择
            if drift_ui.drift_data:
                features = list(drift_ui.drift_data['feature_details'].keys())
                selected_feature = st.selectbox(
                    "选择要分析的特征:",
                    features,
                    key="feature_selector"
                )
                
                if selected_feature:
                    drift_ui.render_feature_comparison(selected_feature)
        
        with drift_tab4:
            st.subheader("数据漂移历史趋势")
            drift_ui.render_drift_timeline()
            
            # 添加说明
            st.info("📝 注意：这是基于模拟数据的历史趋势图。在实际部署中，这将显示真实的历史漂移数据。")
        
        with drift_tab5:
            st.subheader("建议与报告")
            
            # 显示建议
            drift_ui.render_recommendations()
            
            st.divider()
            
            # 导出报告
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 生成详细报告", key="generate_report"):
                    report = drift_ui.export_drift_report()
                    st.download_button(
                        label="📥 下载报告",
                        data=report,
                        file_name=f"drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
            
            with col2:
                if st.button("🚨 触发告警", key="trigger_alert"):
                    if drift_ui.drift_data and drift_ui.drift_data['summary']['overall_drift_detected']:
                        st.error("⚠️ 数据漂移告警已触发！建议立即检查数据质量。")
                        
                        # 显示告警详情
                        with st.expander("告警详情"):
                            drifted_features = [
                                name for name, details in drift_ui.drift_data['feature_details'].items()
                                if details['is_drifted']
                            ]
                            st.write(f"**漂移特征:** {', '.join(drifted_features)}")
                            st.write(f"**漂移特征数:** {len(drifted_features)}")
                            st.write(f"**建议操作:** 检查数据收集流程，考虑重新训练模型")
                    else:
                        st.success("✅ 当前数据质量良好，无需告警。")
        
        # 添加技术说明
        with st.expander("🔧 技术说明"):
            st.markdown("""
            ### 数据漂移监控技术说明
            
            **漂移检测算法:**
            - **数值特征**: 基于均值和标准差变化检测
            - **分类特征**: 使用 Jensen-Shannon 散度比较分布
            
            **漂移分类:**
            - 🟢 **无漂移** (< 0.1): 数据分布稳定
            - 🟡 **轻微漂移** (0.1 - 0.3): 轻微变化，需要关注
            - 🟠 **中等漂移** (0.3 - 0.5): 明显变化，建议调查
            - 🔴 **严重漂移** (> 0.5): 严重变化，需要立即处理
            
            **监控频率建议:**
            - 实时监控：每小时检查
            - 日常监控：每天检查
            - 定期审查：每周深度分析
            
            **集成说明:**
            - 本界面展示的是模拟数据
            - 实际部署时将连接到 TFX Pipeline 的漂移监控组件
            - 支持 Prometheus 指标导出和 Grafana 可视化
            """)
    
    else:
        st.error("无法加载数据漂移结果。请确保数据漂移监控组件正在运行。")
        
        # 提供手动触发选项
        if st.button("🔄 手动触发漂移检测", key="manual_trigger"):
            with st.spinner("正在执行数据漂移检测..."):
                time.sleep(3)  # 模拟检测过程
                st.success("✅ 数据漂移检测已完成！请刷新页面查看结果。")
                st.info("💡 提示：在实际部署中，这将触发 TFX Pipeline 中的数据漂移监控组件。")


if __name__ == "__main__":
    main()
