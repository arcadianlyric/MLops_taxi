#!/usr/bin/env python3
"""
MLMD (ML Metadata) Streamlit UI 集成
提供数据血缘追踪和元数据管理的可视化界面
"""

import os
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
        """render MLMD main interface"""
        st.header("🔗 MLMD data lineage tracking")
        st.markdown("**ML Metadata (MLMD) data lineage relationship and metadata management**")
        
        # create tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 service overview", 
            "🌐 lineage graph", 
            "📦 artifacts", 
            "⚙️ executions",
            "📈 lineage analysis",
            "🧪 demo and testing"
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
        """render service overview"""
        st.subheader("📊 MLMD service status")
        
        try:
            # get MLMD service info
            response = requests.get(f"{self.mlmd_api_url}/info", timeout=10)
            
            if response.status_code == 200:
                mlmd_info = response.json()
                
                # 显示服务状态
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    status_color = "🟢" if mlmd_info["available"] else "🔴"
                    st.metric(
                        "status",
                        f"{status_color} {'available' if mlmd_info['available'] else 'unavailable'}",
                        delta=f"mode: {mlmd_info['mode']}"
                    )
                
                with col2:
                    st.metric(
                        "artifacts total",
                        mlmd_info["total_artifacts"],
                        delta="data and model artifacts"
                    )
                
                with col3:
                    st.metric(
                        "executions total",
                        mlmd_info["total_executions"],
                        delta="executions"
                    )
                
                with col4:
                    st.metric(
                        "events total",
                        mlmd_info["total_events"],
                        delta="lineage events"
                    )
                
                # show detailed info
                st.markdown("### 📋 detailed info")
                
                info_data = {
                    "database path": mlmd_info["database_path"],
                    "mode": mlmd_info["mode"],
                    "last updated": mlmd_info["last_updated"],
                    "available": "✅ available" if mlmd_info["available"] else "❌ unavailable"
                }
                
                for key, value in info_data.items():
                    st.text(f"{key}: {value}")
                
                # 显示原始数据
                with st.expander("🔍 show original info"):
                    st.json(mlmd_info)
            
            else:
                st.error(f"❌ MLMD info unavailable (status code: {response.status_code})")
        
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ MLMD connection failed: {e}")
            st.info("💡 please ensure FastAPI service is running (http://localhost:8000)")
        
        except Exception as e:
            st.error(f"❌ get MLMD info failed: {e}")
    
    def _render_lineage_graph(self):
        """render lineage graph"""
        st.subheader("🌐 data lineage graph")
        
        # query options
        col1, col2 = st.columns(2)
        with col1:
            artifact_id = st.text_input("🎯 artifact id (optional)", help="specify specific artifact id for query")
        with col2:
            execution_id = st.text_input("⚙️ execution id (optional)", help="specify specific execution id for query")
        
        if st.button("🔍 get lineage graph", type="primary"):
            try:
                # build query params
                params = {}
                if artifact_id:
                    params["artifact_id"] = artifact_id
                if execution_id:
                    params["execution_id"] = execution_id
                
                response = requests.get(f"{self.mlmd_api_url}/lineage/graph", params=params, timeout=15)
                
                if response.status_code == 200:
                    lineage_data = response.json()
                    
                    # visualize lineage graph
                    self._visualize_lineage_graph(lineage_data)
                    
                    # show statistics
                    metadata = lineage_data.get("metadata", {})
                    st.markdown("### 📊 lineage statistics")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("total nodes", metadata.get("total_nodes", 0))
                    with col2:
                        st.metric("total edges", metadata.get("total_edges", 0))
                    with col3:
                        st.metric("mode", metadata.get("mode", "unknown"))
                    
                    # show original data
                    with st.expander("🔍 show original lineage data"):
                        st.json(lineage_data)
                
                else:
                    st.error(f"❌ get lineage graph failed (status code: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ get lineage graph failed: {e}")
    
    def _visualize_lineage_graph(self, lineage_data: Dict[str, Any]):
        """visualize lineage graph"""
        nodes = lineage_data.get("nodes", [])
        edges = lineage_data.get("edges", [])
        
        if not nodes:
            st.warning("⚠️ no lineage data found")
            return
        
        # create network graph
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
        
        # update layout
        fig.update_layout(
            title="🌐 data lineage graph",
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[ dict(
                text="blue circle: Artifacts (data/model) | red square: Executions (execution process)",
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
        """render artifacts management"""
        st.subheader("📦 artifacts management")
        
        if st.button("🔄 refresh artifacts list", type="secondary"):
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
                                "name": artifact["name"],
                                "subtype": artifact.get("subtype", "Unknown"),
                                "URI": artifact.get("uri", ""),
                                "timestamp": artifact.get("timestamp", "")
                            })
                        
                        df = pd.DataFrame(df_data)
                        
                        # show statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Artifacts count", len(artifacts))
                        with col2:
                            types = df["subtype"].value_counts()
                            st.metric("subtype count", len(types))
                        with col3:
                            st.metric("latest created", df["timestamp"].max() if not df.empty else "")
                        
                        # 显示 Artifacts 表格
                        st.markdown("### 📋 Artifacts list")
                        st.dataframe(df, use_container_width=True)
                        
                        # subtype distribution
                        if len(types) > 0:
                            st.markdown("### 📊 Artifacts subtype distribution")
                            fig = px.pie(
                                values=types.values,
                                names=types.index,
                                title="Artifacts subtype distribution"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # show original data
                        with st.expander("🔍 show original Artifacts data"):
                            st.json(artifacts_data)
                    
                    else:
                        st.info("ℹ️ no Artifacts data")
                
                else:
                    st.error(f"❌ failed to get Artifacts (status code: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ failed to get Artifacts: {e}")
    
    def _render_executions_management(self):
        """render Executions management"""
        st.subheader("⚙️ Executions management")
        
        if st.button("🔄 refresh Executions list", type="secondary"):
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
                                "name": execution["name"],
                                "subtype": execution.get("subtype", "Unknown"),
                                "timestamp": execution.get("timestamp", "")
                            })
                        
                        df = pd.DataFrame(df_data)
                        
                        # show statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Executions count", len(executions))
                        with col2:
                            types = df["subtype"].value_counts()
                            st.metric("subtype count", len(types))
                        with col3:
                            st.metric("latest execution", df["timestamp"].max() if not df.empty else "")
                        
                        # 显示 Executions 表格
                        st.markdown("### 📋 Executions list")
                        st.dataframe(df, use_container_width=True)
                        
                        # subtype distribution
                        if len(types) > 0:
                            st.markdown("### 📊 Executions subtype distribution")
                            fig = px.pie(
                                values=types.values,
                                names=types.index,
                                title="Executions subtype distribution"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # show original data
                        with st.expander("🔍 show original Executions data"):
                            st.json(executions_data)
                    
                    else:
                        st.info("ℹ️ no Executions data")
                
                else:
                    st.error(f"❌ failed to get Executions (status code: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ failed to get Executions: {e}")
    
    def _render_lineage_analysis(self):
        """渲染血缘分析"""
        st.subheader("📈 lineage analysis")
        
        # analysis type
        analysis_type = st.selectbox(
            "analysis type",
            ["pipeline depth analysis", "data flow analysis"],
            help="select the type of lineage analysis to execute"
        )
        
        if st.button("🔍 execute analysis", type="primary"):
            if analysis_type == "pipeline depth analysis":
                self._perform_pipeline_depth_analysis()
            elif analysis_type == "data flow analysis":
                self._perform_data_flow_analysis()
    
    def _perform_pipeline_depth_analysis(self):
        """执行管道深度分析"""
        try:
            response = requests.get(f"{self.mlmd_api_url}/analysis/pipeline-depth", timeout=10)
            
            if response.status_code == 200:
                analysis_data = response.json()
                
                st.markdown("### 📊 pipeline depth analysis result")
                
                # show key metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("pipeline depth", analysis_data["pipeline_depth"])
                with col2:
                    st.metric("total artifacts", analysis_data["total_artifacts"])
                with col3:
                    st.metric("complexity score", f"{analysis_data['complexity_score']:.2f}")
                with col4:
                    st.metric("analysis timestamp", analysis_data["analysis_timestamp"][:19])
                
                # Execution types distribution
                if analysis_data["execution_types"]:
                    st.markdown("### ⚙️ Execution types distribution")
                    exec_types = analysis_data["execution_types"]
                    fig = px.bar(
                        x=list(exec_types.keys()),
                        y=list(exec_types.values()),
                        title="Execution types distribution",
                        labels={"x": "Execution types", "y": "count"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Artifact types distribution
                if analysis_data["artifact_types"]:
                    st.markdown("### 📦 Artifact types distribution")
                    art_types = analysis_data["artifact_types"]
                    fig = px.bar(
                        x=list(art_types.keys()),
                        y=list(art_types.values()),
                        title="Artifact types distribution",
                        labels={"x": "Artifact types", "y": "count"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # show original data
                with st.expander("🔍 show detailed analysis data"):
                    st.json(analysis_data)
            
            else:
                st.error(f"❌ pipeline depth analysis failed (status code: {response.status_code})")
        
        except Exception as e:
            st.error(f"❌ failed to perform pipeline depth analysis: {e}")
    
    def _perform_data_flow_analysis(self):
        """执行数据流分析"""
        try:
            response = requests.get(f"{self.mlmd_api_url}/analysis/data-flow", timeout=10)
            
            if response.status_code == 200:
                analysis_data = response.json()
                
                st.markdown("### 🌊 data flow analysis result")
                
                # show key metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("total data flows", analysis_data["total_flows"])
                with col2:
                    st.metric("average path length", f"{analysis_data['average_path_length']:.1f}")
                with col3:
                    st.metric("analysis timestamp", analysis_data["analysis_timestamp"][:19])
                
                # data flows details
                data_flows = analysis_data["data_flows"]
                if data_flows:
                    st.markdown("### 📋 data flows paths")
                    
                    for i, flow in enumerate(data_flows):
                        with st.expander(f"data flow {i+1}: {flow['source_dataset']}"):
                            st.write(f"**source dataset**: {flow['source_dataset']}")
                            st.write(f"**path length**: {flow['path_length']}")
                            st.write("**flow path**:")
                            
                            # show flow path
                            path_str = " → ".join(flow['flow_path'])
                            st.code(path_str)
                
                # show original data
                with st.expander("🔍 show detailed analysis data"):
                    st.json(analysis_data)
            
            else:
                st.error(f"❌ data flow analysis failed (status code: {response.status_code})")
        
        except Exception as e:
            st.error(f"❌ data flow analysis failed: {e}")
    
    def _render_demo_and_testing(self):
        """渲染演示和测试"""
        st.subheader("🧪 demo and testing")
        
        # create example data
        st.markdown("### 🎯 create example lineage data")
        st.markdown("click the button below to create example lineage data for demo and testing.")
        
        if st.button("🚀 create example lineage data", type="primary"):
            try:
                response = requests.post(f"{self.mlmd_api_url}/demo/create-sample-lineage", timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    st.success("✅ example lineage data created successfully!")
                    
                    # show creation result
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**ingestion execution id**: {result['ingestion_execution_id']}")
                    with col2:
                        st.info(f"**training execution id**: {result['training_execution_id']}")
                    
                    st.markdown(f"**created at**: {result['created_at']}")
                    
                    # 显示原始响应
                    with st.expander("🔍 show details"):
                        st.json(result)
                    
                    st.markdown("---")
                    st.info("💡 now you can view the created example data in the 'lineage graph' tab!")
                
                else:
                    st.error(f"❌ failed to create example data (status code: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ failed to create example data: {e}")
        
        # export report
        st.markdown("### 📄 export report")
        st.markdown("generate and export complete lineage report.")
        
        if st.button("📥 export report", type="secondary"):
            try:
                response = requests.post(f"{self.mlmd_api_url}/reports/export", timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result["status"] == "generating":
                        st.info("⏳ report is generating...")
                        st.markdown(f"**report path**: {result['report_path']}")
                        st.markdown(f"**estimated completion**: {result['estimated_completion']}")
                    else:
                        st.warning(f"⚠️ {result['message']}")
                
                else:
                    st.error(f"❌ failed to export report (status code: {response.status_code})")
            
            except Exception as e:
                st.error(f"❌ failed to export report: {e}")


# 全局实例
def get_mlmd_ui_integration(api_base_url: str = None) -> MLMDUIIntegration:
    """获取 MLMD UI 集成实例"""
    if api_base_url is None:
        api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    return MLMDUIIntegration(api_base_url)


__all__ = ["MLMDUIIntegration", "get_mlmd_ui_integration"]
