#!/usr/bin/env python3
"""
Streamlit UI - MLOps Platform Frontend Interface
Chicago Taxi Fare Prediction based on TFX Pipeline
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
import random

# Add project path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import integration modules
from feast_ui_integration import feast_ui
from kafka_ui_integration import kafka_ui
from mlflow_ui_integration import mlflow_ui
from mlmd_ui_integration import get_mlmd_ui_integration

# Page configuration
st.set_page_config(
    page_title="MLOps Platform - Chicago Taxi Fare Prediction",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Custom CSS – normalise font sizes (only st.header stays large)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Metric label */
[data-testid="stMetricLabel"] { font-size: 0.85rem !important; }
/* Metric value */
[data-testid="stMetricValue"] { font-size: 1.1rem !important; }
/* Metric delta */
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }
/* Subheaders inside tabs */
.stTabs [data-baseweb="tab-panel"] h3 { font-size: 1.05rem !important; }
/* Tab labels */
.stTabs [data-baseweb="tab"] button p { font-size: 0.85rem !important; }
/* Expander header */
.streamlit-expanderHeader p { font-size: 0.9rem !important; }
/* General markdown / body text */
.stMarkdown p, .stMarkdown li { font-size: 0.9rem !important; }
/* Dataframe header */
[data-testid="stDataFrame"] th { font-size: 0.8rem !important; }
/* Selectbox / input labels */
.stSelectbox label, .stNumberInput label, .stTextInput label,
.stSlider label, .stRadio label { font-size: 0.85rem !important; }
</style>
""", unsafe_allow_html=True)

