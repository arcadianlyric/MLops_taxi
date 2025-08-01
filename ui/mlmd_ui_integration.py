#!/usr/bin/env python3
"""
MLMD (ML Metadata) Streamlit UI 集成
提供数据血缘追踪和元数据管理的可视化界面
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MLMDUIIntegration:
    """MLMD UI 集成类"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.mlmd_api_url = f"{api_base_url}/mlmd"
    
    def render_mlmd_interface(self):
        """渲染 MLMD 主界面"""
        st.header("🔗 MLMD 数据血缘追踪")
        st.markdown("**ML Metadata (MLMD) 数据血缘关系和元数据管理**")
        
        # 创建标签页
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 服务概览", 
            "🌐 血缘关系图", 
            "📦 Artifacts", 
            "⚙️ Executions",
            "📈 血缘分析",
            "🧪 演示和测试"
        ])
        
        with tab1:
            self._render_service_overview()
        
        with tab2:
            self._render_lineage_graph()
        
        with tab3:
            self._render_artifacts_management()
        
        with tab4:
            self._render_executions_management()
        
        with tab5:
            self._render_lineage_analysis()
        
        with tab6:
            self._render_demo_and_testing()
    
    def _render_service_overview(self):
        """渲染服务概览"""
        st.subheader("📊 MLMD 服务状态")
        
        try:
            # 获取 MLMD 服务信息
            response = requests.get(f"{self.mlmd_api_url}/info", timeout=10)
            
            if response.status_code == 200:
                mlmd_info = response.json()
                
                # 显示服务状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    status_color = "🟢" if mlmd_info["available"] else "🔴"
                    st.metric(
                        "服务状态",
                        f"{status_color} {'可用' if mlmd_info['available'] else '不可用'}",
                        delta=f"模式: {mlmd_info['mode']}"
                    )
                
                with col2:
                    st.metric(
                        "Artifacts 总数",
                        mlmd_info["total_artifacts"],
                        delta="数据和模型制品"
                    )
                
                with col3:
                    st.metric(
                        "Executions 总数",
                        mlmd_info["total_executions"],
                        delta="执行过程"
                    )
                
                with col4:
                    st.metric(
                        "Events 总数",
                        mlmd_info["total_events"],
                        delta="血缘关系"
                    )
                
                # 显示详细信息
                st.markdown("### 📋 详细信息")
                
                info_data = {
                    "数据库路径": mlmd_info["database_path"],
                    "运行模式": mlmd_info["mode"],
                    "最后更新": mlmd_info["last_updated"],
                    "服务可用性": "✅ 可用" if mlmd_info["available"] else "❌ 不可用"
                }
                
                for key, value in info_data.items():
                    st.text(f"{key}: {value}")
                
                # 显示原始数据
                with st.expander("🔍 查看原始服务信息"):
                    st.json(mlmd_info)
            
            else:
                st.error(f"❌ 无法获取 MLMD 服务信息 (状态码: {response.status_code})")
        
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ MLMD 服务连接失败: {e}")
            st.info("💡 请确保 FastAPI 服务正在运行 (http://localhost:8000)")
        
        except Exception as e:
            st.error(f"❌ 获取 MLMD 信息时发生错误: {e}")
    
    def _render_lineage_graph(self):
        """渲染血缘关系图"""
        st.subheader("🌐 数据血缘关系图")
        
        # 查询选项
        col1, col2 = st.columns(2)
        with col1:
            artifact_id = st.text_input("🎯 Artifact ID (可选)", help="指定特定的 Artifact ID 进行查询")
        with col2:
            execution_id = st.text_input("⚙️ Execution ID (可选)", help="指定特定的 Execution ID 进行查询")
        
        if st.button("🔍 获取血缘关系图", type="primary"):
            try:
                # 构建查询参数
                params = {}
                if artifact_id:
                    params["artifact_id"] = artifact_id
                if execution_id:
                    params["execution_id"] = execution_id
                
                response = requests.get(f"{self.mlmd_api_url}/lineage/graph", params=params, timeout=15)
                
                if response.status_code == 200:
                    lineage_data = response.json()
                    
                    # 显示血缘关系图
                    self._visualize_lineage_graph(lineage_data)
                    
                    # 显示统计信息
                    metadata = lineage_data.get("metadata", {})
                    st.markdown("### 📊 血缘关系统计")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("节点总数", metadata.get("total_nodes", 0))
                    with col2:
                        st.metric("边总数", metadata.get("total_edges", 0))
                    with col3:
                        st.metric("生成模式", metadata.get("mode", "unknown"))
                    
                    # 显示原始数据
                    with st.expander("🔍 查看原始血缘数据"):
                        st.json(lineage_data)
                
                else:
                    st.error(f"❌ 获取血缘关系图失败 (状态码: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ 获取血缘关系图时发生错误: {e}")
    
    def _visualize_lineage_graph(self, lineage_data: Dict[str, Any]):
        """可视化血缘关系图"""
        nodes = lineage_data.get("nodes", [])
        edges = lineage_data.get("edges", [])
        
        if not nodes:
            st.warning("⚠️ 没有找到血缘关系数据")
            return
        
        # 创建网络图
        fig = go.Figure()
        
        # 节点位置计算 (简化的布局算法)
        node_positions = self._calculate_node_positions(nodes, edges)
        
        # 添加边
        for edge in edges:
            source_pos = node_positions.get(edge["source"])
            target_pos = node_positions.get(edge["target"])
            
            if source_pos and target_pos:
                fig.add_trace(go.Scatter(
                    x=[source_pos[0], target_pos[0], None],
                    y=[source_pos[1], target_pos[1], None],
                    mode='lines',
                    line=dict(width=2, color='gray'),
                    hoverinfo='none',
                    showlegend=False
                ))
        
        # 添加节点
        artifact_nodes = [n for n in nodes if n["type"] == "artifact"]
        execution_nodes = [n for n in nodes if n["type"] == "execution"]
        
        # Artifact 节点
        if artifact_nodes:
            artifact_x = [node_positions[n["id"]][0] for n in artifact_nodes]
            artifact_y = [node_positions[n["id"]][1] for n in artifact_nodes]
            artifact_text = [f"{n['name']}<br>({n.get('subtype', 'Unknown')})" for n in artifact_nodes]
            
            fig.add_trace(go.Scatter(
                x=artifact_x,
                y=artifact_y,
                mode='markers+text',
                marker=dict(size=20, color='lightblue', symbol='circle'),
                text=artifact_text,
                textposition="middle center",
                name="Artifacts",
                hovertemplate="<b>%{text}</b><br>类型: Artifact<extra></extra>"
            ))
        
        # Execution 节点
        if execution_nodes:
            execution_x = [node_positions[n["id"]][0] for n in execution_nodes]
            execution_y = [node_positions[n["id"]][1] for n in execution_nodes]
            execution_text = [f"{n['name']}<br>({n.get('subtype', 'Unknown')})" for n in execution_nodes]
            
            fig.add_trace(go.Scatter(
                x=execution_x,
                y=execution_y,
                mode='markers+text',
                marker=dict(size=20, color='lightcoral', symbol='square'),
                text=execution_text,
                textposition="middle center",
                name="Executions",
                hovertemplate="<b>%{text}</b><br>类型: Execution<extra></extra>"
            ))
        
        # 更新布局
        fig.update_layout(
            title="🌐 数据血缘关系图",
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[ dict(
                text="蓝色圆圈: Artifacts (数据/模型) | 红色方块: Executions (执行过程)",
                showarrow=False,
                xref="paper", yref="paper",
                x=0.005, y=-0.002,
                xanchor='left', yanchor='bottom',
                font=dict(size=12)
            )],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _calculate_node_positions(self, nodes: List[Dict], edges: List[Dict]) -> Dict[str, tuple]:
        """计算节点位置 (简化的布局算法)"""
        positions = {}
        
        # 简单的网格布局
        import math
        n_nodes = len(nodes)
        cols = math.ceil(math.sqrt(n_nodes))
        
        for i, node in enumerate(nodes):
            x = (i % cols) * 2
            y = (i // cols) * 2
            positions[node["id"]] = (x, y)
        
        return positions
    
    def _render_artifacts_management(self):
        """渲染 Artifacts 管理"""
        st.subheader("📦 Artifacts 管理")
        
        if st.button("🔄 刷新 Artifacts 列表", type="secondary"):
            try:
                response = requests.get(f"{self.mlmd_api_url}/lineage/artifacts", timeout=10)
                
                if response.status_code == 200:
                    artifacts_data = response.json()
                    artifacts = artifacts_data.get("artifacts", [])
                    
                    if artifacts:
                        # 创建 DataFrame
                        df_data = []
                        for artifact in artifacts:
                            df_data.append({
                                "ID": artifact["id"],
                                "名称": artifact["name"],
                                "类型": artifact.get("subtype", "Unknown"),
                                "URI": artifact.get("uri", ""),
                                "创建时间": artifact.get("timestamp", "")
                            })
                        
                        df = pd.DataFrame(df_data)
                        
                        # 显示统计信息
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Artifacts 总数", len(artifacts))
                        with col2:
                            types = df["类型"].value_counts()
                            st.metric("类型数量", len(types))
                        with col3:
                            st.metric("最新创建", df["创建时间"].max() if not df.empty else "无")
                        
                        # 显示 Artifacts 表格
                        st.markdown("### 📋 Artifacts 列表")
                        st.dataframe(df, use_container_width=True)
                        
                        # 类型分布图
                        if len(types) > 0:
                            st.markdown("### 📊 Artifacts 类型分布")
                            fig = px.pie(
                                values=types.values,
                                names=types.index,
                                title="Artifacts 类型分布"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # 显示原始数据
                        with st.expander("🔍 查看原始 Artifacts 数据"):
                            st.json(artifacts_data)
                    
                    else:
                        st.info("ℹ️ 暂无 Artifacts 数据")
                
                else:
                    st.error(f"❌ 获取 Artifacts 失败 (状态码: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ 获取 Artifacts 时发生错误: {e}")
    
    def _render_executions_management(self):
        """渲染 Executions 管理"""
        st.subheader("⚙️ Executions 管理")
        
        if st.button("🔄 刷新 Executions 列表", type="secondary"):
            try:
                response = requests.get(f"{self.mlmd_api_url}/lineage/executions", timeout=10)
                
                if response.status_code == 200:
                    executions_data = response.json()
                    executions = executions_data.get("executions", [])
                    
                    if executions:
                        # 创建 DataFrame
                        df_data = []
                        for execution in executions:
                            df_data.append({
                                "ID": execution["id"],
                                "名称": execution["name"],
                                "类型": execution.get("subtype", "Unknown"),
                                "创建时间": execution.get("timestamp", "")
                            })
                        
                        df = pd.DataFrame(df_data)
                        
                        # 显示统计信息
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Executions 总数", len(executions))
                        with col2:
                            types = df["类型"].value_counts()
                            st.metric("类型数量", len(types))
                        with col3:
                            st.metric("最新执行", df["创建时间"].max() if not df.empty else "无")
                        
                        # 显示 Executions 表格
                        st.markdown("### 📋 Executions 列表")
                        st.dataframe(df, use_container_width=True)
                        
                        # 类型分布图
                        if len(types) > 0:
                            st.markdown("### 📊 Executions 类型分布")
                            fig = px.pie(
                                values=types.values,
                                names=types.index,
                                title="Executions 类型分布"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # 显示原始数据
                        with st.expander("🔍 查看原始 Executions 数据"):
                            st.json(executions_data)
                    
                    else:
                        st.info("ℹ️ 暂无 Executions 数据")
                
                else:
                    st.error(f"❌ 获取 Executions 失败 (状态码: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ 获取 Executions 时发生错误: {e}")
    
    def _render_lineage_analysis(self):
        """渲染血缘分析"""
        st.subheader("📈 血缘关系分析")
        
        # 分析选项
        analysis_type = st.selectbox(
            "选择分析类型",
            ["管道深度分析", "数据流分析"],
            help="选择要执行的血缘关系分析类型"
        )
        
        if st.button("🔍 执行分析", type="primary"):
            if analysis_type == "管道深度分析":
                self._perform_pipeline_depth_analysis()
            elif analysis_type == "数据流分析":
                self._perform_data_flow_analysis()
    
    def _perform_pipeline_depth_analysis(self):
        """执行管道深度分析"""
        try:
            response = requests.get(f"{self.mlmd_api_url}/analysis/pipeline-depth", timeout=10)
            
            if response.status_code == 200:
                analysis_data = response.json()
                
                st.markdown("### 📊 管道深度分析结果")
                
                # 显示关键指标
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("管道深度", analysis_data["pipeline_depth"])
                with col2:
                    st.metric("Artifacts 总数", analysis_data["total_artifacts"])
                with col3:
                    st.metric("复杂度评分", f"{analysis_data['complexity_score']:.2f}")
                with col4:
                    st.metric("分析时间", analysis_data["analysis_timestamp"][:19])
                
                # Execution 类型分布
                if analysis_data["execution_types"]:
                    st.markdown("### ⚙️ Execution 类型分布")
                    exec_types = analysis_data["execution_types"]
                    fig = px.bar(
                        x=list(exec_types.keys()),
                        y=list(exec_types.values()),
                        title="Execution 类型分布",
                        labels={"x": "Execution 类型", "y": "数量"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Artifact 类型分布
                if analysis_data["artifact_types"]:
                    st.markdown("### 📦 Artifact 类型分布")
                    art_types = analysis_data["artifact_types"]
                    fig = px.bar(
                        x=list(art_types.keys()),
                        y=list(art_types.values()),
                        title="Artifact 类型分布",
                        labels={"x": "Artifact 类型", "y": "数量"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # 显示原始数据
                with st.expander("🔍 查看详细分析数据"):
                    st.json(analysis_data)
            
            else:
                st.error(f"❌ 管道深度分析失败 (状态码: {response.status_code})")
        
        except Exception as e:
            st.error(f"❌ 执行管道深度分析时发生错误: {e}")
    
    def _perform_data_flow_analysis(self):
        """执行数据流分析"""
        try:
            response = requests.get(f"{self.mlmd_api_url}/analysis/data-flow", timeout=10)
            
            if response.status_code == 200:
                analysis_data = response.json()
                
                st.markdown("### 🌊 数据流分析结果")
                
                # 显示关键指标
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("数据流总数", analysis_data["total_flows"])
                with col2:
                    st.metric("平均路径长度", f"{analysis_data['average_path_length']:.1f}")
                with col3:
                    st.metric("分析时间", analysis_data["analysis_timestamp"][:19])
                
                # 数据流详情
                data_flows = analysis_data["data_flows"]
                if data_flows:
                    st.markdown("### 📋 数据流路径")
                    
                    for i, flow in enumerate(data_flows):
                        with st.expander(f"数据流 {i+1}: {flow['source_dataset']}"):
                            st.write(f"**源数据集**: {flow['source_dataset']}")
                            st.write(f"**路径长度**: {flow['path_length']}")
                            st.write("**流动路径**:")
                            
                            # 显示流动路径
                            path_str = " → ".join(flow['flow_path'])
                            st.code(path_str)
                
                # 显示原始数据
                with st.expander("🔍 查看详细分析数据"):
                    st.json(analysis_data)
            
            else:
                st.error(f"❌ 数据流分析失败 (状态码: {response.status_code})")
        
        except Exception as e:
            st.error(f"❌ 执行数据流分析时发生错误: {e}")
    
    def _render_demo_and_testing(self):
        """渲染演示和测试"""
        st.subheader("🧪 演示和测试")
        
        # 创建示例数据
        st.markdown("### 🎯 创建示例血缘数据")
        st.markdown("点击下面的按钮创建示例血缘关系数据，用于演示和测试。")
        
        if st.button("🚀 创建示例血缘数据", type="primary"):
            try:
                response = requests.post(f"{self.mlmd_api_url}/demo/create-sample-lineage", timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    st.success("✅ 示例血缘数据创建成功！")
                    
                    # 显示创建结果
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**数据摄取执行 ID**: {result['ingestion_execution_id']}")
                    with col2:
                        st.info(f"**模型训练执行 ID**: {result['training_execution_id']}")
                    
                    st.markdown(f"**创建时间**: {result['created_at']}")
                    
                    # 显示原始响应
                    with st.expander("🔍 查看创建详情"):
                        st.json(result)
                    
                    st.markdown("---")
                    st.info("💡 现在您可以在 '血缘关系图' 标签页中查看创建的示例数据！")
                
                else:
                    st.error(f"❌ 创建示例数据失败 (状态码: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ 创建示例数据时发生错误: {e}")
        
        # 导出报告
        st.markdown("### 📄 导出血缘关系报告")
        st.markdown("生成并导出完整的血缘关系报告。")
        
        if st.button("📥 导出血缘关系报告", type="secondary"):
            try:
                response = requests.post(f"{self.mlmd_api_url}/reports/export", timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result["status"] == "generating":
                        st.info("⏳ 血缘关系报告正在后台生成...")
                        st.markdown(f"**报告路径**: {result['report_path']}")
                        st.markdown(f"**预计完成时间**: {result['estimated_completion']}")
                    else:
                        st.warning(f"⚠️ {result['message']}")
                
                else:
                    st.error(f"❌ 导出报告失败 (状态码: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ 导出报告时发生错误: {e}")


# 全局实例
def get_mlmd_ui_integration(api_base_url: str = "http://localhost:8000") -> MLMDUIIntegration:
    """获取 MLMD UI 集成实例"""
    return MLMDUIIntegration(api_base_url)


__all__ = ["MLMDUIIntegration", "get_mlmd_ui_integration"]
