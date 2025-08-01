#!/usr/bin/env python3
"""
Streamlit UI 与 Kafka 流处理集成
实时显示 Chicago Taxi 流处理结果
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import threading
import time
from datetime import datetime, timedelta
from collections import deque
import asyncio
from typing import Dict, List, Any

# 导入流处理器
from kafka_stream_processor import KafkaStreamProcessor, TaxiPrediction, ModelMetric


class StreamlitKafkaIntegration:
    """Streamlit 与 Kafka 流处理集成类"""
    
    def __init__(self):
        """初始化集成组件"""
        self.processor = KafkaStreamProcessor()
        
        # 数据缓存（使用 deque 保持最近的数据）
        self.predictions_buffer = deque(maxlen=100)
        self.metrics_buffer = deque(maxlen=50)
        self.ride_stats = {
            'total_rides': 0,
            'total_revenue': 0.0,
            'avg_fare': 0.0,
            'avg_tip': 0.0
        }
        
        # 启动后台数据消费线程
        self._start_background_consumers()
    
    def _start_background_consumers(self):
        """启动后台数据消费线程"""
        
        def consume_predictions():
            """消费预测结果"""
            def prediction_callback(prediction: TaxiPrediction):
                self.predictions_buffer.append({
                    'trip_id': prediction.trip_id,
                    'timestamp': prediction.timestamp,
                    'predicted_fare': prediction.predicted_fare,
                    'predicted_tip': prediction.predicted_tip,
                    'confidence': prediction.confidence_score,
                    'model_version': prediction.model_version
                })
                
                # 更新统计信息
                self.ride_stats['total_rides'] += 1
                self.ride_stats['total_revenue'] += prediction.predicted_fare
                self.ride_stats['avg_fare'] = self.ride_stats['total_revenue'] / self.ride_stats['total_rides']
                
                # 计算平均小费
                tips = [p['predicted_tip'] for p in list(self.predictions_buffer)]
                self.ride_stats['avg_tip'] = sum(tips) / len(tips) if tips else 0.0
            
            self.processor.consume_predictions_for_ui(prediction_callback)
        
        def consume_metrics():
            """消费指标数据"""
            consumer = self.processor._get_consumer(
                self.processor.topics['metrics'], 
                'streamlit-metrics-group'
            )
            
            for message in consumer:
                try:
                    metric_data = message.value
                    self.metrics_buffer.append(metric_data)
                except Exception as e:
                    st.error(f"消费指标数据失败: {e}")
        
        # 启动后台线程
        prediction_thread = threading.Thread(target=consume_predictions)
        prediction_thread.daemon = True
        prediction_thread.start()
        
        metrics_thread = threading.Thread(target=consume_metrics)
        metrics_thread.daemon = True
        metrics_thread.start()
    
    def render_real_time_dashboard(self):
        """渲染实时仪表板"""
        st.header("🌊 实时数据流监控")
        
        # 控制面板
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.subheader("📊 实时流处理状态")
        
        with col2:
            if st.button("🔄 刷新数据", key="refresh_stream"):
                st.rerun()
        
        with col3:
            auto_refresh = st.checkbox("自动刷新 (5秒)", key="auto_refresh_stream")
        
        # 自动刷新逻辑
        if auto_refresh:
            time.sleep(5)
            st.rerun()
        
        # 实时统计概览
        self._render_real_time_stats()
        
        st.divider()
        
        # 创建标签页
        stream_tab1, stream_tab2, stream_tab3, stream_tab4 = st.tabs([
            "🚕 实时预测", "📈 流处理指标", "🔄 数据流状态", "⚡ 性能监控"
        ])
        
        with stream_tab1:
            self._render_real_time_predictions()
        
        with stream_tab2:
            self._render_stream_metrics()
        
        with stream_tab3:
            self._render_data_flow_status()
        
        with stream_tab4:
            self._render_performance_monitoring()
    
    def _render_real_time_stats(self):
        """渲染实时统计概览"""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "总行程数",
                f"{self.ride_stats['total_rides']:,}",
                delta=f"+{len(self.predictions_buffer)}" if self.predictions_buffer else None
            )
        
        with col2:
            st.metric(
                "总收入",
                f"${self.ride_stats['total_revenue']:.2f}",
                delta=f"+${self.predictions_buffer[-1]['predicted_fare']:.2f}" if self.predictions_buffer else None
            )
        
        with col3:
            st.metric(
                "平均车费",
                f"${self.ride_stats['avg_fare']:.2f}"
            )
        
        with col4:
            st.metric(
                "平均小费",
                f"${self.ride_stats['avg_tip']:.2f}"
            )
    
    def _render_real_time_predictions(self):
        """渲染实时预测结果"""
        st.subheader("🚕 实时预测结果")
        
        if not self.predictions_buffer:
            st.info("等待实时预测数据...")
            
            # 提供模拟数据按钮
            if st.button("🎲 生成模拟数据", key="generate_mock_stream"):
                with st.spinner("生成模拟流数据..."):
                    self.processor.simulate_taxi_rides(5)
                    time.sleep(2)
                    st.success("模拟数据已发送到 Kafka 流！")
            return
        
        # 最近预测表格
        recent_predictions = list(self.predictions_buffer)[-10:]  # 最近10条
        df_predictions = pd.DataFrame(recent_predictions)
        
        st.dataframe(
            df_predictions[['trip_id', 'predicted_fare', 'predicted_tip', 'confidence']],
            use_container_width=True
        )
        
        # 实时预测趋势图
        if len(recent_predictions) > 1:
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('实时车费预测', '实时小费预测'),
                vertical_spacing=0.1
            )
            
            timestamps = [datetime.fromisoformat(p['timestamp'].replace('Z', '+00:00')) for p in recent_predictions]
            
            # 车费趋势
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=[p['predicted_fare'] for p in recent_predictions],
                    mode='lines+markers',
                    name='预测车费',
                    line=dict(color='blue')
                ),
                row=1, col=1
            )
            
            # 小费趋势
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=[p['predicted_tip'] for p in recent_predictions],
                    mode='lines+markers',
                    name='预测小费',
                    line=dict(color='green')
                ),
                row=2, col=1
            )
            
            fig.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_stream_metrics(self):
        """渲染流处理指标"""
        st.subheader("📈 流处理指标")
        
        if not self.metrics_buffer:
            st.info("等待流处理指标数据...")
            return
        
        # 指标数据处理
        metrics_data = list(self.metrics_buffer)
        df_metrics = pd.DataFrame(metrics_data)
        
        if df_metrics.empty:
            st.warning("暂无指标数据")
            return
        
        # 按指标类型分组显示
        metric_types = df_metrics['metric_name'].unique()
        
        for metric_type in metric_types:
            metric_data = df_metrics[df_metrics['metric_name'] == metric_type]
            
            if len(metric_data) > 1:
                fig = px.line(
                    metric_data,
                    x='timestamp',
                    y='metric_value',
                    title=f'{metric_type} 趋势',
                    markers=True
                )
                
                # 添加阈值线
                if 'threshold' in metric_data.columns:
                    threshold = metric_data['threshold'].iloc[0]
                    fig.add_hline(
                        y=threshold,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"阈值: {threshold}"
                    )
                
                st.plotly_chart(fig, use_container_width=True)
    
    def _render_data_flow_status(self):
        """渲染数据流状态"""
        st.subheader("🔄 数据流状态")
        
        # Kafka Topics 状态
        topics_status = {
            "taxi-rides-raw": "🟢 活跃",
            "taxi-features-realtime": "🟢 活跃",
            "taxi-predictions": "🟢 活跃",
            "model-metrics": "🟡 中等",
            "data-quality-alerts": "🟢 活跃"
        }
        
        st.subheader("📋 Kafka Topics 状态")
        for topic, status in topics_status.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{topic}**")
            with col2:
                st.write(status)
        
        # 流处理器状态
        st.subheader("⚙️ 流处理器状态")
        processors_status = {
            "特征工程处理器": "🟢 运行中",
            "模型推理处理器": "🟢 运行中",
            "指标计算处理器": "🟢 运行中",
            "异常检测处理器": "🟡 待启动"
        }
        
        for processor, status in processors_status.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{processor}**")
            with col2:
                st.write(status)
    
    def _render_performance_monitoring(self):
        """渲染性能监控"""
        st.subheader("⚡ 性能监控")
        
        # 模拟性能数据
        performance_data = {
            "消息处理延迟": "23ms",
            "吞吐量": "1,250 msg/sec",
            "错误率": "0.02%",
            "内存使用": "245MB",
            "CPU 使用": "15%"
        }
        
        col1, col2 = st.columns(2)
        
        with col1:
            for metric, value in list(performance_data.items())[:3]:
                st.metric(metric, value)
        
        with col2:
            for metric, value in list(performance_data.items())[3:]:
                st.metric(metric, value)
        
        # 性能趋势图（模拟数据）
        if self.predictions_buffer:
            timestamps = [datetime.now() - timedelta(minutes=i) for i in range(10, 0, -1)]
            latencies = [20 + i * 2 + (i % 3) * 5 for i in range(10)]
            throughputs = [1200 + i * 50 + (i % 2) * 100 for i in range(10)]
            
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('处理延迟 (ms)', '吞吐量 (msg/sec)'),
                vertical_spacing=0.1
            )
            
            fig.add_trace(
                go.Scatter(x=timestamps, y=latencies, mode='lines+markers', name='延迟'),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=timestamps, y=throughputs, mode='lines+markers', name='吞吐量'),
                row=2, col=1
            )
            
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    def render_stream_control_panel(self):
        """渲染流控制面板"""
        st.sidebar.header("🎛️ 流处理控制")
        
        # 启动/停止控制
        if st.sidebar.button("🚀 启动所有处理器"):
            with st.spinner("启动流处理器..."):
                self.processor.start_all_processors()
                st.sidebar.success("流处理器已启动！")
        
        if st.sidebar.button("⏹️ 停止所有处理器"):
            with st.spinner("停止流处理器..."):
                self.processor.close()
                st.sidebar.success("流处理器已停止！")
        
        st.sidebar.divider()
        
        # 数据生成控制
        st.sidebar.subheader("📊 数据生成")
        
        num_rides = st.sidebar.slider("生成行程数量", 1, 50, 10)
        
        if st.sidebar.button("🎲 生成模拟数据"):
            with st.spinner(f"生成 {num_rides} 个模拟行程..."):
                self.processor.simulate_taxi_rides(num_rides)
                st.sidebar.success(f"已生成 {num_rides} 个模拟行程！")
        
        st.sidebar.divider()
        
        # 配置选项
        st.sidebar.subheader("⚙️ 配置")
        
        kafka_server = st.sidebar.text_input(
            "Kafka 服务器",
            value="localhost:9092"
        )
        
        api_endpoint = st.sidebar.text_input(
            "API 端点",
            value="http://localhost:8000"
        )
        
        if st.sidebar.button("🔄 重新连接"):
            self.processor = KafkaStreamProcessor(kafka_server)
            st.sidebar.success("已重新连接到 Kafka！")


def main():
    """主函数"""
    st.set_page_config(
        page_title="Chicago Taxi 实时流处理",
        page_icon="🌊",
        layout="wide"
    )
    
    # 初始化集成组件
    if 'kafka_integration' not in st.session_state:
        st.session_state.kafka_integration = StreamlitKafkaIntegration()
    
    integration = st.session_state.kafka_integration
    
    # 渲染控制面板
    integration.render_stream_control_panel()
    
    # 渲染主仪表板
    integration.render_real_time_dashboard()
    
    # 添加说明
    with st.expander("ℹ️ 使用说明"):
        st.markdown("""
        ### 🌊 实时流处理功能说明
        
        **数据流程：**
        1. 📡 **数据采集**: 模拟出租车行程数据发送到 Kafka
        2. 🔧 **特征工程**: 实时计算行程特征（距离、时间、区域等）
        3. 🤖 **模型推理**: 调用 FastAPI 服务进行费用和小费预测
        4. 📊 **指标计算**: 计算模型性能和业务指标
        5. 📈 **实时展示**: 在 Streamlit UI 中实时显示结果
        
        **操作步骤：**
        1. 点击侧边栏"🚀 启动所有处理器"启动流处理
        2. 点击"🎲 生成模拟数据"发送测试数据
        3. 观察各个标签页中的实时数据更新
        4. 启用"自动刷新"获得最佳体验
        
        **注意事项：**
        - 确保 Kafka 服务器在 localhost:9092 运行
        - 确保 FastAPI 服务在 localhost:8000 运行
        - 首次启动可能需要几秒钟初始化时间
        """)


if __name__ == "__main__":
    main()
