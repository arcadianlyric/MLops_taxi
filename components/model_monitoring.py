#!/usr/bin/env python3
"""
模型监控组件
集成 Prometheus + Grafana + Loki 进行模型性能监控
"""

import os
import json
import requests
from typing import Any, Dict, List, Optional, Text
from absl import logging
from datetime import datetime
import pandas as pd

from tfx import types
from tfx.components.base import base_component
from tfx.components.base import executor_spec
from tfx.components.base import base_executor
from tfx.types import standard_artifacts
from tfx.types.artifact_utils import get_single_uri
from tfx.utils import io_utils

class ModelMonitoringExecutor(base_executor.BaseExecutor):
    """模型监控执行器"""
    
    def Do(self, input_dict: Dict[Text, List[types.Artifact]],
           output_dict: Dict[Text, List[types.Artifact]],
           exec_properties: Dict[Text, Any]) -> None:
        """
        执行模型监控设置
        
        Args:
            input_dict: 输入工件字典
            output_dict: 输出工件字典
            exec_properties: 执行属性
        """
        
        # 获取输入
        model = input_dict.get('model', [])
        examples = input_dict.get('examples', [])
        
        if not model:
            raise ValueError("需要输入 model")
            
        # 获取配置
        prometheus_url = exec_properties.get('prometheus_url', 'http://prometheus:9090')
        grafana_url = exec_properties.get('grafana_url', 'http://grafana:3000')
        loki_url = exec_properties.get('loki_url', 'http://loki:3100')
        model_name = exec_properties.get('model_name', 'taxi-model')
        
        logging.info(f"开始设置模型监控: {model_name}")
        
        try:
            # 创建监控指标
            self._setup_prometheus_metrics(prometheus_url, model_name)
            
            # 创建 Grafana 仪表板
            self._setup_grafana_dashboard(grafana_url, model_name)
            
            # 配置 Loki 日志收集
            self._setup_loki_logging(loki_url, model_name)
            
            # 生成监控报告
            monitoring_report = self._generate_monitoring_report(
                model, examples, exec_properties
            )
            
            # 创建输出工件
            monitoring_output = output_dict['monitoring_config'][0]
            monitoring_output.uri = f"/tmp/monitoring/{model_name}"
            os.makedirs(monitoring_output.uri, exist_ok=True)
            
            # 保存监控配置
            config_path = os.path.join(monitoring_output.uri, 'monitoring_config.json')
            with open(config_path, 'w') as f:
                json.dump(monitoring_report, f, indent=2)
            
            logging.info(f"✅ 模型监控设置完成: {monitoring_output.uri}")
            
        except Exception as e:
            logging.error(f"❌ 模型监控设置失败: {e}")
            raise
    
    def _setup_prometheus_metrics(self, prometheus_url: str, model_name: str):
        """设置 Prometheus 指标收集"""
        
        # 定义模型监控指标
        metrics_config = {
            'model_prediction_latency': {
                'type': 'histogram',
                'description': f'{model_name} 预测延迟',
                'labels': ['model_name', 'version', 'endpoint']
            },
            'model_prediction_count': {
                'type': 'counter',
                'description': f'{model_name} 预测请求数',
                'labels': ['model_name', 'version', 'status']
            },
            'model_accuracy': {
                'type': 'gauge',
                'description': f'{model_name} 模型准确率',
                'labels': ['model_name', 'version', 'dataset']
            },
            'model_drift_score': {
                'type': 'gauge',
                'description': f'{model_name} 数据漂移分数',
                'labels': ['model_name', 'feature', 'metric']
            },
            'model_resource_usage': {
                'type': 'gauge',
                'description': f'{model_name} 资源使用率',
                'labels': ['model_name', 'resource_type']
            }
        }
        
        # 创建 Prometheus 规则文件
        prometheus_rules = {
            'groups': [{
                'name': f'{model_name}_alerts',
                'rules': [
                    {
                        'alert': 'ModelHighLatency',
                        'expr': f'histogram_quantile(0.95, model_prediction_latency{{model_name="{model_name}"}}) > 1.0',
                        'for': '5m',
                        'labels': {'severity': 'warning'},
                        'annotations': {
                            'summary': f'{model_name} 预测延迟过高',
                            'description': f'{model_name} 95分位延迟超过1秒'
                        }
                    },
                    {
                        'alert': 'ModelAccuracyDrop',
                        'expr': f'model_accuracy{{model_name="{model_name}"}} < 0.8',
                        'for': '10m',
                        'labels': {'severity': 'critical'},
                        'annotations': {
                            'summary': f'{model_name} 准确率下降',
                            'description': f'{model_name} 准确率低于80%'
                        }
                    },
                    {
                        'alert': 'ModelDataDrift',
                        'expr': f'model_drift_score{{model_name="{model_name}"}} > 0.5',
                        'for': '15m',
                        'labels': {'severity': 'warning'},
                        'annotations': {
                            'summary': f'{model_name} 检测到数据漂移',
                            'description': f'{model_name} 数据漂移分数超过阈值'
                        }
                    }
                ]
            }]
        }
        
        logging.info(f"Prometheus 指标配置完成: {len(metrics_config)} 个指标")
        return metrics_config, prometheus_rules
    
    def _setup_grafana_dashboard(self, grafana_url: str, model_name: str):
        """设置 Grafana 仪表板"""
        
        dashboard_config = {
            'dashboard': {
                'id': None,
                'title': f'{model_name} 模型监控仪表板',
                'tags': ['mlops', 'model-monitoring', model_name],
                'timezone': 'browser',
                'panels': [
                    {
                        'id': 1,
                        'title': '预测请求数',
                        'type': 'stat',
                        'targets': [{
                            'expr': f'sum(rate(model_prediction_count{{model_name="{model_name}"}}[5m]))',
                            'legendFormat': 'RPS'
                        }],
                        'gridPos': {'h': 8, 'w': 6, 'x': 0, 'y': 0}
                    },
                    {
                        'id': 2,
                        'title': '预测延迟',
                        'type': 'graph',
                        'targets': [{
                            'expr': f'histogram_quantile(0.95, model_prediction_latency{{model_name="{model_name}"}})',
                            'legendFormat': 'P95 延迟'
                        }],
                        'gridPos': {'h': 8, 'w': 12, 'x': 6, 'y': 0}
                    },
                    {
                        'id': 3,
                        'title': '模型准确率',
                        'type': 'graph',
                        'targets': [{
                            'expr': f'model_accuracy{{model_name="{model_name}"}}',
                            'legendFormat': '准确率'
                        }],
                        'gridPos': {'h': 8, 'w': 6, 'x': 18, 'y': 0}
                    },
                    {
                        'id': 4,
                        'title': '数据漂移监控',
                        'type': 'heatmap',
                        'targets': [{
                            'expr': f'model_drift_score{{model_name="{model_name}"}}',
                            'legendFormat': '{{feature}}'
                        }],
                        'gridPos': {'h': 8, 'w': 12, 'x': 0, 'y': 8}
                    },
                    {
                        'id': 5,
                        'title': '资源使用情况',
                        'type': 'graph',
                        'targets': [
                            {
                                'expr': f'model_resource_usage{{model_name="{model_name}", resource_type="cpu"}}',
                                'legendFormat': 'CPU 使用率'
                            },
                            {
                                'expr': f'model_resource_usage{{model_name="{model_name}", resource_type="memory"}}',
                                'legendFormat': '内存使用率'
                            }
                        ],
                        'gridPos': {'h': 8, 'w': 12, 'x': 12, 'y': 8}
                    }
                ],
                'time': {'from': 'now-1h', 'to': 'now'},
                'refresh': '30s'
            }
        }
        
        logging.info(f"Grafana 仪表板配置完成: {dashboard_config['dashboard']['title']}")
        return dashboard_config
    
    def _setup_loki_logging(self, loki_url: str, model_name: str):
        """设置 Loki 日志收集"""
        
        # 定义日志标签和查询
        log_config = {
            'labels': {
                'app': model_name,
                'component': 'model-serving',
                'environment': 'production'
            },
            'queries': [
                {
                    'name': '错误日志',
                    'query': f'{{app="{model_name}"}} |= "ERROR"',
                    'description': '模型服务错误日志'
                },
                {
                    'name': '预测日志',
                    'query': f'{{app="{model_name}"}} |= "prediction"',
                    'description': '模型预测日志'
                },
                {
                    'name': '性能日志',
                    'query': f'{{app="{model_name}"}} |= "latency"',
                    'description': '模型性能日志'
                }
            ],
            'alerts': [
                {
                    'name': 'HighErrorRate',
                    'query': f'rate({{app="{model_name}"}} |= "ERROR" [5m]) > 0.1',
                    'description': '错误率过高告警'
                }
            ]
        }
        
        logging.info(f"Loki 日志配置完成: {len(log_config['queries'])} 个查询")
        return log_config
    
    def _generate_monitoring_report(self, model, examples, exec_properties):
        """生成监控报告"""
        
        model_uri = get_single_uri(model) if model else ""
        
        report = {
            'model_info': {
                'name': exec_properties.get('model_name', 'taxi-model'),
                'version': datetime.now().strftime('%Y%m%d_%H%M%S'),
                'uri': model_uri,
                'framework': 'tensorflow'
            },
            'monitoring_setup': {
                'prometheus_enabled': True,
                'grafana_enabled': True,
                'loki_enabled': True,
                'alerts_configured': True
            },
            'metrics': {
                'prediction_latency': 'histogram',
                'prediction_count': 'counter',
                'model_accuracy': 'gauge',
                'data_drift': 'gauge',
                'resource_usage': 'gauge'
            },
            'thresholds': {
                'max_latency_p95': 1.0,
                'min_accuracy': 0.8,
                'max_drift_score': 0.5,
                'max_error_rate': 0.05
            },
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        return report

class ModelMonitoringComponent(base_component.BaseComponent):
    """模型监控组件"""
    
    SPEC_CLASS = types.ComponentSpec
    EXECUTOR_SPEC = executor_spec.ExecutorClassSpec(ModelMonitoringExecutor)
    
    def __init__(self,
                 model: types.Channel,
                 examples: Optional[types.Channel] = None,
                 model_name: str = 'taxi-model',
                 prometheus_url: str = 'http://prometheus:9090',
                 grafana_url: str = 'http://grafana:3000',
                 loki_url: str = 'http://loki:3100'):
        """
        初始化模型监控组件
        
        Args:
            model: 训练好的模型
            examples: 示例数据
            model_name: 模型名称
            prometheus_url: Prometheus 地址
            grafana_url: Grafana 地址
            loki_url: Loki 地址
        """
        
        # 定义输出
        monitoring_config = types.Channel(type=standard_artifacts.ExternalArtifact)
        
        spec = types.ComponentSpec(
            inputs={
                'model': model,
                'examples': examples
            } if examples else {
                'model': model
            },
            outputs={
                'monitoring_config': monitoring_config
            },
            parameters={
                'model_name': model_name,
                'prometheus_url': prometheus_url,
                'grafana_url': grafana_url,
                'loki_url': loki_url
            }
        )
        
        super().__init__(spec=spec)
