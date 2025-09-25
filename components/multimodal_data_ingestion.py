"""
Multimodal Data Ingestion Component for RAG System
支持文本、图像和多模态数据集的摄取和预处理
"""

import os
import json
import logging
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from PIL import Image
import requests
from datasets import load_dataset, Dataset
import torch
from transformers import AutoTokenizer
import cv2
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DatasetConfig:
    """数据集配置"""
    name: str
    type: str  # 'text', 'image', 'multimodal'
    source: str  # 'huggingface', 'local', 'url'
    path: str
    preprocessing: Dict
    batch_size: int = 32

class MultimodalDataIngestion:
    """多模态数据摄取组件"""
    
    def __init__(self, config_path: str = None):
        """
        初始化数据摄取组件
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.datasets_config = self._load_config()
        self.supported_text_datasets = [
            'ms_marco', 'natural_questions', 'squad_v2', 'fever'
        ]
        self.supported_image_datasets = [
            'coco', 'visual_genome', 'open_images', 'imagenet'
        ]
        self.supported_multimodal_datasets = [
            'vqa_v2', 'conceptual_captions', 'flickr30k', 'clip_dataset'
        ]
        
    def _load_config(self) -> Dict:
        """加载数据集配置"""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "text_datasets": {
                "ms_marco": {
                    "source": "huggingface",
                    "path": "microsoft/ms_marco",
                    "subset": "v1.1",
                    "preprocessing": {
                        "max_length": 512,
                        "tokenizer": "bert-base-uncased"
                    }
                },
                "natural_questions": {
                    "source": "huggingface", 
                    "path": "natural_questions",
                    "preprocessing": {
                        "max_length": 512,
                        "tokenizer": "bert-base-uncased"
                    }
                }
            },
            "image_datasets": {
                "coco": {
                    "source": "huggingface",
                    "path": "detection-datasets/coco",
                    "preprocessing": {
                        "image_size": [224, 224],
                        "normalize": True,
                        "augmentation": True
                    }
                }
            },
            "multimodal_datasets": {
                "vqa_v2": {
                    "source": "huggingface",
                    "path": "HuggingFaceM4/VQAv2",
                    "preprocessing": {
                        "image_size": [224, 224],
                        "max_text_length": 128
                    }
                }
            }
        }
    
    def ingest_text_data(self, dataset_name: str, output_dir: str = "data/text") -> Dict:
        """
        摄取文本数据集
        
        Args:
            dataset_name: 数据集名称
            output_dir: 输出目录
            
        Returns:
            摄取结果统计
        """
        logger.info(f"开始摄取文本数据集: {dataset_name}")
        
        if dataset_name not in self.supported_text_datasets:
            raise ValueError(f"不支持的文本数据集: {dataset_name}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            if dataset_name == 'ms_marco':
                return self._ingest_ms_marco(output_dir)
            elif dataset_name == 'natural_questions':
                return self._ingest_natural_questions(output_dir)
            elif dataset_name == 'squad_v2':
                return self._ingest_squad_v2(output_dir)
            else:
                return self._ingest_generic_text_dataset(dataset_name, output_dir)
                
        except Exception as e:
            logger.error(f"摄取文本数据集失败: {str(e)}")
            raise
    
    def ingest_image_data(self, dataset_name: str, output_dir: str = "data/images") -> Dict:
        """
        摄取图像数据集
        
        Args:
            dataset_name: 数据集名称
            output_dir: 输出目录
            
        Returns:
            摄取结果统计
        """
        logger.info(f"开始摄取图像数据集: {dataset_name}")
        
        if dataset_name not in self.supported_image_datasets:
            raise ValueError(f"不支持的图像数据集: {dataset_name}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            if dataset_name == 'coco':
                return self._ingest_coco(output_dir)
            elif dataset_name == 'visual_genome':
                return self._ingest_visual_genome(output_dir)
            else:
                return self._ingest_generic_image_dataset(dataset_name, output_dir)
                
        except Exception as e:
            logger.error(f"摄取图像数据集失败: {str(e)}")
            raise
    
    def ingest_multimodal_data(self, dataset_name: str, output_dir: str = "data/multimodal") -> Dict:
        """
        摄取多模态数据集
        
        Args:
            dataset_name: 数据集名称
            output_dir: 输出目录
            
        Returns:
            摄取结果统计
        """
        logger.info(f"开始摄取多模态数据集: {dataset_name}")
        
        if dataset_name not in self.supported_multimodal_datasets:
            raise ValueError(f"不支持的多模态数据集: {dataset_name}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            if dataset_name == 'vqa_v2':
                return self._ingest_vqa_v2(output_dir)
            elif dataset_name == 'conceptual_captions':
                return self._ingest_conceptual_captions(output_dir)
            elif dataset_name == 'flickr30k':
                return self._ingest_flickr30k(output_dir)
            else:
                return self._ingest_generic_multimodal_dataset(dataset_name, output_dir)
                
        except Exception as e:
            logger.error(f"摄取多模态数据集失败: {str(e)}")
            raise
    
    def _ingest_ms_marco(self, output_dir: str) -> Dict:
        """摄取 MS-MARCO 数据集"""
        try:
            # 加载数据集
            dataset = load_dataset("microsoft/ms_marco", "v1.1", split="train[:10000]")  # 限制样本数量
            
            # 预处理
            processed_data = []
            for item in dataset:
                processed_item = {
                    'query_id': item.get('query_id', ''),
                    'query': item.get('query', ''),
                    'passages': item.get('passages', []),
                    'answers': item.get('answers', []),
                    'wellFormedAnswers': item.get('wellFormedAnswers', [])
                }
                processed_data.append(processed_item)
            
            # 保存处理后的数据
            output_file = os.path.join(output_dir, 'ms_marco_processed.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
            
            return {
                'dataset_name': 'ms_marco',
                'total_samples': len(processed_data),
                'output_file': output_file,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"MS-MARCO 摄取失败: {str(e)}")
            # 创建模拟数据
            return self._create_mock_text_data(output_dir, 'ms_marco')
    
    def _ingest_natural_questions(self, output_dir: str) -> Dict:
        """摄取 Natural Questions 数据集"""
        try:
            # 由于 Natural Questions 数据集较大，这里创建模拟数据
            return self._create_mock_text_data(output_dir, 'natural_questions')
            
        except Exception as e:
            logger.error(f"Natural Questions 摄取失败: {str(e)}")
            return self._create_mock_text_data(output_dir, 'natural_questions')
    
    def _ingest_squad_v2(self, output_dir: str) -> Dict:
        """摄取 SQuAD v2 数据集"""
        try:
            dataset = load_dataset("squad_v2", split="train[:1000]")
            
            processed_data = []
            for item in dataset:
                processed_item = {
                    'id': item.get('id', ''),
                    'title': item.get('title', ''),
                    'context': item.get('context', ''),
                    'question': item.get('question', ''),
                    'answers': item.get('answers', {})
                }
                processed_data.append(processed_item)
            
            output_file = os.path.join(output_dir, 'squad_v2_processed.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
            
            return {
                'dataset_name': 'squad_v2',
                'total_samples': len(processed_data),
                'output_file': output_file,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"SQuAD v2 摄取失败: {str(e)}")
            return self._create_mock_text_data(output_dir, 'squad_v2')
    
    def _ingest_coco(self, output_dir: str) -> Dict:
        """摄取 COCO 数据集"""
        try:
            # 创建模拟 COCO 数据
            return self._create_mock_image_data(output_dir, 'coco')
            
        except Exception as e:
            logger.error(f"COCO 摄取失败: {str(e)}")
            return self._create_mock_image_data(output_dir, 'coco')
    
    def _ingest_visual_genome(self, output_dir: str) -> Dict:
        """摄取 Visual Genome 数据集"""
        try:
            return self._create_mock_image_data(output_dir, 'visual_genome')
            
        except Exception as e:
            logger.error(f"Visual Genome 摄取失败: {str(e)}")
            return self._create_mock_image_data(output_dir, 'visual_genome')
    
    def _ingest_vqa_v2(self, output_dir: str) -> Dict:
        """摄取 VQA v2 数据集"""
        try:
            return self._create_mock_multimodal_data(output_dir, 'vqa_v2')
            
        except Exception as e:
            logger.error(f"VQA v2 摄取失败: {str(e)}")
            return self._create_mock_multimodal_data(output_dir, 'vqa_v2')
    
    def _ingest_conceptual_captions(self, output_dir: str) -> Dict:
        """摄取 Conceptual Captions 数据集"""
        try:
            return self._create_mock_multimodal_data(output_dir, 'conceptual_captions')
            
        except Exception as e:
            logger.error(f"Conceptual Captions 摄取失败: {str(e)}")
            return self._create_mock_multimodal_data(output_dir, 'conceptual_captions')
    
    def _ingest_flickr30k(self, output_dir: str) -> Dict:
        """摄取 Flickr30K 数据集"""
        try:
            return self._create_mock_multimodal_data(output_dir, 'flickr30k')
            
        except Exception as e:
            logger.error(f"Flickr30K 摄取失败: {str(e)}")
            return self._create_mock_multimodal_data(output_dir, 'flickr30k')
    
    def _create_mock_text_data(self, output_dir: str, dataset_name: str) -> Dict:
        """创建模拟文本数据"""
        mock_data = []
        
        if dataset_name == 'ms_marco':
            for i in range(100):
                mock_data.append({
                    'query_id': f'query_{i}',
                    'query': f'What is the capital of country {i}?',
                    'passages': [
                        {'text': f'The capital of country {i} is city {i}.', 'is_selected': 1},
                        {'text': f'Country {i} has many cities including city {i}.', 'is_selected': 0}
                    ],
                    'answers': [f'City {i}'],
                    'wellFormedAnswers': [f'The capital is City {i}.']
                })
        elif dataset_name == 'natural_questions':
            for i in range(100):
                mock_data.append({
                    'question_id': f'nq_{i}',
                    'question_text': f'When was event {i} happened?',
                    'document_text': f'Event {i} happened in year {2000 + i}. It was a significant event.',
                    'annotations': [{'short_answers': [f'Year {2000 + i}']}]
                })
        elif dataset_name == 'squad_v2':
            for i in range(100):
                mock_data.append({
                    'id': f'squad_{i}',
                    'title': f'Topic {i}',
                    'context': f'This is context about topic {i}. It contains important information.',
                    'question': f'What is topic {i} about?',
                    'answers': {'text': [f'Topic {i} information'], 'answer_start': [20]}
                })
        
        output_file = os.path.join(output_dir, f'{dataset_name}_mock.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(mock_data, f, ensure_ascii=False, indent=2)
        
        return {
            'dataset_name': dataset_name,
            'total_samples': len(mock_data),
            'output_file': output_file,
            'status': 'mock_data_created'
        }
    
    def _create_mock_image_data(self, output_dir: str, dataset_name: str) -> Dict:
        """创建模拟图像数据"""
        mock_data = []
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        for i in range(50):
            # 创建模拟图像
            image = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
            image_pil = Image.fromarray(image)
            image_path = os.path.join(images_dir, f'{dataset_name}_image_{i}.jpg')
            image_pil.save(image_path)
            
            mock_data.append({
                'image_id': f'{dataset_name}_{i}',
                'image_path': image_path,
                'annotations': [
                    {'category': f'object_{i % 10}', 'bbox': [10, 10, 100, 100]},
                    {'category': f'object_{(i+1) % 10}', 'bbox': [50, 50, 150, 150]}
                ],
                'captions': [f'This is a mock image {i} with objects.']
            })
        
        output_file = os.path.join(output_dir, f'{dataset_name}_mock.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(mock_data, f, ensure_ascii=False, indent=2)
        
        return {
            'dataset_name': dataset_name,
            'total_samples': len(mock_data),
            'output_file': output_file,
            'images_dir': images_dir,
            'status': 'mock_data_created'
        }
    
    def _create_mock_multimodal_data(self, output_dir: str, dataset_name: str) -> Dict:
        """创建模拟多模态数据"""
        mock_data = []
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        for i in range(50):
            # 创建模拟图像
            image = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
            image_pil = Image.fromarray(image)
            image_path = os.path.join(images_dir, f'{dataset_name}_image_{i}.jpg')
            image_pil.save(image_path)
            
            if dataset_name == 'vqa_v2':
                mock_data.append({
                    'question_id': f'vqa_{i}',
                    'image_id': f'image_{i}',
                    'image_path': image_path,
                    'question': f'What color is object {i % 5} in the image?',
                    'answers': [f'Color {i % 7}'],
                    'answer_type': 'other'
                })
            elif dataset_name in ['conceptual_captions', 'flickr30k']:
                mock_data.append({
                    'image_id': f'image_{i}',
                    'image_path': image_path,
                    'caption': f'A mock image showing object {i % 10} in setting {i % 5}.',
                    'url': f'http://mock-url-{i}.com'
                })
        
        output_file = os.path.join(output_dir, f'{dataset_name}_mock.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(mock_data, f, ensure_ascii=False, indent=2)
        
        return {
            'dataset_name': dataset_name,
            'total_samples': len(mock_data),
            'output_file': output_file,
            'images_dir': images_dir,
            'status': 'mock_data_created'
        }
    
    def _ingest_generic_text_dataset(self, dataset_name: str, output_dir: str) -> Dict:
        """通用文本数据集摄取"""
        return self._create_mock_text_data(output_dir, dataset_name)
    
    def _ingest_generic_image_dataset(self, dataset_name: str, output_dir: str) -> Dict:
        """通用图像数据集摄取"""
        return self._create_mock_image_data(output_dir, dataset_name)
    
    def _ingest_generic_multimodal_dataset(self, dataset_name: str, output_dir: str) -> Dict:
        """通用多模态数据集摄取"""
        return self._create_mock_multimodal_data(output_dir, dataset_name)
    
    def get_dataset_info(self, dataset_name: str) -> Dict:
        """获取数据集信息"""
        all_datasets = {
            **self.datasets_config.get('text_datasets', {}),
            **self.datasets_config.get('image_datasets', {}),
            **self.datasets_config.get('multimodal_datasets', {})
        }
        
        return all_datasets.get(dataset_name, {})
    
    def list_supported_datasets(self) -> Dict[str, List[str]]:
        """列出支持的数据集"""
        return {
            'text_datasets': self.supported_text_datasets,
            'image_datasets': self.supported_image_datasets,
            'multimodal_datasets': self.supported_multimodal_datasets
        }

# 使用示例
if __name__ == "__main__":
    # 初始化数据摄取组件
    ingestion = MultimodalDataIngestion()
    
    # 摄取文本数据
    text_result = ingestion.ingest_text_data('ms_marco', 'data/text')
    print(f"文本数据摄取结果: {text_result}")
    
    # 摄取图像数据
    image_result = ingestion.ingest_image_data('coco', 'data/images')
    print(f"图像数据摄取结果: {image_result}")
    
    # 摄取多模态数据
    multimodal_result = ingestion.ingest_multimodal_data('vqa_v2', 'data/multimodal')
    print(f"多模态数据摄取结果: {multimodal_result}")
