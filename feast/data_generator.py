#!/usr/bin/env python3
"""
Feast 特征数据生成器
为 Chicago Taxi 特征存储生成训练和测试数据
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging


class FeastDataGenerator:
    """Feast 特征数据生成器"""
    
    def __init__(self, output_dir: str = "data/offline_store"):
        """
        初始化数据生成器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 芝加哥社区区域映射
        self.community_areas = {
            1: "Rogers Park", 8: "Near North Side", 32: "Loop",
            76: "O'Hare", 77: "Edgewater", 6: "Lake View"
        }
        
        # 出租车公司列表
        self.companies = [
            "Flash Cab", "Taxi Affiliation Services", "Yellow Cab",
            "Blue Diamond", "Chicago Carriage Cab Corp", "City Service"
        ]
    
    def generate_trip_features(self, num_trips: int = 10000) -> pd.DataFrame:
        """
        生成行程基础特征数据
        
        Args:
            num_trips: 生成的行程数量
            
        Returns:
            行程特征 DataFrame
        """
        self.logger.info(f"生成 {num_trips} 个行程特征...")
        
        # 生成时间序列（过去30天）
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        
        # 生成随机时间戳
        timestamps = pd.date_range(start_time, end_time, periods=num_trips)
        
        # 生成行程数据
        data = {
            "trip_id": [f"trip_{i:06d}" for i in range(num_trips)],
            "event_timestamp": timestamps,
            "created_timestamp": [datetime.now()] * num_trips,
            
            # 基础特征
            "trip_miles": np.random.exponential(3.0, num_trips),
            "trip_seconds": np.random.exponential(900, num_trips).astype(int),
            "fare": np.random.exponential(12.0, num_trips),
            
            # 地理位置（芝加哥市区）
            "pickup_latitude": np.random.normal(41.88, 0.05, num_trips),
            "pickup_longitude": np.random.normal(-87.63, 0.05, num_trips),
            "dropoff_latitude": np.random.normal(41.89, 0.05, num_trips),
            "dropoff_longitude": np.random.normal(-87.62, 0.05, num_trips),
            
            # 时间特征
            "pickup_hour": [ts.hour for ts in timestamps],
            "pickup_day_of_week": [ts.weekday() for ts in timestamps],
            "pickup_month": [ts.month for ts in timestamps],
            
            # 其他特征
            "passenger_count": np.random.randint(1, 5, num_trips),
            "payment_type": np.random.choice(
                ["Credit Card", "Cash", "No Charge", "Dispute"], 
                num_trips, p=[0.7, 0.25, 0.03, 0.02]
            ),
            "company": np.random.choice(self.companies, num_trips),
        }
        
        df = pd.DataFrame(data)
        
        # 数据清理和约束
        df["trip_miles"] = np.clip(df["trip_miles"], 0.1, 50.0)
        df["trip_seconds"] = np.clip(df["trip_seconds"], 60, 7200)
        df["fare"] = np.clip(df["fare"], 2.5, 100.0)
        df["passenger_count"] = np.clip(df["passenger_count"], 1, 6)
        
        return df
    
    def generate_area_features(self, num_areas: int = 100) -> pd.DataFrame:
        """
        生成区域聚合特征数据
        
        Args:
            num_areas: 区域数量
            
        Returns:
            区域特征 DataFrame
        """
        self.logger.info(f"生成 {num_areas} 个区域特征...")
        
        # 生成时间序列（每小时一个数据点，过去7天）
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        timestamps = pd.date_range(start_time, end_time, freq='H')
        
        data = []
        for area_id in range(1, num_areas + 1):
            for timestamp in timestamps:
                # 基于时间和区域生成不同的模式
                hour = timestamp.hour
                is_weekend = timestamp.weekday() >= 5
                
                # 高峰时段调整
                peak_multiplier = 1.5 if hour in [7, 8, 17, 18, 19] else 1.0
                weekend_multiplier = 0.8 if is_weekend else 1.0
                
                base_trips = np.random.poisson(20) * peak_multiplier * weekend_multiplier
                
                data.append({
                    "area_id": area_id,
                    "event_timestamp": timestamp,
                    "created_timestamp": datetime.now(),
                    
                    "avg_trip_distance": np.random.normal(3.5, 1.0),
                    "avg_trip_duration": np.random.normal(900, 300),
                    "avg_fare": np.random.normal(12.0, 3.0),
                    "trip_count_1h": max(1, int(base_trips)),
                    "trip_count_24h": max(24, int(base_trips * 24 * np.random.uniform(0.8, 1.2))),
                    "pickup_density": np.random.exponential(0.5),
                    "dropoff_density": np.random.exponential(0.5),
                })
        
        df = pd.DataFrame(data)
        
        # 数据清理
        df["avg_trip_distance"] = np.clip(df["avg_trip_distance"], 0.5, 20.0)
        df["avg_trip_duration"] = np.clip(df["avg_trip_duration"], 300, 3600)
        df["avg_fare"] = np.clip(df["avg_fare"], 5.0, 50.0)
        
        return df
    
    def generate_company_features(self) -> pd.DataFrame:
        """
        生成公司统计特征数据
        
        Returns:
            公司特征 DataFrame
        """
        self.logger.info(f"生成 {len(self.companies)} 个公司特征...")
        
        # 生成时间序列（每天一个数据点，过去30天）
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        timestamps = pd.date_range(start_time, end_time, freq='D')
        
        data = []
        for company in self.companies:
            # 为每个公司生成基础统计
            base_fare = np.random.normal(12.0, 2.0)
            base_rating = np.random.normal(4.2, 0.3)
            base_drivers = np.random.randint(50, 500)
            
            for timestamp in timestamps:
                # 添加时间变化
                daily_variation = np.random.normal(1.0, 0.1)
                
                data.append({
                    "company_id": company,
                    "event_timestamp": timestamp,
                    "created_timestamp": datetime.now(),
                    
                    "company_avg_fare": max(5.0, base_fare * daily_variation),
                    "company_trip_count": max(10, int(np.random.poisson(100) * daily_variation)),
                    "company_rating": np.clip(base_rating + np.random.normal(0, 0.1), 1.0, 5.0),
                    "company_active_drivers": max(10, int(base_drivers * daily_variation)),
                })
        
        return pd.DataFrame(data)
    
    def generate_all_features(self, num_trips: int = 10000):
        """
        生成所有特征数据并保存
        
        Args:
            num_trips: 行程数量
        """
        self.logger.info("开始生成所有特征数据...")
        
        # 1. 生成行程特征
        trip_df = self.generate_trip_features(num_trips)
        trip_path = self.output_dir / "trip_features.parquet"
        trip_df.to_parquet(trip_path, index=False)
        self.logger.info(f"行程特征已保存到: {trip_path}")
        
        # 2. 生成区域特征
        area_df = self.generate_area_features()
        area_path = self.output_dir / "area_features.parquet"
        area_df.to_parquet(area_path, index=False)
        self.logger.info(f"区域特征已保存到: {area_path}")
        
        # 3. 生成公司特征
        company_df = self.generate_company_features()
        company_path = self.output_dir / "company_features.parquet"
        company_df.to_parquet(company_path, index=False)
        self.logger.info(f"公司特征已保存到: {company_path}")
        
        # 4. 生成特征摘要
        self.generate_feature_summary(trip_df, area_df, company_df)
        
        self.logger.info("所有特征数据生成完成！")
    
    def generate_feature_summary(self, trip_df: pd.DataFrame, 
                                area_df: pd.DataFrame, 
                                company_df: pd.DataFrame):
        """
        生成特征数据摘要
        
        Args:
            trip_df: 行程特征数据
            area_df: 区域特征数据  
            company_df: 公司特征数据
        """
        summary = {
            "generation_time": datetime.now().isoformat(),
            "datasets": {
                "trip_features": {
                    "rows": len(trip_df),
                    "columns": len(trip_df.columns),
                    "time_range": {
                        "start": trip_df["event_timestamp"].min().isoformat(),
                        "end": trip_df["event_timestamp"].max().isoformat()
                    },
                    "features": list(trip_df.columns)
                },
                "area_features": {
                    "rows": len(area_df),
                    "columns": len(area_df.columns),
                    "unique_areas": area_df["area_id"].nunique(),
                    "features": list(area_df.columns)
                },
                "company_features": {
                    "rows": len(company_df),
                    "columns": len(company_df.columns),
                    "unique_companies": company_df["company_id"].nunique(),
                    "features": list(company_df.columns)
                }
            }
        }
        
        import json
        summary_path = self.output_dir / "feature_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info(f"特征摘要已保存到: {summary_path}")


def main():
    """主函数"""
    generator = FeastDataGenerator()
    generator.generate_all_features(num_trips=5000)


if __name__ == "__main__":
    main()