# Global configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def check_api_health():
    """Check API service health status"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

def call_taxi_prediction_api(features: Dict[str, Any], endpoint: str = "predict"):
    """Call Chicago Taxi fare prediction API"""
    try:
        payload = features
        
        response = requests.post(
            f"{API_BASE_URL}/{endpoint}",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"API Error: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"Request Failed: {str(e)}"

def call_batch_prediction_api(taxi_trips: List[Dict[str, Any]]):
    """Call batch taxi fare prediction API"""
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
            return False, f"API Error: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"Request Failed: {str(e)}"

def main():
    """Main interface"""
    
    # Title and description
    st.title("🚕 MLOps Platform - Chicago Taxi Fare Prediction")
    st.markdown("Taxi fare prediction system based on TFX Pipeline + Kubeflow + KFServing")
    
    # Sidebar - Service status
    with st.sidebar:
        st.header("🔧 Service Status")
        
        # Check API health status
        is_healthy, health_data = check_api_health()
        
        if is_healthy:
            st.success("✅ API Service Normal")
            if health_data:
                st.json(health_data)
        else:
            st.error("❌ API Service Unavailable")
            st.warning("Please ensure FastAPI service is running: `uvicorn api.main:app --reload`")
        
        st.divider()
        
        # Configuration options
        st.header("⚙️ Configuration Options")
        api_timeout = st.slider("API Timeout (seconds)", 5, 60, 30)
        show_debug = st.checkbox("Show Debug Info", False)
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "🚖 Single Prediction", 
        "📊 Batch Prediction", 
        "📈 Data Analysis", 
        "⚡ Performance Monitoring", 
        "🔍 Data Drift Monitoring",
        "🍃 Feast Feature Store",
        "🚀 Kafka Stream Processing",
        "🎯 MLflow Model Registry",
        "🔗 MLMD Data Lineage"
    ])
    
    # Tab 1: Single prediction
    with tab1:
        st.header("🚕 Single Taxi Fare Prediction")
        st.markdown("Enter taxi trip information to predict tip amount")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Trip Information Input")
            
            # Basic trip information
            st.write("**🚕 Basic Information**")
            trip_miles = st.number_input("Trip Distance (miles)", min_value=0.1, max_value=100.0, value=5.2, step=0.1)
            trip_seconds = st.number_input("Trip Duration (seconds)", min_value=60, max_value=7200, value=900, step=30)
            fare = st.number_input("Fare (USD)", min_value=2.5, max_value=200.0, value=12.5, step=0.25)
            
            st.write("**📍 Location Information**")
            pickup_latitude = st.number_input("Pickup Latitude", min_value=41.6, max_value=42.1, value=41.8781, step=0.0001, format="%.4f")
            pickup_longitude = st.number_input("Pickup Longitude", min_value=-87.9, max_value=-87.5, value=-87.6298, step=0.0001, format="%.4f")
            dropoff_latitude = st.number_input("Dropoff Latitude", min_value=41.6, max_value=42.1, value=41.8881, step=0.0001, format="%.4f")
            dropoff_longitude = st.number_input("Dropoff Longitude", min_value=-87.9, max_value=-87.5, value=-87.6198, step=0.0001, format="%.4f")
            
            st.write("**⏰ Time Information**")
            trip_start_hour = st.selectbox("Departure Hour", range(24), index=14)
            trip_start_day = st.selectbox("Departure Day (1-31)", range(1, 32), index=14)
            trip_start_month = st.selectbox("Departure Month", range(1, 13), index=5)
            
            st.write("**🏢 Area Information**")
            pickup_community_area = st.number_input("Pickup Community Area", min_value=1, max_value=77, value=8)
            dropoff_community_area = st.number_input("Dropoff Community Area", min_value=1, max_value=77, value=24)
            pickup_census_tract = st.number_input("Pickup Census Tract", min_value=1, max_value=999999, value=170301)
            dropoff_census_tract = st.number_input("Dropoff Census Tract", min_value=1, max_value=999999, value=170401)
            
            st.write("**💳 Payment Information**")
            payment_type = st.selectbox("Payment Type", ["Credit Card", "Cash", "No Charge", "Dispute", "Unknown"])
            company = st.selectbox("Taxi Company", ["Flash Cab", "Taxi Affiliation Services", "Yellow Cab", "Blue Diamond", "Other"])
        
        with col2:
            st.markdown("### 🚀 Execute Prediction")
            
            # Build feature dictionary
            # Calculate pickup_day_of_week (Monday=0, Sunday=6)
            try:
                trip_date = datetime(2023, trip_start_month, trip_start_day)
                pickup_day_of_week = trip_date.weekday()
            except ValueError:
                st.error("Invalid date selected. Please choose a valid day for the selected month.")
                pickup_day_of_week = 0 # Default to Monday on error

            features = {
                "trip_miles": trip_miles,
                "trip_seconds": trip_seconds,
                "fare": fare,
                "pickup_latitude": pickup_latitude,
                "pickup_longitude": pickup_longitude,
                "dropoff_latitude": dropoff_latitude,
                "dropoff_longitude": dropoff_longitude,
                "pickup_hour": trip_start_hour, # Renamed from trip_start_hour
                "pickup_day_of_week": pickup_day_of_week, # Added calculated field
                "trip_start_day": trip_start_day,
                "trip_start_month": trip_start_month,
                "pickup_community_area": pickup_community_area,
                "dropoff_community_area": dropoff_community_area,
                "pickup_census_tract": pickup_census_tract,
                "dropoff_census_tract": dropoff_census_tract,
                "payment_type": payment_type,
                "company": company,
                "passenger_count": 1 # Assuming a default passenger count
            }
            
            # Display input summary
            st.write("📋 **Input Summary**")
            summary_col1, summary_col2 = st.columns(2)
            with summary_col1:
                st.markdown(f"<small>**Trip Distance:** {trip_miles} miles</small>", unsafe_allow_html=True)
                st.markdown(f"<small>**Fare:** ${fare}</small>", unsafe_allow_html=True)
            with summary_col2:
                st.markdown(f"<small>**Trip Duration:** {trip_seconds//60} minutes</small>", unsafe_allow_html=True)
                st.markdown(f"<small>**Payment Type:** {payment_type}</small>", unsafe_allow_html=True)
            
            # Execute prediction
            if st.button("🚕 Predict Tip", type="primary"):
                with st.spinner("Predicting tip amount..."):
                    start_time = time.time()
                    success, result = call_taxi_prediction_api(features)
                    end_time = time.time()
                    
                    if success:
                        st.success(f"✅ Prediction completed! Time taken: {(end_time-start_time)*1000:.2f}ms")
                        
                        # Display prediction results
                        if result and 'fare_amount' in result:
                            predicted_fare = result['fare_amount']
                            
                            # Main result display
                            st.markdown("### 🎆 Prediction Results")
                            
                            st.metric("💰 Predicted Fare", f"${predicted_fare:.2f}")
                            
                            
                    else:
                        st.error(f"❌ Prediction failed: {result}")
            
            # Debug information
            if show_debug:
                st.subheader("🔍 Debug Information")
                st.json({
                    "API_URL": f"{API_BASE_URL}/predict",
                    "Feature Data": features,
                    "Feature Count": len(features)
                })
    
    # Tab 2: Batch prediction
    with tab2:
        st.header("📦 Batch Taxi Fare Prediction")
        st.markdown("Test large-scale batch prediction performance and data analysis")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("⚙️ Batch Configuration")
            
            batch_size = st.slider("Batch Size", 1, 50, 20)
            num_trips = st.slider("Number of Trips", 10, 200, 50)
            
            st.info(f"📊 Total Trips: {num_trips}")
            
            # Generate batch test data
            if st.button("📦 Generate Batch Test Data"):
                
                # Chicago taxi data ranges
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
                st.success(f"✅ Generated test data for {len(batch_trips)} taxi trips")
                
                # Display data preview
                if batch_trips:
                    preview_df = pd.DataFrame(batch_trips[:5])  # Show first 5 records
                    st.dataframe(preview_df, use_container_width=True)
        
        with col2:
            st.subheader("🚀 Execute Batch Prediction")
            
            if 'batch_trips' in st.session_state:
                if st.button("📦 Start Batch Prediction", type="primary"):
                    batch_trips = st.session_state.batch_trips
                    
                    try:
                        with st.spinner("Executing batch prediction..."):
                            start_time = time.time()
                            success, result = call_batch_prediction_api(batch_trips)
                            end_time = time.time()
                            
                            if success:
                                st.success(f"✅ Batch prediction completed!")
                                
                                # Performance metrics
                                total_time = end_time - start_time
                                throughput = len(batch_trips) / total_time
                                avg_latency = total_time / len(batch_trips) * 1000
                                
                                col_perf1, col_perf2, col_perf3 = st.columns(3)
                                with col_perf1:
                                    st.metric("Total Time", f"{total_time:.2f}s")
                                with col_perf2:
                                    st.metric("Throughput", f"{throughput:.2f} trips/s")
                                with col_perf3:
                                    st.metric("Average Latency", f"{avg_latency:.2f}ms")
                                
                                # Result analysis
                                if result and 'predictions' in result:
                                    predictions = result['predictions']
                                    
                                    # Create results DataFrame
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
                                    
                                    # Display statistics
                                    st.markdown("### 📊 Batch Prediction Statistics")
                                    
                                    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                                    with stat_col1:
                                        st.metric("Average Tip", f"${results_df['predicted_tip'].mean():.2f}")
                                    with stat_col2:
                                        st.metric("Average Tip Rate", f"{results_df['tip_rate'].mean():.1f}%")
                                    with stat_col3:
                                        st.metric("Highest Tip", f"${results_df['predicted_tip'].max():.2f}")
                                    with stat_col4:
                                        st.metric("Lowest Tip", f"${results_df['predicted_tip'].min():.2f}")
                                    
                                    # Tip distribution histogram
                                    fig_hist = px.histogram(
                                        results_df, 
                                        x='predicted_tip',
                                        nbins=20,
                                        title="Tip Amount Distribution",
                                        labels={'predicted_tip': 'Predicted Tip ($)', 'count': 'Count'}
                                    )
                                    st.plotly_chart(fig_hist, use_container_width=True)
                                    
                                    # Payment type vs tip rate
                                    fig_box = px.box(
                                        results_df, 
                                        x='payment_type', 
                                        y='tip_rate',
                                        title="Tip Rate Distribution by Payment Type",
                                        labels={'tip_rate': 'Tip Rate (%)', 'payment_type': 'Payment Type'}
                                    )
                                    st.plotly_chart(fig_box, use_container_width=True)
                                    
                                    # Display detailed results table
                                    st.markdown("### 📋 Detailed Results")
                                    st.dataframe(results_df.head(20), use_container_width=True)
                                    
                            else:
                                st.error(f"❌ Batch prediction failed: {result}")
                                
                    except Exception as e:
                        st.error(f"❌ Batch prediction error: {str(e)}")
            else:
                st.warning("Please generate batch test data first")
    
    # Tab 3: Data analysis (real data from API)
    with tab3:
        st.header("📊 Chicago Taxi Data Analysis")
        st.markdown("In-depth analysis and insights based on **real Chicago Taxi dataset**")
        
        try:
            stats_resp = requests.get(f"{API_BASE_URL}/data/stats", timeout=15)
            if stats_resp.status_code == 200:
                stats_json = stats_resp.json()
                stats_data = stats_json.get("data", {})
                total_rows = stats_json.get("total_rows", 0)
                
                # Data overview from real stats
                st.subheader("📈 Data Overview")
                fare_stats = stats_data.get("fare", {})
                tips_stats = stats_data.get("tips", {})
                miles_stats = stats_data.get("trip_miles", {})
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Trips", f"{total_rows:,}")
                with col2:
                    st.metric("Average Fare", f"${fare_stats.get('mean', 0):.2f}")
                with col3:
                    st.metric("Average Tip", f"${tips_stats.get('mean', 0):.2f}")
                with col4:
                    avg_tip_rate = (tips_stats.get('mean', 0) / fare_stats.get('mean', 1) * 100) if fare_stats.get('mean', 0) > 0 else 0
                    st.metric("Average Tip Rate", f"{avg_tip_rate:.1f}%")
                
                # Data analysis options
                analysis_type = st.selectbox(
                    "Select Analysis Type:",
                    ["Time Trend Analysis", "Fare & Tip Distribution", "Payment Method Analysis", "Company Performance Comparison"]
                )
                
                if analysis_type == "Time Trend Analysis":
                    st.subheader("⏰ Time Trend Analysis")
                    hourly = stats_data.get("hourly", [])
                    if hourly:
                        hourly_df = pd.DataFrame(hourly)
                        col_h1, col_h2 = st.columns(2)
                        with col_h1:
                            fig_tips = px.line(hourly_df, x="trip_start_hour", y="avg_tips",
                                             title="Average Tip by Hour (Real Data)",
                                             labels={"trip_start_hour": "Hour", "avg_tips": "Average Tip ($)"})
                            fig_tips.update_traces(line=dict(color='blue', width=3))
                            st.plotly_chart(fig_tips, use_container_width=True)
                        with col_h2:
                            fig_fare = px.bar(hourly_df, x="trip_start_hour", y="avg_fare",
                                            title="Average Fare by Hour (Real Data)",
                                            labels={"trip_start_hour": "Hour", "avg_fare": "Average Fare ($)"},
                                            color="avg_fare", color_continuous_scale="blues")
                            st.plotly_chart(fig_fare, use_container_width=True)
                        
                        fig_count = px.bar(hourly_df, x="trip_start_hour", y="count",
                                          title="Trip Count by Hour (Real Data)",
                                          labels={"trip_start_hour": "Hour", "count": "Trip Count"},
                                          color="count", color_continuous_scale="viridis")
                        st.plotly_chart(fig_count, use_container_width=True)
                        
                        peak_hour = hourly_df.loc[hourly_df["avg_tips"].idxmax()]
                        low_hour = hourly_df.loc[hourly_df["avg_tips"].idxmin()]
                        st.info(f"💡 **Insight**: Peak tip hour is **{int(peak_hour['trip_start_hour'])}:00** (avg ${peak_hour['avg_tips']:.2f}), lowest at **{int(low_hour['trip_start_hour'])}:00** (avg ${low_hour['avg_tips']:.2f})")
                    else:
                        st.warning("No hourly data available")
                
                elif analysis_type == "Fare & Tip Distribution":
                    st.subheader("� Fare & Tip Distribution")
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.markdown("**Fare Statistics**")
                        fare_df = pd.DataFrame([fare_stats]).T
                        fare_df.columns = ["Value"]
                        st.dataframe(fare_df, use_container_width=True)
                    with col_d2:
                        st.markdown("**Tip Statistics**")
                        tips_df = pd.DataFrame([tips_stats]).T
                        tips_df.columns = ["Value"]
                        st.dataframe(tips_df, use_container_width=True)
                    
                    monthly = stats_data.get("monthly", [])
                    if monthly:
                        monthly_df = pd.DataFrame(monthly)
                        fig_monthly = px.bar(monthly_df, x="trip_start_month", y=["avg_fare", "avg_tips"],
                                            title="Monthly Average Fare & Tip (Real Data)",
                                            labels={"trip_start_month": "Month", "value": "Amount ($)"},
                                            barmode="group")
                        st.plotly_chart(fig_monthly, use_container_width=True)
                
                elif analysis_type == "Payment Method Analysis":
                    st.subheader("💳 Payment Method Analysis")
                    by_payment = stats_data.get("by_payment_type", [])
                    if by_payment:
                        pay_df = pd.DataFrame(by_payment)
                        pay_df["tip_rate"] = (pay_df["avg_tips"] / pay_df["avg_fare"].replace(0, np.nan) * 100).fillna(0)
                        
                        col_pay1, col_pay2 = st.columns(2)
                        with col_pay1:
                            fig_pt = px.bar(pay_df, x="payment_type", y="avg_tips",
                                           title="Average Tip by Payment Method (Real Data)",
                                           color="avg_tips", color_continuous_scale="blues")
                            st.plotly_chart(fig_pt, use_container_width=True)
                        with col_pay2:
                            fig_pr = px.bar(pay_df, x="payment_type", y="tip_rate",
                                           title="Tip Rate by Payment Method (Real Data)",
                                           color="tip_rate", color_continuous_scale="reds")
                            st.plotly_chart(fig_pr, use_container_width=True)
                        
                        fig_pie = px.pie(pay_df, values="count", names="payment_type",
                                        title="Trip Count by Payment Method")
                        st.plotly_chart(fig_pie, use_container_width=True)
                        st.dataframe(pay_df, use_container_width=True)
                        
                        top_pay = pay_df.loc[pay_df["avg_tips"].idxmax()]
                        st.info(f"💡 **Insight**: **{top_pay['payment_type']}** has the highest average tip (${top_pay['avg_tips']:.2f})")
                    else:
                        st.warning("No payment type data available")
                
                else:  # Company performance comparison
                    st.subheader("🚕 Taxi Company Performance Comparison")
                    by_company = stats_data.get("by_company", [])
                    if by_company:
                        co_df = pd.DataFrame(by_company).sort_values("avg_tips", ascending=False).head(10)
                        
                        fig_co = px.bar(co_df, x="company", y=["avg_fare", "avg_tips"],
                                       title="Top 10 Companies: Average Fare & Tip (Real Data)",
                                       barmode="group")
                        fig_co.update_layout(xaxis_tickangle=45)
                        st.plotly_chart(fig_co, use_container_width=True)
                        
                        fig_scatter = px.scatter(co_df, x="avg_fare", y="avg_tips", size="count",
                                               color="company", hover_name="company",
                                               title="Company Performance (bubble size = trip count)",
                                               labels={"avg_fare": "Average Fare ($)", "avg_tips": "Average Tip ($)"})
                        st.plotly_chart(fig_scatter, use_container_width=True)
                        st.dataframe(co_df, use_container_width=True)
                        
                        best = co_df.iloc[0]
                        st.info(f"💡 **Insight**: **{best['company']}** has the highest average tip (${best['avg_tips']:.2f}) with {int(best['count'])} trips")
                    else:
                        st.warning("No company data available")
            else:
                st.error(f"Failed to load data stats: HTTP {stats_resp.status_code}")
        except Exception as e:
            st.error(f"Failed to load data analysis: {str(e)}")
            st.info("Please ensure FastAPI service is running")

    
    # Tab 4: Performance monitoring
    with tab4:
        st.header("🔍 Chicago Taxi Model Performance Monitoring")
        st.markdown("Real-time monitoring of TFX Pipeline model service performance and system status")
        
        # Get service metrics
        try:
            response = requests.get(f"{API_BASE_URL}/metrics", timeout=10)
            if response.status_code == 200:
                metrics = response.json()
                
                # Service status overview
                st.subheader("🟢 Service Status Overview")
                col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
                with col_metric1:
                    st.metric("🚕 Model Service", metrics.get('model_status', 'Normal'))
                with col_metric2:
                    st.metric("🔗 API Status", "Normal" if metrics.get('api_status', True) else "Error")
                with col_metric3:
                    st.metric("📊 Prediction Count", f"{metrics.get('total_predictions', 0):,}")
                with col_metric4:
                    st.metric("Last Updated", metrics.get('timestamp', 'N/A')[:19])
                
                # Simulated performance data (in actual deployment, get from Prometheus)
                if st.button("🔄 Refresh Monitoring Data"):
                    
                    # Generate simulated time series data
                    timestamps = pd.date_range(
                        start=datetime.now().replace(hour=0, minute=0, second=0),
                        periods=24,
                        freq='H'
                    )
                    
                    # Simulated metrics
                    latency_data = [50 + random.gauss(0, 10) for _ in range(24)]
                    throughput_data = [100 + random.gauss(0, 20) for _ in range(24)]
                    error_rate_data = [random.uniform(0, 5) for _ in range(24)]
                    
                    # Latency trend
                    fig_latency = go.Figure()
                    fig_latency.add_trace(go.Scatter(
                        x=timestamps,
                        y=latency_data,
                        mode='lines+markers',
                        name='Average Latency (ms)',
                        line=dict(color='blue')
                    ))
                    fig_latency.update_layout(title="Inference Latency Trend", xaxis_title="Time", yaxis_title="Latency (ms)")
                    st.plotly_chart(fig_latency, use_container_width=True)
                    
                    # Throughput and error rate
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        fig_throughput = go.Figure()
                        fig_throughput.add_trace(go.Scatter(
                            x=timestamps,
                            y=throughput_data,
                            mode='lines+markers',
                            name='Throughput (req/s)',
                            line=dict(color='green')
                        ))
                        fig_throughput.update_layout(title="Throughput Trend", xaxis_title="Time", yaxis_title="Requests/Second")
                        st.plotly_chart(fig_throughput, use_container_width=True)
                    
                    with col_chart2:
                        fig_error = go.Figure()
                        fig_error.add_trace(go.Scatter(
                            x=timestamps,
                            y=error_rate_data,
                            mode='lines+markers',
                            name='Error Rate (%)',
                            line=dict(color='red')
                        ))
                        fig_error.update_layout(title="Error Rate Trend", xaxis_title="Time", yaxis_title="Error Rate (%)")
                        st.plotly_chart(fig_error, use_container_width=True)
                    
                    # Performance summary
                    st.subheader("📈 Performance Summary")
                    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                    
                    with summary_col1:
                        st.metric("Average Latency", f"{np.mean(latency_data):.1f} ms")
                    with summary_col2:
                        st.metric("Average Throughput", f"{np.mean(throughput_data):.1f} req/s")
                    with summary_col3:
                        st.metric("Average Error Rate", f"{np.mean(error_rate_data):.2f}%")
                    with summary_col4:
                        st.metric("Availability", "99.9%")
            else:
                st.error("Unable to retrieve service metrics")
                
        except Exception as e:
            st.error(f"Failed to retrieve monitoring data: {str(e)}")
    
    # Tab 5: Data drift monitoring (real data from API)
    with tab5:
        st.header("🔍 Data Drift Monitoring")
        st.markdown("Monitor data distribution changes based on **real Chicago Taxi dataset** (baseline vs current split)")
        
        try:
            drift_resp = requests.get(f"{API_BASE_URL}/data/drift", timeout=15)
            if drift_resp.status_code == 200:
                drift_data = drift_resp.json()
                drift_summary = drift_data.get("summary", {})
                drift_details = drift_data.get("feature_details", {})
                drift_recs = drift_data.get("recommendations", [])
                
                # Overview metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Features Monitored", drift_summary.get("total_features_checked", 0))
                with col2:
                    st.metric("Drift Detected", drift_summary.get("drifted_features_count", 0))
                with col3:
                    avg_score = np.mean([v["drift_score"] for v in drift_details.values()]) if drift_details else 0
                    st.metric("Avg Drift Score", f"{avg_score:.3f}")
                with col4:
                    st.metric("Baseline / Current", f"{drift_summary.get('baseline_rows', 0):,} / {drift_summary.get('current_rows', 0):,}")
                
                st.divider()
                
                drift_tab1, drift_tab2, drift_tab3 = st.tabs([
                    "📊 Drift Overview", "📈 Feature Analysis", "⚠️ Alerts & Actions"
                ])
                
                with drift_tab1:
                    st.subheader("Data Drift Overview (Real Data)")
                    
                    drift_features = list(drift_details.keys())
                    drift_scores_list = [drift_details[f]["drift_score"] for f in drift_features]
                    drift_types = [drift_details[f]["drift_type"] for f in drift_features]
                    
                    color_map = {"No": "#2E8B57", "Low": "#FFD700", "Medium": "#FF8C00", "High": "#DC143C"}
                    colors = [color_map.get(dt, "#808080") for dt in drift_types]
                    
                    fig_drift = go.Figure(data=[
                        go.Bar(x=drift_features, y=drift_scores_list, marker_color=colors,
                               text=[f"{s:.3f} ({t})" for s, t in zip(drift_scores_list, drift_types)],
                               textposition='auto')
                    ])
                    fig_drift.add_hline(y=0.1, line_dash="dash", line_color="red", annotation_text="Drift Threshold (0.1)")
                    fig_drift.update_layout(title="Feature Drift Scores (Real Data)", xaxis_title="Feature",
                                           yaxis_title="Drift Score", height=500)
                    fig_drift.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_drift, use_container_width=True)
                    
                    drift_table = pd.DataFrame({
                        "Feature": drift_features,
                        "Drift Score": drift_scores_list,
                        "Type": drift_types,
                        "Drifted": [drift_details[f]["is_drifted"] for f in drift_features],
                    })
                    st.dataframe(drift_table, use_container_width=True)
                
                with drift_tab2:
                    st.subheader("Feature Analysis (Real Data)")
                    
                    selected_drift_feat = st.selectbox("Select feature to analyze:", drift_features, key="drift_feat_select")
                    
                    if selected_drift_feat and selected_drift_feat in drift_details:
                        detail = drift_details[selected_drift_feat]
                        baseline_s = detail.get("baseline_stats", {})
                        current_s = detail.get("current_stats", {})
                        
                        st.write(f"**Analyzing: {selected_drift_feat}** — Drift Score: **{detail['drift_score']:.3f}** ({detail['drift_type']})")
                        
                        if baseline_s.get("type") == "FLOAT":
                            col_bs, col_cs = st.columns(2)
                            with col_bs:
                                st.write("**Baseline Statistics**")
                                st.json({k: v for k, v in baseline_s.items() if k != "type"})
                            with col_cs:
                                st.write("**Current Statistics**")
                                st.json({k: v for k, v in current_s.items() if k != "type"})
                            
                            # Comparison bar chart
                            compare_metrics = ["mean", "std_dev", "min", "max", "median"]
                            b_vals = [baseline_s.get(m, 0) for m in compare_metrics]
                            c_vals = [current_s.get(m, 0) for m in compare_metrics]
                            fig_comp = go.Figure(data=[
                                go.Bar(name="Baseline", x=compare_metrics, y=b_vals),
                                go.Bar(name="Current", x=compare_metrics, y=c_vals),
                            ])
                            fig_comp.update_layout(barmode="group", title=f"{selected_drift_feat}: Baseline vs Current")
                            st.plotly_chart(fig_comp, use_container_width=True)
                        else:
                            col_bs, col_cs = st.columns(2)
                            with col_bs:
                                st.write("**Baseline Distribution**")
                                top_vals = baseline_s.get("top_values", [])
                                if top_vals:
                                    bdf = pd.DataFrame(top_vals)
                                    fig_b = px.bar(bdf, x="value", y="frequency", title="Baseline")
                                    st.plotly_chart(fig_b, use_container_width=True)
                            with col_cs:
                                st.write("**Current Distribution**")
                                top_vals_c = current_s.get("top_values", [])
                                if top_vals_c:
                                    cdf = pd.DataFrame(top_vals_c)
                                    fig_c = px.bar(cdf, x="value", y="frequency", title="Current")
                                    st.plotly_chart(fig_c, use_container_width=True)
                
                with drift_tab3:
                    st.subheader("Alerts & Actions")
                    
                    drifted_feats = [f for f in drift_features if drift_details[f]["is_drifted"]]
                    if drifted_feats:
                        st.error(f"⚠️ Drift detected in {len(drifted_feats)} feature(s)!")
                        st.write(f"**Drifted features:** {', '.join(drifted_feats)}")
                    else:
                        st.success("✅ All features within acceptable drift thresholds")
                    
                    st.write("**Recommendations:**")
                    for rec in drift_recs:
                        st.write(f"- {rec}")
                    
                    col_action1, col_action2 = st.columns(2)
                    with col_action1:
                        if st.button("🔄 Refresh Drift Analysis"):
                            st.rerun()
                    with col_action2:
                        report_md = f"# Data Drift Report\n\n**Generated:** {datetime.now().isoformat()}\n\n"
                        report_md += f"**Total Features:** {drift_summary.get('total_features_checked', 0)}\n"
                        report_md += f"**Drifted Features:** {drift_summary.get('drifted_features_count', 0)}\n\n"
                        for f, d in drift_details.items():
                            report_md += f"## {f}\n- Score: {d['drift_score']}\n- Type: {d['drift_type']}\n- Drifted: {d['is_drifted']}\n\n"
                        st.download_button(
                            label="📥 Download Drift Report",
                            data=report_md,
                            file_name=f"drift_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.md",
                            mime="text/markdown"
                        )
            else:
                st.error(f"Failed to load drift data: HTTP {drift_resp.status_code}")
        except Exception as e:
            st.error(f"Failed to load drift monitoring: {str(e)}")
            st.info("Please ensure FastAPI service is running")
    
    # Tab 6: Feast feature store
    with tab6:
        try:
            feast_ui.render_feast_dashboard()
        except Exception as e:
            st.error(f"Feast feature store interface failed to load: {str(e)}")
            st.info("Please ensure Feast service and Redis are running")
    
    # Tab 7: Kafka stream processing
    with tab7:
        try:
            kafka_ui.render_kafka_dashboard()
        except Exception as e:
            st.error(f"Kafka stream processing interface failed to load: {str(e)}")
            st.info("Please ensure Kafka service is running")
    
    # Tab 8: MLflow model registry
    with tab8:
        try:
            mlflow_ui.render_mlflow_dashboard()
        except Exception as e:
            st.error(f"MLflow model registry interface failed to load: {str(e)}")
            st.info("Please ensure MLflow service is running")
    
    # Tab 9: MLMD data lineage
    with tab9:
        try:
            mlmd_ui = get_mlmd_ui_integration(API_BASE_URL)
            mlmd_ui.render_mlmd_interface()
        except Exception as e:
            st.error(f"MLMD data lineage interface failed to load: {str(e)}")
            st.info("Please ensure MLMD components and FastAPI service are running")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: gray;'>
        🚕 Chicago Taxi MLOps Platform v1.0.0 | Based on TFX Pipeline + Kubeflow + KFServing + Streamlit<br>
        💡 Tip: Ensure FastAPI service (localhost:8000) and TFX Pipeline are running<br>
        📊 Data Source: Chicago Taxi Trips Dataset | 🎯 Prediction Target: Tip Amount (Tips)
    </div>
    """, unsafe_allow_html=True)

