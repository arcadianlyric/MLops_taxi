#!/usr/bin/env python3
"""
KFServing 模型部署组件
将训练好的模型部署到 KFServing 进行在线推理
"""

import os
import yaml
from typing import Any, Dict, List, Optional, Text
from absl import logging
import kubernetes
from kubernetes import client, config

from tfx import types
from tfx.components.base import base_component
from tfx.components.base import executor_spec
from tfx.components.base import base_executor
from tfx.types import standard_artifacts
from tfx.types.artifact_utils import get_single_uri
from tfx.utils import io_utils

class KFServingDeployerExecutor(base_executor.BaseExecutor):
    """KFServing 部署执行器"""
    
    def Do(self, input_dict: Dict[Text, List[types.Artifact]],
           output_dict: Dict[Text, List[types.Artifact]],
           exec_properties: Dict[Text, Any]) -> None:
        """
        执行模型部署到 KFServing
        
        Args:
            input_dict: 输入工件字典
            output_dict: 输出工件字典
            exec_properties: 执行属性
        """
        
        # 获取输入
        model = input_dict.get('model', [])
        model_blessing = input_dict.get('model_blessing', [])
        
        if not model:
            raise ValueError("需要输入 model")
            
        # 检查模型是否通过验证
        if model_blessing and not self._is_model_blessed(model_blessing[0]):
            logging.warning("模型未通过验证，跳过部署")
            return
            
        # 获取配置
        service_name = exec_properties.get('service_name', 'taxi-model-serving')
        namespace = exec_properties.get('namespace', 'default')
        model_uri = get_single_uri(model)
        
        logging.info(f"开始部署模型到 KFServing: {service_name}")
        
        try:
            # 初始化 Kubernetes 客户端
            self._init_k8s_client()
            
            # 创建 InferenceService
            inference_service = self._create_inference_service(
                service_name, namespace, model_uri, exec_properties
            )
            
            # 部署到 Kubernetes
            self._deploy_inference_service(inference_service, namespace)
            
            # 等待部署就绪
            self._wait_for_deployment(service_name, namespace)
            
            # 创建输出工件
            serving_output = output_dict['serving_config'][0]
            serving_output.uri = f"http://{service_name}.{namespace}.svc.cluster.local"
            
            # 保存部署信息
            deployment_info = {
                'service_name': service_name,
                'namespace': namespace,
                'model_uri': model_uri,
                'endpoint': serving_output.uri,
                'status': 'deployed'
            }
            
            io_utils.write_string_file(
                os.path.join(serving_output.uri.replace('http://', '/tmp/'), 'deployment.yaml'),
                yaml.dump(deployment_info)
            )
            
            logging.info(f"✅ 模型成功部署到 KFServing: {serving_output.uri}")
            
        except Exception as e:
            logging.error(f"❌ KFServing 部署失败: {e}")
            raise
    
    def _is_model_blessed(self, model_blessing):
        """检查模型是否通过验证"""
        try:
            blessing_uri = get_single_uri(model_blessing)
            # 检查 blessing 文件
            return os.path.exists(os.path.join(blessing_uri, 'BLESSED'))
        except:
            return True  # 如果无法检查，默认通过
    
    def _init_k8s_client(self):
        """初始化 Kubernetes 客户端"""
        try:
            # 尝试加载集群内配置
            config.load_incluster_config()
        except:
            # 加载本地配置
            config.load_kube_config()
    
    def _create_inference_service(self, service_name: str, namespace: str, 
                                model_uri: str, exec_properties: Dict[str, Any]):
        """创建 InferenceService 配置"""
        
        # 获取配置参数
        framework = exec_properties.get('framework', 'tensorflow')
        min_replicas = exec_properties.get('min_replicas', 1)
        max_replicas = exec_properties.get('max_replicas', 3)
        cpu_request = exec_properties.get('cpu_request', '100m')
        memory_request = exec_properties.get('memory_request', '512Mi')
        cpu_limit = exec_properties.get('cpu_limit', '1')
        memory_limit = exec_properties.get('memory_limit', '2Gi')
        
        inference_service = {
            'apiVersion': 'serving.kserve.io/v1beta1',
            'kind': 'InferenceService',
            'metadata': {
                'name': service_name,
                'namespace': namespace,
                'annotations': {
                    'serving.kserve.io/deploymentMode': 'Serverless'
                },
                'labels': {
                    'app': 'taxi-model',
                    'version': 'v1',
                    'managed-by': 'tfx-pipeline'
                }
            },
            'spec': {
                'predictor': {
                    'serviceAccountName': 'default',
                    framework: {
                        'storageUri': model_uri,
                        'resources': {
                            'requests': {
                                'cpu': cpu_request,
                                'memory': memory_request
                            },
                            'limits': {
                                'cpu': cpu_limit,
                                'memory': memory_limit
                            }
                        }
                    },
                    'minReplicas': min_replicas,
                    'maxReplicas': max_replicas,
                    'scaleTarget': 70,
                    'scaleMetric': 'concurrency'
                }
            }
        }
        
        # 添加 Transformer (如果需要)
        if exec_properties.get('enable_transformer', False):
            transformer_image = exec_properties.get('transformer_image', 
                                                  'your-registry/taxi-transformer:latest')
            inference_service['spec']['transformer'] = {
                'containers': [{
                    'name': 'kserve-container',
                    'image': transformer_image,
                    'env': [
                        {
                            'name': 'FEAST_SERVING_URL',
                            'value': exec_properties.get('feast_serving_url', 
                                                       'feast-serving:6566')
                        }
                    ],
                    'resources': {
                        'requests': {'cpu': '100m', 'memory': '256Mi'},
                        'limits': {'cpu': '500m', 'memory': '1Gi'}
                    }
                }]
            }
        
        return inference_service
    
    def _deploy_inference_service(self, inference_service: Dict, namespace: str):
        """部署 InferenceService 到 Kubernetes"""
        
        # 创建自定义资源 API 客户端
        api_client = client.ApiClient()
        custom_api = client.CustomObjectsApi(api_client)
        
        try:
            # 检查是否已存在
            existing_service = custom_api.get_namespaced_custom_object(
                group='serving.kserve.io',
                version='v1beta1',
                namespace=namespace,
                plural='inferenceservices',
                name=inference_service['metadata']['name']
            )
            
            # 如果存在，则更新
            logging.info(f"更新现有 InferenceService: {inference_service['metadata']['name']}")
            custom_api.patch_namespaced_custom_object(
                group='serving.kserve.io',
                version='v1beta1',
                namespace=namespace,
                plural='inferenceservices',
                name=inference_service['metadata']['name'],
                body=inference_service
            )
            
        except client.exceptions.ApiException as e:
            if e.status == 404:
                # 不存在，创建新的
                logging.info(f"创建新 InferenceService: {inference_service['metadata']['name']}")
                custom_api.create_namespaced_custom_object(
                    group='serving.kserve.io',
                    version='v1beta1',
                    namespace=namespace,
                    plural='inferenceservices',
                    body=inference_service
                )
            else:
                raise
    
    def _wait_for_deployment(self, service_name: str, namespace: str, timeout: int = 300):
        """等待部署就绪"""
        import time
        
        api_client = client.ApiClient()
        custom_api = client.CustomObjectsApi(api_client)
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                service = custom_api.get_namespaced_custom_object(
                    group='serving.kserve.io',
                    version='v1beta1',
                    namespace=namespace,
                    plural='inferenceservices',
                    name=service_name
                )
                
                status = service.get('status', {})
                conditions = status.get('conditions', [])
                
                # 检查就绪状态
                for condition in conditions:
                    if (condition.get('type') == 'Ready' and 
                        condition.get('status') == 'True'):
                        logging.info(f"✅ InferenceService {service_name} 部署就绪")
                        return
                
                logging.info(f"等待 InferenceService {service_name} 就绪...")
                time.sleep(10)
                
            except Exception as e:
                logging.warning(f"检查部署状态失败: {e}")
                time.sleep(10)
        
        raise TimeoutError(f"InferenceService {service_name} 部署超时")

