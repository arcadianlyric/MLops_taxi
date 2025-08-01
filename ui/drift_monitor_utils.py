#!/usr/bin/env python3
"""
数据漂移监控 UI 辅助工具
用于在 Streamlit 中可视化数据漂移监控结果
"""

import os
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import streamlit as st


class DriftMonitorUI:
    """数据漂移监控 UI 类"""
    
    def __init__(self, drift_results_path: str = None):
        """
        初始化数据漂移监控 UI
        
        Args:
            drift_results_path: 漂移结果文件路径
        """
        self.drift_results_path = drift_results_path
        self.drift_data = None
        
        # 默认结果路径
        if not self.drift_results_path:
            # 尝试从 UI 结果目录加载
            ui_results_dir = os.path.join(os.path.dirname(__file__), 'drift_results')
            config_path = os.path.join(ui_results_dir, 'config.json')
            
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    self.drift_results_path = config.get('drift_report_path')
                except Exception:
                    pass
        
    def load_drift_results(self, results_path: str = None) -> bool:
        """
        加载数据漂移结果
        
        Args:
            results_path: 结果文件路径
            
        Returns:
            是否成功加载
        """
        path = results_path or self.drift_results_path
        
        # 首先尝试加载真实数据
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.drift_data = json.load(f)
                st.success(f"✅ 已加载真实漂移监控数据: {os.path.basename(path)}")
                return True
            except Exception as e:
                st.warning(f"加载真实数据失败: {e}，将使用模拟数据")
        
        # 如果没有真实数据，生成模拟数据
        self.drift_data = self._generate_mock_drift_data()
        st.info("📊 当前显示模拟数据。运行数据漂移监控 Pipeline 以获取真实结果。")
        return True
    
    def _generate_mock_drift_data(self) -> Dict[str, Any]:
        """生成模拟数据漂移结果"""
        
        # 模拟特征漂移数据
        features = [
            'trip_miles', 'fare', 'trip_seconds', 'pickup_latitude',
            'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude',
            'payment_type', 'company', 'trip_start_hour'
        ]
        
        feature_details = {}
        overall_drift = False
        
        for feature in features:
            # 随机生成漂移分数
            drift_score = np.random.uniform(0.0, 0.8)
            is_drifted = drift_score > 0.1
            
            if is_drifted:
                overall_drift = True
            
            # 分类漂移类型
            if drift_score < 0.1:
                drift_type = "无漂移"
            elif drift_score < 0.3:
                drift_type = "轻微漂移"
            elif drift_score < 0.5:
                drift_type = "中等漂移"
            else:
                drift_type = "严重漂移"
            
            feature_details[feature] = {
                'drift_score': round(drift_score, 3),
                'is_drifted': is_drifted,
                'drift_type': drift_type,
                'baseline_stats': self._generate_mock_stats(feature, 'baseline'),
                'current_stats': self._generate_mock_stats(feature, 'current')
            }
        
        return {
            'summary': {
                'timestamp': datetime.now().isoformat(),
                'overall_drift_detected': overall_drift,
                'threshold': 0.1,
                'total_features_checked': len(features),
                'drifted_features_count': sum(1 for f in feature_details.values() if f['is_drifted'])
            },
            'feature_details': feature_details,
            'recommendations': self._generate_mock_recommendations(overall_drift)
        }
    
    def _generate_mock_stats(self, feature: str, data_type: str) -> Dict[str, Any]:
        """生成模拟特征统计信息"""
        
        if feature in ['trip_miles', 'fare', 'trip_seconds', 'pickup_latitude', 
                      'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude']:
            # 数值特征
            base_mean = {'trip_miles': 5.2, 'fare': 12.5, 'trip_seconds': 900,
                        'pickup_latitude': 41.88, 'pickup_longitude': -87.63,
                        'dropoff_latitude': 41.89, 'dropoff_longitude': -87.62}
            
            mean_val = base_mean.get(feature, 10.0)
            if data_type == 'current':
                mean_val *= np.random.uniform(0.8, 1.2)  # 添加一些变化
            
            return {
                'name': feature,
                'type': 'FLOAT',
                'mean': round(mean_val, 2),
                'std_dev': round(mean_val * 0.3, 2),
                'min': round(mean_val * 0.1, 2),
                'max': round(mean_val * 3, 2),
                'median': round(mean_val * 0.95, 2)
            }
        else:
            # 分类特征
            if feature == 'payment_type':
                values = ['Credit Card', 'Cash', 'No Charge', 'Dispute']
                frequencies = [0.65, 0.30, 0.03, 0.02]
            elif feature == 'company':
                values = ['Flash Cab', 'Taxi Affiliation Services', 'Yellow Cab', 'Blue Diamond']
                frequencies = [0.35, 0.25, 0.25, 0.15]
            else:
                values = [f'{feature}_val_{i}' for i in range(4)]
                frequencies = np.random.dirichlet([1, 1, 1, 1])
            
            if data_type == 'current':
                # 添加一些分布变化
                frequencies = np.array(frequencies) * np.random.uniform(0.7, 1.3, len(frequencies))
                frequencies = frequencies / frequencies.sum()
            
            return {
                'name': feature,
                'type': 'BYTES',
                'unique_count': len(values),
                'top_values': [
                    {'value': val, 'frequency': round(freq, 3)}
                    for val, freq in zip(values, frequencies)
                ]
            }
    
    def _generate_mock_recommendations(self, overall_drift: bool) -> List[str]:
        """生成模拟建议"""
        if overall_drift:
            return [
                "检测到数据漂移，建议进行以下操作：",
                "1. 检查数据收集流程是否有变化",
                "2. 考虑重新训练模型",
                "3. 更新数据预处理逻辑",
                "4. 特别关注严重漂移特征"
            ]
        else:
            return ["未检测到显著数据漂移，模型可以继续使用"]
    
    def render_drift_overview(self):
        """渲染漂移概览"""
        if not self.drift_data:
            st.error("未找到漂移数据，请先加载数据")
            return
        
        summary = self.drift_data['summary']
        
        # 概览指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            drift_status = "🔴 检测到漂移" if summary['overall_drift_detected'] else "🟢 无漂移"
            st.metric("漂移状态", drift_status)
        
        with col2:
            st.metric("漂移特征数", f"{summary['drifted_features_count']}/{summary['total_features_checked']}")
        
        with col3:
            drift_rate = (summary['drifted_features_count'] / summary['total_features_checked']) * 100
            st.metric("漂移率", f"{drift_rate:.1f}%")
        
        with col4:
            st.metric("检测阈值", f"{summary['threshold']}")
        
        # 时间信息
        timestamp = datetime.fromisoformat(summary['timestamp'].replace('Z', '+00:00'))
        st.info(f"📅 最后检测时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def render_feature_drift_chart(self):
        """渲染特征漂移图表"""
        if not self.drift_data:
            return
        
        features = list(self.drift_data['feature_details'].keys())
        drift_scores = [self.drift_data['feature_details'][f]['drift_score'] for f in features]
        drift_types = [self.drift_data['feature_details'][f]['drift_type'] for f in features]
        
        # 创建颜色映射
        color_map = {
            "无漂移": "#2E8B57",      # 绿色
            "轻微漂移": "#FFD700",    # 黄色
            "中等漂移": "#FF8C00",    # 橙色
            "严重漂移": "#DC143C"     # 红色
        }
        
        colors = [color_map.get(dt, "#808080") for dt in drift_types]
        
        # 创建条形图
        fig = go.Figure(data=[
            go.Bar(
                x=features,
                y=drift_scores,
                marker_color=colors,
                text=[f"{score:.3f}<br>{dtype}" for score, dtype in zip(drift_scores, drift_types)],
                textposition='auto',
                hovertemplate="<b>%{x}</b><br>漂移分数: %{y:.3f}<br>类型: %{text}<extra></extra>"
            )
        ])
        
        # 添加阈值线
        fig.add_hline(y=0.1, line_dash="dash", line_color="red", 
                     annotation_text="漂移阈值 (0.1)")
        
        fig.update_layout(
            title="特征漂移分数分布",
            xaxis_title="特征",
            yaxis_title="漂移分数",
            showlegend=False,
            height=500
        )
        
        fig.update_xaxis(tickangle=45)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_drift_heatmap(self):
        """渲染漂移热力图"""
        if not self.drift_data:
            return
        
        features = list(self.drift_data['feature_details'].keys())
        drift_scores = [self.drift_data['feature_details'][f]['drift_score'] for f in features]
        
        # 创建热力图数据
        heatmap_data = np.array(drift_scores).reshape(1, -1)
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=features,
            y=['漂移分数'],
            colorscale='RdYlGn_r',
            zmin=0,
            zmax=1,
            colorbar=dict(title="漂移分数"),
            hovertemplate="特征: %{x}<br>漂移分数: %{z:.3f}<extra></extra>"
        ))
        
        fig.update_layout(
            title="特征漂移热力图",
            height=200
        )
        
        fig.update_xaxis(tickangle=45)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_feature_comparison(self, selected_feature: str):
        """渲染特征对比分析"""
        if not self.drift_data or selected_feature not in self.drift_data['feature_details']:
            return
        
        feature_data = self.drift_data['feature_details'][selected_feature]
        baseline_stats = feature_data['baseline_stats']
        current_stats = feature_data['current_stats']
        
        st.subheader(f"特征分析: {selected_feature}")
        
        # 基本信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("漂移分数", f"{feature_data['drift_score']:.3f}")
        with col2:
            st.metric("漂移类型", feature_data['drift_type'])
        with col3:
            status = "是" if feature_data['is_drifted'] else "否"
            st.metric("是否漂移", status)
        
        # 统计对比
        if baseline_stats.get('type') == 'FLOAT':
            # 数值特征对比
            self._render_numerical_comparison(baseline_stats, current_stats)
        else:
            # 分类特征对比
            self._render_categorical_comparison(baseline_stats, current_stats)
    
    def _render_numerical_comparison(self, baseline_stats: Dict, current_stats: Dict):
        """渲染数值特征对比"""
        
        # 统计指标对比
        metrics = ['mean', 'std_dev', 'min', 'max', 'median']
        baseline_values = [baseline_stats.get(m, 0) for m in metrics]
        current_values = [current_stats.get(m, 0) for m in metrics]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='基线数据',
            x=metrics,
            y=baseline_values,
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            name='当前数据',
            x=metrics,
            y=current_values,
            marker_color='lightcoral'
        ))
        
        fig.update_layout(
            title="数值特征统计对比",
            xaxis_title="统计指标",
            yaxis_title="数值",
            barmode='group'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_categorical_comparison(self, baseline_stats: Dict, current_stats: Dict):
        """渲染分类特征对比"""
        
        # 获取频率分布
        baseline_values = baseline_stats.get('top_values', [])
        current_values = current_stats.get('top_values', [])
        
        # 创建对比数据
        categories = list(set([v['value'] for v in baseline_values] + [v['value'] for v in current_values]))
        
        baseline_freq = {v['value']: v['frequency'] for v in baseline_values}
        current_freq = {v['value']: v['frequency'] for v in current_values}
        
        baseline_freqs = [baseline_freq.get(cat, 0) for cat in categories]
        current_freqs = [current_freq.get(cat, 0) for cat in categories]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='基线数据',
            x=categories,
            y=baseline_freqs,
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            name='当前数据',
            x=categories,
            y=current_freqs,
            marker_color='lightcoral'
        ))
        
        fig.update_layout(
            title="分类特征频率对比",
            xaxis_title="类别",
            yaxis_title="频率",
            barmode='group'
        )
        
        fig.update_xaxis(tickangle=45)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_recommendations(self):
        """渲染建议"""
        if not self.drift_data:
            return
        
        recommendations = self.drift_data.get('recommendations', [])
        
        st.subheader("💡 建议")
        
        for i, rec in enumerate(recommendations, 1):
            if rec.startswith("检测到数据漂移") or rec.startswith("未检测到"):
                st.info(rec)
            else:
                st.write(f"{rec}")
    
    def render_drift_timeline(self):
        """渲染漂移时间线（模拟历史数据）"""
        
        # 生成模拟历史数据
        dates = pd.date_range(start=datetime.now() - timedelta(days=30), 
                             end=datetime.now(), freq='D')
        
        overall_drift = [np.random.choice([0, 1], p=[0.7, 0.3]) for _ in dates]
        avg_drift_score = [np.random.uniform(0.05, 0.4) for _ in dates]
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('整体漂移状态', '平均漂移分数'),
            vertical_spacing=0.1
        )
        
        # 漂移状态时间线
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=overall_drift,
                mode='lines+markers',
                name='漂移状态',
                line=dict(color='red'),
                yaxis='y1'
            ),
            row=1, col=1
        )
        
        # 平均漂移分数时间线
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=avg_drift_score,
                mode='lines+markers',
                name='平均漂移分数',
                line=dict(color='blue'),
                yaxis='y2'
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            title="数据漂移历史趋势",
            height=500,
            showlegend=False
        )
        
        fig.update_yaxes(title_text="漂移状态", row=1, col=1)
        fig.update_yaxes(title_text="漂移分数", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def export_drift_report(self) -> str:
        """导出漂移报告"""
        if not self.drift_data:
            return ""
        
        # 生成报告内容
        summary = self.drift_data['summary']
        
        report = f"""
# 数据漂移监控报告

## 概览
- 检测时间: {summary['timestamp']}
- 整体漂移状态: {'检测到漂移' if summary['overall_drift_detected'] else '无漂移'}
- 漂移特征数: {summary['drifted_features_count']}/{summary['total_features_checked']}
- 检测阈值: {summary['threshold']}

## 特征详情
"""
        
        for feature, details in self.drift_data['feature_details'].items():
            report += f"""
### {feature}
- 漂移分数: {details['drift_score']:.3f}
- 漂移类型: {details['drift_type']}
- 是否漂移: {'是' if details['is_drifted'] else '否'}
"""
        
        report += f"""
## 建议
{chr(10).join(self.drift_data['recommendations'])}
"""
        
        return report
