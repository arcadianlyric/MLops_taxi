#!/usr/bin/env python3
"""
Feast 特征存储集成管道
独立于 TFX Pipeline 运行，符合业界最佳实践
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import yaml
import json
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from feast import FeatureStore
    from feast.infra.offline_stores.file_source import SavedDatasetFileStorage
    FEAST_AVAILABLE = True
except ImportError:
    FEAST_AVAILABLE = False
    logging.warning("Feast 未安装，使用模拟模式")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis 未安装，使用模拟模式")


class FeastIntegrationPipeline:
    """
    Feast 特征存储集成管道
    
    独立运行的特征工程和存储管道，从 TFX 输出读取数据，
    处理特征并推送到 Feast 特征存储
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化 Feast 集成管道
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or "feast/integration_config.yaml"
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化 Feast 存储
        self.feast_store = None
        self.redis_client = None
        
        if FEAST_AVAILABLE:
            self._initialize_feast_store()
        
        if REDIS_AVAILABLE:
            self._initialize_redis_client()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            else:
                return self._get_default_config()
        except Exception as e:
            self.logger.warning(f"加载配置失败，使用默认配置: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "feast": {
                "repo_path": "feast/",
                "online_store": {
                    "type": "redis",
                    "connection_string": "redis://localhost:6379"
                },
                "offline_store": {
                    "type": "file",
                    "path": "feast/data/"
                }
            },
            "data_sources": {
                "tfx_output_path": "tfx_pipeline/output/",
                "raw_data_path": "data/",
                "processed_data_path": "feast/data/"
            },
            "feature_processing": {
                "batch_size": 1000,
                "window_size": "7d",
                "aggregation_functions": ["mean", "sum", "count", "std"]
            },
            "scheduling": {
                "feature_refresh_interval": "1h",
                "materialization_interval": "6h"
            }
        }
    
    def _initialize_feast_store(self):
        """初始化 Feast 特征存储"""
        try:
            feast_repo_path = self.config["feast"]["repo_path"]
            if os.path.exists(feast_repo_path):
                self.feast_store = FeatureStore(repo_path=feast_repo_path)
                self.logger.info("Feast 特征存储初始化成功")
            else:
                self.logger.warning(f"Feast 仓库路径不存在: {feast_repo_path}")
        except Exception as e:
            self.logger.error(f"Feast 特征存储初始化失败: {e}")
    
    def _initialize_redis_client(self):
        """初始化 Redis 客户端"""
        try:
            redis_config = self.config["feast"]["online_store"]
            if redis_config["type"] == "redis":
                connection_string = redis_config["connection_string"]
                # 解析连接字符串
                if connection_string.startswith("redis://"):
                    host_port = connection_string.replace("redis://", "").split(":")
                    host = host_port[0]
                    port = int(host_port[1]) if len(host_port) > 1 else 6379
                    
                    self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
                    # 测试连接
                    self.redis_client.ping()
                    self.logger.info("Redis 客户端连接成功")
        except Exception as e:
            self.logger.warning(f"Redis 客户端连接失败: {e}")
    
    def extract_features_from_tfx(self, tfx_output_path: str = None) -> pd.DataFrame:
        """
        从 TFX Pipeline 输出提取特征数据
        
        Args:
            tfx_output_path: TFX 输出路径
            
        Returns:
            提取的特征数据
        """
        tfx_path = tfx_output_path or self.config["data_sources"]["tfx_output_path"]
        
        try:
            # 查找 TFX Transform 组件的输出
            transform_output_path = os.path.join(tfx_path, "Transform")
            
            if os.path.exists(transform_output_path):
                # 查找最新的输出
                latest_output = self._find_latest_tfx_output(transform_output_path)
                
                if latest_output:
                    # 读取转换后的数据
                    return self._read_tfx_transformed_data(latest_output)
            
            # 如果没有 TFX 输出，生成模拟数据
            self.logger.warning("未找到 TFX 输出，生成模拟特征数据")
            return self._generate_mock_feature_data()
            
        except Exception as e:
            self.logger.error(f"从 TFX 提取特征失败: {e}")
            return self._generate_mock_feature_data()
    
    def _find_latest_tfx_output(self, transform_path: str) -> Optional[str]:
        """查找最新的 TFX 输出"""
        try:
            if not os.path.exists(transform_path):
                return None
            
            # 查找最新的执行目录
            execution_dirs = [d for d in os.listdir(transform_path) 
                            if os.path.isdir(os.path.join(transform_path, d))]
            
            if not execution_dirs:
                return None
            
            # 按时间排序，获取最新的
            execution_dirs.sort(reverse=True)
            latest_dir = os.path.join(transform_path, execution_dirs[0])
            
            # 查找转换后的数据文件
            for root, dirs, files in os.walk(latest_dir):
                for file in files:
                    if file.endswith('.parquet') or file.endswith('.csv'):
                        return os.path.join(root, file)
            
            return None
            
        except Exception as e:
            self.logger.error(f"查找 TFX 输出失败: {e}")
            return None
    
    def _read_tfx_transformed_data(self, file_path: str) -> pd.DataFrame:
        """读取 TFX 转换后的数据"""
        try:
            if file_path.endswith('.parquet'):
                return pd.read_parquet(file_path)
            elif file_path.endswith('.csv'):
                return pd.read_csv(file_path)
            else:
                raise ValueError(f"不支持的文件格式: {file_path}")
        except Exception as e:
            self.logger.error(f"读取 TFX 数据失败: {e}")
            return self._generate_mock_feature_data()
    
    def _generate_mock_feature_data(self) -> pd.DataFrame:
        """生成模拟特征数据"""
        np.random.seed(42)
        n_samples = 1000
        
        # 生成时间序列
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        timestamps = pd.date_range(start=start_time, end=end_time, periods=n_samples)
        
        # 生成特征数据
        data = {
            'trip_id': [f'trip_{i:06d}' for i in range(n_samples)],
            'event_timestamp': timestamps,
            'pickup_location_id': np.random.randint(1, 265, n_samples),
            'dropoff_location_id': np.random.randint(1, 265, n_samples),
            'company_id': np.random.randint(1, 50, n_samples),
            
            # 行程特征
            'trip_distance': np.random.exponential(3.0, n_samples),
            'trip_duration': np.random.exponential(900, n_samples),  # 秒
            'passenger_count': np.random.randint(1, 5, n_samples),
            'fare_amount': np.random.exponential(12.0, n_samples),
            
            # 时间特征
            'hour_of_day': [ts.hour for ts in timestamps],
            'day_of_week': [ts.dayofweek for ts in timestamps],
            'month': [ts.month for ts in timestamps],
            'is_weekend': [ts.dayofweek >= 5 for ts in timestamps],
            
            # 聚合特征（模拟）
            'pickup_area_avg_fare_7d': np.random.uniform(8, 25, n_samples),
            'pickup_area_trip_count_7d': np.random.randint(50, 500, n_samples),
            'company_avg_fare_7d': np.random.uniform(10, 20, n_samples),
            'company_trip_count_7d': np.random.randint(100, 1000, n_samples),
        }
        
        return pd.DataFrame(data)
    
    def process_features(self, raw_data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        处理特征数据，分离不同的特征视图
        
        Args:
            raw_data: 原始特征数据
            
        Returns:
            按特征视图分组的数据字典
        """
        processed_features = {}
        
        try:
            # 1. 行程特征
            trip_features = raw_data[[
                'trip_id', 'event_timestamp', 'trip_distance', 'trip_duration',
                'passenger_count', 'fare_amount', 'pickup_location_id', 'dropoff_location_id'
            ]].copy()
            
            # 添加派生特征
            trip_features['fare_per_mile'] = trip_features['fare_amount'] / (trip_features['trip_distance'] + 0.1)
            trip_features['fare_per_minute'] = trip_features['fare_amount'] / (trip_features['trip_duration'] / 60 + 0.1)
            
            processed_features['trip_features'] = trip_features
            
            # 2. 区域特征
            area_features = raw_data.groupby(['pickup_location_id', 'event_timestamp']).agg({
                'fare_amount': ['mean', 'count', 'std'],
                'trip_distance': ['mean', 'count'],
                'trip_duration': ['mean']
            }).reset_index()
            
            # 扁平化列名
            area_features.columns = ['pickup_location_id', 'event_timestamp'] + [
                f'pickup_area_{col[1]}_{col[0]}' if col[1] else f'pickup_area_{col[0]}'
                for col in area_features.columns[2:]
            ]
            
            processed_features['area_features'] = area_features
            
            # 3. 公司特征
            company_features = raw_data.groupby(['company_id', 'event_timestamp']).agg({
                'fare_amount': ['mean', 'count', 'std'],
                'trip_distance': ['mean', 'count'],
                'passenger_count': ['mean']
            }).reset_index()
            
            # 扁平化列名
            company_features.columns = ['company_id', 'event_timestamp'] + [
                f'company_{col[1]}_{col[0]}' if col[1] else f'company_{col[0]}'
                for col in company_features.columns[2:]
            ]
            
            processed_features['company_features'] = company_features
            
            # 4. 时间特征
            time_features = raw_data[[
                'trip_id', 'event_timestamp', 'hour_of_day', 'day_of_week',
                'month', 'is_weekend'
            ]].copy()
            
            # 添加时间段特征
            time_features['time_period'] = pd.cut(
                time_features['hour_of_day'],
                bins=[0, 6, 12, 18, 24],
                labels=['night', 'morning', 'afternoon', 'evening'],
                include_lowest=True
            )
            
            processed_features['time_features'] = time_features
            
            self.logger.info(f"特征处理完成，生成 {len(processed_features)} 个特征视图")
            
        except Exception as e:
            self.logger.error(f"特征处理失败: {e}")
        
        return processed_features
    
    def push_to_feast(self, processed_features: Dict[str, pd.DataFrame]) -> bool:
        """
        将处理后的特征推送到 Feast
        
        Args:
            processed_features: 处理后的特征数据
            
        Returns:
            是否成功
        """
        if not FEAST_AVAILABLE or not self.feast_store:
            self.logger.warning("Feast 不可用，使用模拟模式")
            return self._mock_push_to_feast(processed_features)
        
        try:
            success_count = 0
            
            for feature_view_name, data in processed_features.items():
                try:
                    # 保存到离线存储
                    output_path = os.path.join(
                        self.config["data_sources"]["processed_data_path"],
                        f"{feature_view_name}.parquet"
                    )
                    
                    # 确保目录存在
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # 保存数据
                    data.to_parquet(output_path, index=False)
                    
                    self.logger.info(f"特征视图 {feature_view_name} 保存到: {output_path}")
                    success_count += 1
                    
                except Exception as e:
                    self.logger.error(f"保存特征视图 {feature_view_name} 失败: {e}")
            
            # 物化到在线存储
            if success_count > 0:
                self._materialize_to_online_store()
            
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"推送到 Feast 失败: {e}")
            return False
    
    def _mock_push_to_feast(self, processed_features: Dict[str, pd.DataFrame]) -> bool:
        """模拟推送到 Feast"""
        try:
            for feature_view_name, data in processed_features.items():
                output_path = os.path.join(
                    "feast/data",
                    f"{feature_view_name}.parquet"
                )
                
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                data.to_parquet(output_path, index=False)
                
                self.logger.info(f"模拟模式：特征视图 {feature_view_name} 保存到 {output_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"模拟推送失败: {e}")
            return False
    
    def _materialize_to_online_store(self):
        """物化特征到在线存储"""
        try:
            if not self.feast_store:
                return
            
            # 获取当前时间
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)  # 物化最近1天的数据
            
            # 物化所有特征视图
            self.feast_store.materialize(start_time, end_time)
            
            self.logger.info("特征物化到在线存储完成")
            
        except Exception as e:
            self.logger.warning(f"物化到在线存储失败: {e}")
    
    def run_pipeline(self) -> bool:
        """
        运行完整的 Feast 集成管道
        
        Returns:
            是否成功
        """
        self.logger.info("开始运行 Feast 集成管道")
        
        try:
            # 1. 从 TFX 提取特征
            self.logger.info("步骤 1: 从 TFX 提取特征数据")
            raw_data = self.extract_features_from_tfx()
            
            if raw_data.empty:
                self.logger.error("未提取到特征数据")
                return False
            
            self.logger.info(f"提取到 {len(raw_data)} 条特征记录")
            
            # 2. 处理特征
            self.logger.info("步骤 2: 处理特征数据")
            processed_features = self.process_features(raw_data)
            
            if not processed_features:
                self.logger.error("特征处理失败")
                return False
            
            # 3. 推送到 Feast
            self.logger.info("步骤 3: 推送特征到 Feast")
            success = self.push_to_feast(processed_features)
            
            if success:
                self.logger.info("Feast 集成管道运行成功")
                return True
            else:
                self.logger.error("推送到 Feast 失败")
                return False
                
        except Exception as e:
            self.logger.error(f"Feast 集成管道运行失败: {e}")
            return False
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取管道状态"""
        return {
            "feast_available": FEAST_AVAILABLE,
            "feast_store_initialized": self.feast_store is not None,
            "redis_available": REDIS_AVAILABLE,
            "redis_connected": self.redis_client is not None,
            "config_loaded": self.config is not None,
            "last_run": datetime.now().isoformat()
        }


def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建并运行管道
    pipeline = FeastIntegrationPipeline()
    
    # 显示状态
    status = pipeline.get_pipeline_status()
    print("Feast 集成管道状态:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # 运行管道
    success = pipeline.run_pipeline()
    
    if success:
        print("✅ Feast 集成管道运行成功")
        return 0
    else:
        print("❌ Feast 集成管道运行失败")
        return 1


if __name__ == "__main__":
    exit(main())