class KFServingDeployer(base_component.BaseComponent):
    """KFServing 部署组件"""
    
    SPEC_CLASS = types.ComponentSpec
    EXECUTOR_SPEC = executor_spec.ExecutorClassSpec(KFServingDeployerExecutor)
    
    def __init__(self,
                 model: types.Channel,
                 model_blessing: Optional[types.Channel] = None,
                 service_name: str = 'taxi-model-serving',
                 namespace: str = 'default',
                 framework: str = 'tensorflow',
                 min_replicas: int = 1,
                 max_replicas: int = 3,
                 enable_transformer: bool = False,
                 feast_serving_url: str = 'feast-serving:6566'):
        """
        初始化 KFServing 部署组件
        
        Args:
            model: 训练好的模型
            model_blessing: 模型验证结果
            service_name: 服务名称
            namespace: Kubernetes 命名空间
            framework: 模型框架 (tensorflow, sklearn, xgboost)
            min_replicas: 最小副本数
            max_replicas: 最大副本数
            enable_transformer: 是否启用 Transformer
            feast_serving_url: Feast 服务地址
        """
        
        # 定义输出
        serving_config = types.Channel(type=standard_artifacts.ExternalArtifact)
        
        spec = types.ComponentSpec(
            inputs={
                'model': model,
                'model_blessing': model_blessing
            } if model_blessing else {
                'model': model
            },
            outputs={
                'serving_config': serving_config
            },
            parameters={
                'service_name': service_name,
                'namespace': namespace,
                'framework': framework,
                'min_replicas': min_replicas,
                'max_replicas': max_replicas,
                'enable_transformer': enable_transformer,
                'feast_serving_url': feast_serving_url,
                'cpu_request': '100m',
                'memory_request': '512Mi',
                'cpu_limit': '1',
                'memory_limit': '2Gi'
            }
        )
        
        super().__init__(spec=spec)