def render_data_drift_monitoring():
    """Render data drift monitoring interface"""
    st.header("🔍 Data Drift Monitoring")
    
    # Initialize drift monitoring UI
    drift_ui = DriftMonitorUI()
    
    # Load data
    if drift_ui.load_drift_results():
        
        # Control panel
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.subheader("📊 Drift Monitoring Overview")
        
        with col2:
            if st.button("🔄 Refresh Data", key="refresh_drift"):
                drift_ui.load_drift_results()
                st.rerun()
        
        with col3:
            auto_refresh = st.checkbox("Auto Refresh", key="auto_refresh_drift")
        
        # Auto refresh logic
        if auto_refresh:
            time.sleep(10)  # Refresh every 10 seconds
            st.rerun()
        
        # Drift overview
        drift_ui.render_drift_overview()
        
        st.divider()
        
        # Create sub-tabs
        drift_tab1, drift_tab2, drift_tab3, drift_tab4, drift_tab5 = st.tabs([
            "📈 Feature Drift Charts", "🔥 Drift Heatmap", "🔍 Feature Detail Analysis", "📅 Historical Trends", "💡 Recommendations & Reports"
        ])
        
        with drift_tab1:
            st.subheader("Feature Drift Score Distribution")
            drift_ui.render_feature_drift_chart()
        
        with drift_tab2:
            st.subheader("Feature Drift Heatmap")
            drift_ui.render_drift_heatmap()
        
        with drift_tab3:
            st.subheader("Feature Detail Analysis")
            
            # Feature selection
            if drift_ui.drift_data:
                features = list(drift_ui.drift_data['feature_details'].keys())
                selected_feature = st.selectbox(
                    "Select feature to analyze:",
                    features,
                    key="feature_selector"
                )
                
                if selected_feature:
                    drift_ui.render_feature_comparison(selected_feature)
        
        with drift_tab4:
            st.subheader("Data Drift Historical Trends")
            drift_ui.render_drift_timeline()
            
            # Add explanation
            st.info("📝 Note: This is a historical trend chart based on simulated data. In actual deployment, this will display real historical drift data.")
        
        with drift_tab5:
            st.subheader("Recommendations & Reports")
            
            # Display recommendations
            drift_ui.render_recommendations()
            
            st.divider()
            
            # Export report
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Generate Detailed Report", key="generate_report"):
                    report = drift_ui.export_drift_report()
                    st.download_button(
                        label="📥 Download Report",
                        data=report,
                        file_name=f"drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
            
            with col2:
                if st.button("🚨 Trigger Alert", key="trigger_alert"):
                    if drift_ui.drift_data and drift_ui.drift_data['summary']['overall_drift_detected']:
                        st.error("⚠️ Data drift alert triggered! Recommend immediate data quality check.")
                        
                        # Display alert details
                        with st.expander("Alert Details"):
                            drifted_features = [
                                name for name, details in drift_ui.drift_data['feature_details'].items()
                                if details['is_drifted']
                            ]
                            st.write(f"**Drifted Features:** {', '.join(drifted_features)}")
                            st.write(f"**Number of Drifted Features:** {len(drifted_features)}")
                            st.write(f"**Recommended Actions:** Check data collection process, consider retraining model")
                    else:
                        st.success("✅ Current data quality is good, no alert needed.")
        
        # Add technical explanation
        with st.expander("🔧 Technical Documentation"):
            st.markdown("""
            ### Data Drift Monitoring Technical Documentation
            
            **Drift Detection Algorithms:**
            - **Numerical Features**: Detection based on mean and standard deviation changes
            - **Categorical Features**: Distribution comparison using Jensen-Shannon divergence
            
            **Drift Classification:**
            - 🟢 **No Drift** (< 0.1): Stable data distribution
            - 🟡 **Slight Drift** (0.1 - 0.3): Minor changes, requires attention
            - 🟠 **Moderate Drift** (0.3 - 0.5): Significant changes, investigation recommended
            - 🔴 **Severe Drift** (> 0.5): Critical changes, immediate action required
            
            **Monitoring Frequency Recommendations:**
            - Real-time monitoring: Hourly checks
            - Daily monitoring: Daily checks
            - Periodic review: Weekly in-depth analysis
            
            **Integration Notes:**
            - This interface displays simulated data
            - In actual deployment, will connect to TFX Pipeline drift monitoring components
            - Supports Prometheus metrics export and Grafana visualization
            """)
    
    else:
        st.error("Unable to load data drift results. Please ensure data drift monitoring components are running.")
        
        # Provide manual trigger option
        if st.button("🔄 Manually Trigger Drift Detection", key="manual_trigger"):
            with st.spinner("Executing data drift detection..."):
                time.sleep(3)  # Simulate detection process
                st.success("✅ Data drift detection completed! Please refresh the page to view results.")
                st.info("💡 Tip: In actual deployment, this will trigger the data drift monitoring component in TFX Pipeline.")


if __name__ == "__main__":
    main()
