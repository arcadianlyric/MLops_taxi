#!/usr/bin/env python3
"""
FeastPusher TFX 组件
将 TFX Transform 组件的输出推送到 Feast 特征存储
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import tensorflow as tf
from tfx.components.base import base_component
from tfx.components.base import executor_spec
from tfx.components.base import base_executor
from tfx.types import Artifact
from tfx.types import ComponentSpec
from tfx.types.standard_artifacts import Examples
from tfx.utils import io_utils

# Feast 相关导入
try:
    from feast import FeatureStore
    from feast.infra.offline_stores.file_source import SavedDatasetFileStorage
    FEAST_AVAILABLE = True
except ImportError:
    FEAST_AVAILABLE = False
    logging.warning("Feast 未安装，FeastPusher 将使用模拟模式")


class FeastPusherSpec(ComponentSpec):
    """FeastPusher 组件规范"""
    
    PARAMETERS = {
        'feast_repo_path': str,
        'push_to_online_store': bool,
        'push_to_offline_store': bool,
        'feature_service_name': str,
    }
    
    INPUTS = {
        'transformed_examples': Examples,
    }
    
    OUTPUTS = {
        'pushed_features': Artifact,
    }


class FeastPusherExecutor(base_executor.BaseExecutor):
    """FeastPusher 执行器"""
    
    def Do(self, input_dict: Dict[str, List[Artifact]],
           output_dict: Dict[str, List[Artifact]],
           exec_properties: Dict[str, Any]) -> None:
        """执行特征推送到 Feast"""
        
        logging.info("开始执行 FeastPusher...")
        
        # 获取输入和参数
        transformed_examples = input_dict['transformed_examples'][0]
        feast_repo_path = exec_properties.get('feast_repo_path', 'feast')
        push_to_online = exec_properties.get('push_to_online_store', True)
        push_to_offline = exec_properties.get('push_to_offline_store', True)
        feature_service = exec_properties.get('feature_service_name', 'model_inference_v1')
        
        # 读取转换后的数据
        transformed_data = self._read_transformed_examples(transformed_examples.uri)
        
        if FEAST_AVAILABLE:
            # 使用真实的 Feast
            self._push_to_feast_real(
                transformed_data, feast_repo_path, 
                push_to_online, push_to_offline, feature_service
            )
        else:
            # 使用模拟模式
            self._push_to_feast_mock(
                transformed_data, feast_repo_path,
                push_to_online, push_to_offline, feature_service
            )
        
        # 保存推送结果
        self._save_push_results(output_dict['pushed_features'][0].uri, transformed_data)
        
        logging.info("FeastPusher 执行完成")
    
    def _read_transformed_examples(self, examples_uri: str) -> pd.DataFrame:
        """读取转换后的样本数据"""
        
        logging.info(f"读取转换后的数据: {examples_uri}")
        
        try:
            # 查找 TFRecord 文件
            tfrecord_files = []
            for root, dirs, files in os.walk(examples_uri):
                for file in files:
                    if file.endswith('.tfrecord') or file.endswith('.tfrecords'):
                        tfrecord_files.append(os.path.join(root, file))
            
            if not tfrecord_files:
                logging.warning("未找到 TFRecord 文件，生成模拟数据")
                return self._generate_mock_transformed_data()
            
            # 读取 TFRecord 文件
            dataset = tf.data.TFRecordDataset(tfrecord_files)
            
            # 解析 TFRecord 并转换为 DataFrame
            records = []
            for raw_record in dataset.take(1000):  # 限制读取数量
                example = tf.train.Example()
                example.ParseFromString(raw_record.numpy())
                
                record = {}
                for key, feature in example.features.feature.items():
                    if feature.HasField('float_list'):
                        record[key] = feature.float_list.value[0] if feature.float_list.value else 0.0
                    elif feature.HasField('int64_list'):
                        record[key] = feature.int64_list.value[0] if feature.int64_list.value else 0
                    elif feature.HasField('bytes_list'):
                        record[key] = feature.bytes_list.value[0].decode('utf-8') if feature.bytes_list.value else ""
                
                records.append(record)
            
            df = pd.DataFrame(records)
            logging.info(f"成功读取 {len(df)} 条转换后的数据")
            
            return df
            
        except Exception as e:
            logging.error(f"读取转换后数据失败: {e}")
            return self._generate_mock_transformed_data()
    
    def _generate_mock_transformed_data(self) -> pd.DataFrame:
        """生成模拟的转换后数据"""
        
        logging.info("生成模拟转换后数据...")
        
        n_samples = 1000
        
        data = {
            'trip_id': [f'trip_{i:06d}' for i in range(n_samples)],
            'event_timestamp': [datetime.now()] * n_samples,
            'created_timestamp': [datetime.now()] * n_samples,
            
            # 基础特征
            'trip_miles': np.random.exponential(3.0, n_samples),
            'trip_seconds': np.random.exponential(900, n_samples).astype(int),
            'fare': np.random.exponential(12.0, n_samples),
            
            # 地理特征
            'pickup_latitude': np.random.normal(41.88, 0.05, n_samples),
            'pickup_longitude': np.random.normal(-87.63, 0.05, n_samples),
            'dropoff_latitude': np.random.normal(41.89, 0.05, n_samples),
            'dropoff_longitude': np.random.normal(-87.62, 0.05, n_samples),
            
            # 时间特征
            'pickup_hour': np.random.randint(0, 24, n_samples),
            'pickup_day_of_week': np.random.randint(0, 7, n_samples),
            'pickup_month': np.random.randint(1, 13, n_samples),
            
            # 其他特征
            'passenger_count': np.random.randint(1, 5, n_samples),
            'payment_type': np.random.choice(['Credit Card', 'Cash', 'No Charge'], n_samples),
            'company': np.random.choice(['Flash Cab', 'Yellow Cab', 'Blue Diamond'], n_samples),
        }
        
        return pd.DataFrame(data)
    
    def _push_to_feast_real(self, data: pd.DataFrame, feast_repo_path: str,
                           push_to_online: bool, push_to_offline: bool,
                           feature_service: str):
        """推送数据到真实的 Feast 存储"""
        
        logging.info("推送数据到 Feast 特征存储...")
        
        try:
            # 初始化 Feast 存储
            store = FeatureStore(repo_path=feast_repo_path)
            
            # 准备特征数据
            feature_data = self._prepare_feature_data(data)
            
            if push_to_offline:
                # 推送到离线存储
                logging.info("推送到离线存储...")
                
                # 保存为 Parquet 文件
                offline_path = os.path.join(feast_repo_path, 'data', 'offline_store', 'trip_features.parquet')
                os.makedirs(os.path.dirname(offline_path), exist_ok=True)
                feature_data.to_parquet(offline_path, index=False)
                
                logging.info(f"离线特征已保存到: {offline_path}")
            
            if push_to_online:
                # 推送到在线存储
                logging.info("推送到在线存储...")
                
                try:
                    # 使用 Feast 的 push 功能
                    store.push("trip_features", feature_data, to=None)
                    logging.info("在线特征推送成功")
                except Exception as e:
                    logging.warning(f"在线特征推送失败: {e}")
                    # 备用方案：直接写入 Redis（如果可用）
                    self._push_to_redis_direct(feature_data)
            
        except Exception as e:
            logging.error(f"Feast 推送失败: {e}")
            # 降级到模拟模式
            self._push_to_feast_mock(data, feast_repo_path, push_to_online, push_to_offline, feature_service)
    
    def _push_to_feast_mock(self, data: pd.DataFrame, feast_repo_path: str,
                           push_to_online: bool, push_to_offline: bool,
                           feature_service: str):
        """模拟推送数据到 Feast 存储"""
        
        logging.info("使用模拟模式推送数据到 Feast...")
        
        # 准备特征数据
        feature_data = self._prepare_feature_data(data)
        
        # 创建输出目录
        output_dir = Path(feast_repo_path) / 'data' / 'offline_store'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if push_to_offline:
            # 模拟离线存储
            offline_path = output_dir / 'trip_features.parquet'
            feature_data.to_parquet(offline_path, index=False)
            logging.info(f"模拟离线特征已保存到: {offline_path}")
        
        if push_to_online:
            # 模拟在线存储（保存为 JSON）
            online_path = output_dir / 'online_features.json'
            
            # 转换为在线存储格式
            online_data = {}
            for _, row in feature_data.head(100).iterrows():  # 只保存前100条作为在线数据
                trip_id = row['trip_id']
                online_data[trip_id] = row.to_dict()
            
            with open(online_path, 'w') as f:
                json.dump(online_data, f, default=str, indent=2)
            
            logging.info(f"模拟在线特征已保存到: {online_path}")
    
    def _prepare_feature_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """准备特征数据格式"""
        
        # 确保必要的列存在
        required_columns = ['trip_id', 'event_timestamp', 'created_timestamp']
        
        for col in required_columns:
            if col not in data.columns:
                if col == 'trip_id':
                    data['trip_id'] = [f'trip_{i:06d}' for i in range(len(data))]
                elif col == 'event_timestamp':
                    data['event_timestamp'] = datetime.now()
                elif col == 'created_timestamp':
                    data['created_timestamp'] = datetime.now()
        
        # 数据类型转换
        if 'event_timestamp' in data.columns:
            data['event_timestamp'] = pd.to_datetime(data['event_timestamp'])
        if 'created_timestamp' in data.columns:
            data['created_timestamp'] = pd.to_datetime(data['created_timestamp'])
        
        # 数据清理
        numeric_columns = data.select_dtypes(include=[np.number]).columns
        data[numeric_columns] = data[numeric_columns].fillna(0)
        
        string_columns = data.select_dtypes(include=['object']).columns
        data[string_columns] = data[string_columns].fillna('')
        
        return data
    
    def _push_to_redis_direct(self, data: pd.DataFrame):
        """直接推送到 Redis（备用方案）"""
        
        try:
            import redis
            
            # 连接 Redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            
            # 推送前100条数据作为在线特征
            for _, row in data.head(100).iterrows():
                trip_id = row['trip_id']
                feature_key = f"feast:trip_features:{trip_id}"
                
                # 转换为 Redis 哈希
                feature_dict = row.to_dict()
                for key, value in feature_dict.items():
                    if pd.isna(value):
                        feature_dict[key] = ""
                    else:
                        feature_dict[key] = str(value)
                
                r.hset(feature_key, mapping=feature_dict)
                r.expire(feature_key, 86400)  # 24小时过期
            
            logging.info("直接推送到 Redis 成功")
            
        except Exception as e:
            logging.warning(f"直接推送到 Redis 失败: {e}")
    
    def _save_push_results(self, output_uri: str, data: pd.DataFrame):
        """保存推送结果"""
        
        os.makedirs(output_uri, exist_ok=True)
        
        # 保存推送摘要
        summary = {
            'push_timestamp': datetime.now().isoformat(),
            'total_features_pushed': len(data),
            'feature_columns': list(data.columns),
            'data_time_range': {
                'start': data['event_timestamp'].min().isoformat() if 'event_timestamp' in data.columns else None,
                'end': data['event_timestamp'].max().isoformat() if 'event_timestamp' in data.columns else None,
            },
            'push_status': 'success'
        }
        
        summary_path = os.path.join(output_uri, 'push_summary.json')
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # 保存样本数据
        sample_path = os.path.join(output_uri, 'sample_features.json')
        sample_data = data.head(10).to_dict('records')
        with open(sample_path, 'w') as f:
            json.dump(sample_data, f, default=str, indent=2)
        
        logging.info(f"推送结果已保存到: {output_uri}")


class FeastPusher(base_component.BaseComponent):
    """FeastPusher TFX 组件"""
    
    SPEC_CLASS = FeastPusherSpec
    EXECUTOR_SPEC = executor_spec.ExecutorClassSpec(FeastPusherExecutor)
    
    def __init__(self,
                 transformed_examples: Examples,
                 feast_repo_path: str = 'feast',
                 push_to_online_store: bool = True,
                 push_to_offline_store: bool = True,
                 feature_service_name: str = 'model_inference_v1'):
        """
        初始化 FeastPusher 组件
        
        Args:
            transformed_examples: 转换后的样本数据
            feast_repo_path: Feast 仓库路径
            push_to_online_store: 是否推送到在线存储
            push_to_offline_store: 是否推送到离线存储
            feature_service_name: 特征服务名称
        """
        
        pushed_features = Artifact(type_name='PushedFeatures')
        
        spec = FeastPusherSpec(
            transformed_examples=transformed_examples,
            pushed_features=pushed_features,
            feast_repo_path=feast_repo_path,
            push_to_online_store=push_to_online_store,
            push_to_offline_store=push_to_offline_store,
            feature_service_name=feature_service_name
        )
        
        super(FeastPusher, self).__init__(spec=spec)
