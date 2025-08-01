#!/usr/bin/env python3
"""
数据漂移监控组件
基于 TensorFlow Data Validation (TFDV) 实现完整的数据漂移检测和监控
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import tensorflow_data_validation as tfdv
from tensorflow_metadata.proto.v0 import statistics_pb2
from tensorflow_metadata.proto.v0 import schema_pb2

from tfx.components.base import base_component
from tfx.components.base import executor_spec
from tfx.components.base import base_executor
from tfx.types import Artifact
from tfx.types import ComponentSpec
from tfx.types.standard_artifacts import Examples, Schema
from tfx.utils import io_utils


class DataDriftMonitorSpec(ComponentSpec):
    """数据漂移监控组件规范"""
    
    PARAMETERS = {
        'baseline_data_uri': str,
        'current_data_uri': str,
        'drift_threshold': float,
        'feature_allowlist': List[str],
    }
    
    INPUTS = {
        'baseline_examples': Examples,
        'current_examples': Examples,
        'schema': Schema,
    }
    
    OUTPUTS = {
        'drift_report': Artifact,
        'drift_metrics': Artifact,
    }


class DataDriftMonitorExecutor(base_executor.BaseExecutor):
    """数据漂移监控执行器"""
    
    def Do(self, input_dict: Dict[str, List[Artifact]],
           output_dict: Dict[str, List[Artifact]],
           exec_properties: Dict[str, Any]) -> None:
        """执行数据漂移监控"""
        
        logging.info("开始执行数据漂移监控...")
        
        # 获取输入
        baseline_examples = input_dict['baseline_examples'][0]
        current_examples = input_dict['current_examples'][0]
        schema = input_dict['schema'][0]
        
        # 获取参数
        drift_threshold = exec_properties.get('drift_threshold', 0.1)
        feature_allowlist = exec_properties.get('feature_allowlist', [])
        
        # 读取 schema
        schema_proto = self._read_schema(schema.uri)
        
        # 生成统计信息
        baseline_stats = self._generate_statistics(baseline_examples.uri)
        current_stats = self._generate_statistics(current_examples.uri)
        
        # 检测数据漂移
        drift_results = self._detect_drift(
            baseline_stats, current_stats, schema_proto,
            drift_threshold, feature_allowlist
        )
        
        # 生成漂移报告
        drift_report = self._generate_drift_report(drift_results)
        
        # 生成 Prometheus 指标
        drift_metrics = self._generate_prometheus_metrics(drift_results)
        
        # 保存输出
        self._save_drift_report(output_dict['drift_report'][0].uri, drift_report)
        self._save_drift_metrics(output_dict['drift_metrics'][0].uri, drift_metrics)
        
        logging.info("数据漂移监控完成")
    
    def _read_schema(self, schema_uri: str) -> schema_pb2.Schema:
        """读取数据模式"""
        schema_path = os.path.join(schema_uri, 'schema.pbtxt')
        schema_proto = schema_pb2.Schema()
        
        with open(schema_path, 'r') as f:
            schema_text = f.read()
            from google.protobuf import text_format
            text_format.Parse(schema_text, schema_proto)
        
        return schema_proto
    
    def _generate_statistics(self, examples_uri: str) -> statistics_pb2.DatasetFeatureStatisticsList:
        """生成数据统计信息"""
        # 假设数据是 CSV 格式
        csv_files = []
        for root, dirs, files in os.walk(examples_uri):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
        
        if not csv_files:
            raise ValueError(f"在 {examples_uri} 中未找到 CSV 文件")
        
        # 使用第一个 CSV 文件生成统计
        stats = tfdv.generate_statistics_from_csv(csv_files[0])
        return stats
    
    def _detect_drift(self, baseline_stats: statistics_pb2.DatasetFeatureStatisticsList,
                     current_stats: statistics_pb2.DatasetFeatureStatisticsList,
                     schema: schema_pb2.Schema,
                     threshold: float,
                     feature_allowlist: List[str]) -> Dict[str, Any]:
        """检测数据漂移"""
        
        drift_results = {
            'timestamp': datetime.now().isoformat(),
            'threshold': threshold,
            'overall_drift_detected': False,
            'features': {}
        }
        
        # 获取特征列表
        features_to_check = []
        for feature in schema.feature:
            if not feature_allowlist or feature.name in feature_allowlist:
                features_to_check.append(feature.name)
        
        # 检查每个特征的漂移
        for feature_name in features_to_check:
            drift_score = self._calculate_drift_score(
                baseline_stats, current_stats, feature_name
            )
            
            is_drifted = drift_score > threshold
            
            drift_results['features'][feature_name] = {
                'drift_score': drift_score,
                'is_drifted': is_drifted,
                'drift_type': self._classify_drift_type(drift_score),
                'baseline_stats': self._extract_feature_stats(baseline_stats, feature_name),
                'current_stats': self._extract_feature_stats(current_stats, feature_name)
            }
            
            if is_drifted:
                drift_results['overall_drift_detected'] = True
        
        return drift_results
    
    def _calculate_drift_score(self, baseline_stats, current_stats, feature_name: str) -> float:
        """计算特征漂移分数（使用 Jensen-Shannon 散度）"""
        try:
            baseline_feature = self._get_feature_stats(baseline_stats, feature_name)
            current_feature = self._get_feature_stats(current_stats, feature_name)
            
            if not baseline_feature or not current_feature:
                return 0.0
            
            # 对于数值特征，使用分布比较
            if hasattr(baseline_feature, 'num_stats') and hasattr(current_feature, 'num_stats'):
                return self._calculate_numerical_drift(baseline_feature.num_stats, current_feature.num_stats)
            
            # 对于分类特征，使用频率分布比较
            elif hasattr(baseline_feature, 'string_stats') and hasattr(current_feature, 'string_stats'):
                return self._calculate_categorical_drift(baseline_feature.string_stats, current_feature.string_stats)
            
            return 0.0
            
        except Exception as e:
            logging.warning(f"计算特征 {feature_name} 漂移分数时出错: {e}")
            return 0.0
    
    def _calculate_numerical_drift(self, baseline_stats, current_stats) -> float:
        """计算数值特征漂移分数"""
        # 使用均值和标准差的变化来估计漂移
        baseline_mean = baseline_stats.mean
        current_mean = current_stats.mean
        baseline_std = baseline_stats.std_dev
        current_std = current_stats.std_dev
        
        # 标准化差异
        mean_diff = abs(baseline_mean - current_mean) / (baseline_std + 1e-8)
        std_diff = abs(baseline_std - current_std) / (baseline_std + 1e-8)
        
        # 组合分数
        drift_score = (mean_diff + std_diff) / 2
        return min(drift_score, 1.0)  # 限制在 [0, 1] 范围内
    
    def _calculate_categorical_drift(self, baseline_stats, current_stats) -> float:
        """计算分类特征漂移分数"""
        # 获取频率分布
        baseline_freq = {}
        for value_count in baseline_stats.top_values:
            baseline_freq[value_count.value] = value_count.frequency
        
        current_freq = {}
        for value_count in current_stats.top_values:
            current_freq[value_count.value] = value_count.frequency
        
        # 计算 Jensen-Shannon 散度
        all_values = set(baseline_freq.keys()) | set(current_freq.keys())
        
        p = np.array([baseline_freq.get(v, 0) for v in all_values])
        q = np.array([current_freq.get(v, 0) for v in all_values])
        
        # 归一化
        p = p / (p.sum() + 1e-8)
        q = q / (q.sum() + 1e-8)
        
        # Jensen-Shannon 散度
        m = (p + q) / 2
        js_div = 0.5 * self._kl_divergence(p, m) + 0.5 * self._kl_divergence(q, m)
        
        return min(np.sqrt(js_div), 1.0)
    
    def _kl_divergence(self, p, q):
        """计算 KL 散度"""
        return np.sum(p * np.log((p + 1e-8) / (q + 1e-8)))
    
    def _get_feature_stats(self, stats, feature_name: str):
        """获取特定特征的统计信息"""
        for dataset in stats.datasets:
            for feature in dataset.features:
                if feature.name == feature_name:
                    return feature
        return None
    
    def _classify_drift_type(self, drift_score: float) -> str:
        """分类漂移类型"""
        if drift_score < 0.1:
            return "无漂移"
        elif drift_score < 0.3:
            return "轻微漂移"
        elif drift_score < 0.5:
            return "中等漂移"
        else:
            return "严重漂移"
    
    def _extract_feature_stats(self, stats, feature_name: str) -> Dict[str, Any]:
        """提取特征统计信息"""
        feature_stats = self._get_feature_stats(stats, feature_name)
        if not feature_stats:
            return {}
        
        result = {
            'name': feature_stats.name,
            'type': feature_stats.type
        }
        
        if hasattr(feature_stats, 'num_stats'):
            result.update({
                'mean': feature_stats.num_stats.mean,
                'std_dev': feature_stats.num_stats.std_dev,
                'min': feature_stats.num_stats.min,
                'max': feature_stats.num_stats.max,
                'median': feature_stats.num_stats.median
            })
        
        if hasattr(feature_stats, 'string_stats'):
            result.update({
                'unique_count': feature_stats.string_stats.unique,
                'top_values': [
                    {'value': tv.value, 'frequency': tv.frequency}
                    for tv in feature_stats.string_stats.top_values[:5]
                ]
            })
        
        return result
    
    def _generate_drift_report(self, drift_results: Dict[str, Any]) -> Dict[str, Any]:
        """生成漂移报告"""
        report = {
            'summary': {
                'timestamp': drift_results['timestamp'],
                'overall_drift_detected': drift_results['overall_drift_detected'],
                'threshold': drift_results['threshold'],
                'total_features_checked': len(drift_results['features']),
                'drifted_features_count': sum(
                    1 for f in drift_results['features'].values() if f['is_drifted']
                )
            },
            'feature_details': drift_results['features'],
            'recommendations': self._generate_recommendations(drift_results)
        }
        
        return report
    
    def _generate_recommendations(self, drift_results: Dict[str, Any]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if drift_results['overall_drift_detected']:
            recommendations.append("检测到数据漂移，建议进行以下操作：")
            recommendations.append("1. 检查数据收集流程是否有变化")
            recommendations.append("2. 考虑重新训练模型")
            recommendations.append("3. 更新数据预处理逻辑")
            
            # 针对严重漂移的特征
            severe_drift_features = [
                name for name, stats in drift_results['features'].items()
                if stats['drift_score'] > 0.5
            ]
            
            if severe_drift_features:
                recommendations.append(f"4. 特别关注严重漂移特征: {', '.join(severe_drift_features)}")
        else:
            recommendations.append("未检测到显著数据漂移，模型可以继续使用")
        
        return recommendations
    
    def _generate_prometheus_metrics(self, drift_results: Dict[str, Any]) -> Dict[str, Any]:
        """生成 Prometheus 指标"""
        metrics = {
            'data_drift_overall': {
                'value': 1 if drift_results['overall_drift_detected'] else 0,
                'labels': {'timestamp': drift_results['timestamp']}
            },
            'data_drift_features': []
        }
        
        for feature_name, feature_stats in drift_results['features'].items():
            metrics['data_drift_features'].append({
                'feature_name': feature_name,
                'drift_score': feature_stats['drift_score'],
                'is_drifted': 1 if feature_stats['is_drifted'] else 0,
                'drift_type': feature_stats['drift_type']
            })
        
        return metrics
    
    def _save_drift_report(self, output_uri: str, report: Dict[str, Any]) -> None:
        """保存漂移报告"""
        os.makedirs(output_uri, exist_ok=True)
        report_path = os.path.join(output_uri, 'drift_report.json')
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logging.info(f"漂移报告已保存到: {report_path}")
    
    def _save_drift_metrics(self, output_uri: str, metrics: Dict[str, Any]) -> None:
        """保存漂移指标"""
        os.makedirs(output_uri, exist_ok=True)
        metrics_path = os.path.join(output_uri, 'drift_metrics.json')
        
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        
        logging.info(f"漂移指标已保存到: {metrics_path}")


class DataDriftMonitor(base_component.BaseComponent):
    """数据漂移监控组件"""
    
    SPEC_CLASS = DataDriftMonitorSpec
    EXECUTOR_SPEC = executor_spec.ExecutorClassSpec(DataDriftMonitorExecutor)
    
    def __init__(self,
                 baseline_examples: Examples,
                 current_examples: Examples,
                 schema: Schema,
                 drift_threshold: float = 0.1,
                 feature_allowlist: Optional[List[str]] = None):
        """
        初始化数据漂移监控组件
        
        Args:
            baseline_examples: 基线数据
            current_examples: 当前数据
            schema: 数据模式
            drift_threshold: 漂移阈值
            feature_allowlist: 要检查的特征列表
        """
        
        drift_report = Artifact(type_name='DriftReport')
        drift_metrics = Artifact(type_name='DriftMetrics')
        
        spec = DataDriftMonitorSpec(
            baseline_examples=baseline_examples,
            current_examples=current_examples,
            schema=schema,
            drift_report=drift_report,
            drift_metrics=drift_metrics,
            drift_threshold=drift_threshold,
            feature_allowlist=feature_allowlist or []
        )
        
        super(DataDriftMonitor, self).__init__(spec=spec)
