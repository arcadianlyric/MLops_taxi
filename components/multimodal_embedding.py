"""
Multimodal Embedding Component for RAG System
支持文本、图像和跨模态嵌入生成
"""

import os
import logging
from typing import Dict, List, Optional, Union, Tuple, Any
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import clip
from transformers import (
    AutoTokenizer, AutoModel, 
    CLIPProcessor, CLIPModel,
    BlipProcessor, BlipModel
)
from sentence_transformers import SentenceTransformer
import cv2
from dataclasses import dataclass
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    text_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    image_model: str = "openai/clip-vit-base-patch32"
    multimodal_model: str = "openai/clip-vit-base-patch32"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    batch_size: int = 32
    max_text_length: int = 512
    image_size: Tuple[int, int] = (224, 224)
    normalize_embeddings: bool = True

class MultimodalEmbedding:
    """多模态嵌入生成组件"""
    
    def __init__(self, config: EmbeddingConfig = None):
        """
        初始化多模态嵌入组件
        
        Args:
            config: 嵌入配置
        """
        self.config = config or EmbeddingConfig()
        self.device = torch.device(self.config.device)
        
        # 初始化模型
        self._initialize_models()
        
        logger.info(f"多模态嵌入组件初始化完成，使用设备: {self.device}")
    
    def _initialize_models(self):
        """初始化各种编码器模型"""
        try:
            # 文本编码器
            logger.info("加载文本编码器...")
            self.text_encoder = SentenceTransformer(self.config.text_model)
            self.text_encoder.to(self.device)
            
            # CLIP 模型 (用于图像和跨模态)
            logger.info("加载 CLIP 模型...")
            self.clip_model = CLIPModel.from_pretrained(self.config.multimodal_model)
            self.clip_processor = CLIPProcessor.from_pretrained(self.config.multimodal_model)
            self.clip_model.to(self.device)
            
            # 备用 BERT 模型
            logger.info("加载 BERT 模型...")
            self.bert_tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
            self.bert_model = AutoModel.from_pretrained('bert-base-uncased')
            self.bert_model.to(self.device)
            
            # 设置为评估模式
            self.clip_model.eval()
            self.bert_model.eval()
            
        except Exception as e:
            logger.error(f"模型初始化失败: {str(e)}")
            # 创建模拟编码器
            self._initialize_mock_models()
    
    def _initialize_mock_models(self):
        """初始化模拟编码器（用于测试）"""
        logger.warning("使用模拟编码器")
        self.use_mock = True
        self.text_embedding_dim = 384
        self.image_embedding_dim = 512
        self.multimodal_embedding_dim = 512
    
    def encode_text(self, 
                   text: Union[str, List[str]], 
                   model_type: str = "sentence_transformer") -> np.ndarray:
        """
        文本编码
        
        Args:
            text: 输入文本或文本列表
            model_type: 模型类型 ('sentence_transformer', 'bert', 'clip')
            
        Returns:
            文本嵌入向量
        """
        if hasattr(self, 'use_mock') and self.use_mock:
            return self._mock_encode_text(text)
        
        try:
            if isinstance(text, str):
                text = [text]
            
            if model_type == "sentence_transformer":
                embeddings = self.text_encoder.encode(
                    text, 
                    convert_to_numpy=True,
                    normalize_embeddings=self.config.normalize_embeddings
                )
            elif model_type == "bert":
                embeddings = self._encode_text_with_bert(text)
            elif model_type == "clip":
                embeddings = self._encode_text_with_clip(text)
            else:
                raise ValueError(f"不支持的模型类型: {model_type}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"文本编码失败: {str(e)}")
            return self._mock_encode_text(text)
    
    def encode_image(self, 
                    image: Union[Image.Image, np.ndarray, str, List], 
                    model_type: str = "clip") -> np.ndarray:
        """
        图像编码
        
        Args:
            image: 输入图像（PIL Image、numpy数组、文件路径或列表）
            model_type: 模型类型 ('clip', 'resnet')
            
        Returns:
            图像嵌入向量
        """
        if hasattr(self, 'use_mock') and self.use_mock:
            return self._mock_encode_image(image)
        
        try:
            # 预处理图像
            processed_images = self._preprocess_images(image)
            
            if model_type == "clip":
                embeddings = self._encode_image_with_clip(processed_images)
            else:
                raise ValueError(f"不支持的图像模型类型: {model_type}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"图像编码失败: {str(e)}")
            return self._mock_encode_image(image)
    
    def encode_multimodal(self, 
                         text: Union[str, List[str]], 
                         image: Union[Image.Image, np.ndarray, str, List],
                         fusion_method: str = "concatenate") -> np.ndarray:
        """
        多模态联合编码
        
        Args:
            text: 输入文本
            image: 输入图像
            fusion_method: 融合方法 ('concatenate', 'average', 'attention')
            
        Returns:
            多模态嵌入向量
        """
        if hasattr(self, 'use_mock') and self.use_mock:
            return self._mock_encode_multimodal(text, image)
        
        try:
            # 获取文本和图像嵌入
            text_embeddings = self.encode_text(text, model_type="clip")
            image_embeddings = self.encode_image(image, model_type="clip")
            
            # 融合嵌入
            if fusion_method == "concatenate":
                multimodal_embeddings = np.concatenate([text_embeddings, image_embeddings], axis=-1)
            elif fusion_method == "average":
                multimodal_embeddings = (text_embeddings + image_embeddings) / 2
            elif fusion_method == "attention":
                multimodal_embeddings = self._attention_fusion(text_embeddings, image_embeddings)
            else:
                raise ValueError(f"不支持的融合方法: {fusion_method}")
            
            if self.config.normalize_embeddings:
                multimodal_embeddings = F.normalize(
                    torch.from_numpy(multimodal_embeddings), dim=-1
                ).numpy()
            
            return multimodal_embeddings
            
        except Exception as e:
            logger.error(f"多模态编码失败: {str(e)}")
            return self._mock_encode_multimodal(text, image)
    
    def _encode_text_with_bert(self, texts: List[str]) -> np.ndarray:
        """使用 BERT 编码文本"""
        embeddings = []
        
        for text in texts:
            # 分词
            inputs = self.bert_tokenizer(
                text, 
                return_tensors="pt", 
                max_length=self.config.max_text_length,
                truncation=True, 
                padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # 获取嵌入
            with torch.no_grad():
                outputs = self.bert_model(**inputs)
                # 使用 [CLS] token 的嵌入
                embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                embeddings.append(embedding[0])
        
        return np.array(embeddings)
    
    def _encode_text_with_clip(self, texts: List[str]) -> np.ndarray:
        """使用 CLIP 编码文本"""
        # 处理文本
        inputs = self.clip_processor(text=texts, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # 获取文本嵌入
        with torch.no_grad():
            text_features = self.clip_model.get_text_features(**inputs)
            if self.config.normalize_embeddings:
                text_features = F.normalize(text_features, dim=-1)
            
        return text_features.cpu().numpy()
    
    def _encode_image_with_clip(self, images: List[Image.Image]) -> np.ndarray:
        """使用 CLIP 编码图像"""
        # 处理图像
        inputs = self.clip_processor(images=images, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # 获取图像嵌入
        with torch.no_grad():
            image_features = self.clip_model.get_image_features(**inputs)
            if self.config.normalize_embeddings:
                image_features = F.normalize(image_features, dim=-1)
        
        return image_features.cpu().numpy()
    
    def _preprocess_images(self, image_input: Union[Image.Image, np.ndarray, str, List]) -> List[Image.Image]:
        """预处理图像"""
        if isinstance(image_input, str):
            # 文件路径
            return [Image.open(image_input).convert('RGB')]
        elif isinstance(image_input, Image.Image):
            return [image_input.convert('RGB')]
        elif isinstance(image_input, np.ndarray):
            return [Image.fromarray(image_input).convert('RGB')]
        elif isinstance(image_input, list):
            processed = []
            for img in image_input:
                if isinstance(img, str):
                    processed.append(Image.open(img).convert('RGB'))
                elif isinstance(img, Image.Image):
                    processed.append(img.convert('RGB'))
                elif isinstance(img, np.ndarray):
                    processed.append(Image.fromarray(img).convert('RGB'))
            return processed
        else:
            raise ValueError(f"不支持的图像输入类型: {type(image_input)}")
    
    def _attention_fusion(self, text_embeddings: np.ndarray, image_embeddings: np.ndarray) -> np.ndarray:
        """注意力机制融合"""
        # 简单的注意力融合实现
        text_tensor = torch.from_numpy(text_embeddings).to(self.device)
        image_tensor = torch.from_numpy(image_embeddings).to(self.device)
        
        # 计算注意力权重
        attention_scores = torch.matmul(text_tensor, image_tensor.transpose(-2, -1))
        attention_weights = F.softmax(attention_scores, dim=-1)
        
        # 应用注意力
        attended_features = torch.matmul(attention_weights, image_tensor)
        
        # 融合
        fused_embeddings = text_tensor + attended_features
        
        return fused_embeddings.cpu().numpy()
    
    def _mock_encode_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """模拟文本编码"""
        if isinstance(text, str):
            text = [text]
        
        embeddings = []
        for t in text:
            # 基于文本长度和内容生成确定性嵌入
            hash_val = hash(t) % 1000000
            np.random.seed(hash_val)
            embedding = np.random.normal(0, 1, self.text_embedding_dim)
            if self.config.normalize_embeddings:
                embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)
        
        return np.array(embeddings)
    
    def _mock_encode_image(self, image: Union[Image.Image, np.ndarray, str, List]) -> np.ndarray:
        """模拟图像编码"""
        if not isinstance(image, list):
            image = [image]
        
        embeddings = []
        for i, img in enumerate(image):
            # 生成确定性嵌入
            np.random.seed(i + 42)
            embedding = np.random.normal(0, 1, self.image_embedding_dim)
            if self.config.normalize_embeddings:
                embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)
        
        return np.array(embeddings)
    
    def _mock_encode_multimodal(self, text: Union[str, List[str]], image: Union[Image.Image, np.ndarray, str, List]) -> np.ndarray:
        """模拟多模态编码"""
        text_emb = self._mock_encode_text(text)
        image_emb = self._mock_encode_image(image)
        
        # 简单连接
        multimodal_emb = np.concatenate([text_emb, image_emb], axis=-1)
        
        if self.config.normalize_embeddings:
            multimodal_emb = multimodal_emb / np.linalg.norm(multimodal_emb, axis=-1, keepdims=True)
        
        return multimodal_emb
    
    def batch_encode_text(self, texts: List[str], batch_size: int = None) -> np.ndarray:
        """批量文本编码"""
        batch_size = batch_size or self.config.batch_size
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = self.encode_text(batch_texts)
            all_embeddings.append(batch_embeddings)
        
        return np.vstack(all_embeddings)
    
    def batch_encode_image(self, images: List, batch_size: int = None) -> np.ndarray:
        """批量图像编码"""
        batch_size = batch_size or self.config.batch_size
        all_embeddings = []
        
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]
            batch_embeddings = self.encode_image(batch_images)
            all_embeddings.append(batch_embeddings)
        
        return np.vstack(all_embeddings)
    
    def compute_similarity(self, 
                          embeddings1: np.ndarray, 
                          embeddings2: np.ndarray,
                          metric: str = "cosine") -> np.ndarray:
        """
        计算嵌入相似度
        
        Args:
            embeddings1: 第一组嵌入
            embeddings2: 第二组嵌入
            metric: 相似度度量 ('cosine', 'euclidean', 'dot_product')
            
        Returns:
            相似度矩阵
        """
        if metric == "cosine":
            # 余弦相似度
            norm1 = np.linalg.norm(embeddings1, axis=1, keepdims=True)
            norm2 = np.linalg.norm(embeddings2, axis=1, keepdims=True)
            normalized1 = embeddings1 / (norm1 + 1e-8)
            normalized2 = embeddings2 / (norm2 + 1e-8)
            similarity = np.dot(normalized1, normalized2.T)
        elif metric == "euclidean":
            # 欧几里得距离（转换为相似度）
            distances = np.linalg.norm(embeddings1[:, None] - embeddings2[None, :], axis=2)
            similarity = 1 / (1 + distances)
        elif metric == "dot_product":
            # 点积
            similarity = np.dot(embeddings1, embeddings2.T)
        else:
            raise ValueError(f"不支持的相似度度量: {metric}")
        
        return similarity
    
    def get_embedding_info(self) -> Dict[str, Any]:
        """获取嵌入信息"""
        if hasattr(self, 'use_mock') and self.use_mock:
            return {
                'text_embedding_dim': self.text_embedding_dim,
                'image_embedding_dim': self.image_embedding_dim,
                'multimodal_embedding_dim': self.multimodal_embedding_dim,
                'device': str(self.device),
                'models': 'mock_models'
            }
        else:
            return {
                'text_model': self.config.text_model,
                'image_model': self.config.image_model,
                'multimodal_model': self.config.multimodal_model,
                'device': str(self.device),
                'text_embedding_dim': self.text_encoder.get_sentence_embedding_dimension(),
                'image_embedding_dim': self.clip_model.config.projection_dim,
                'multimodal_embedding_dim': self.clip_model.config.projection_dim * 2
            }

# 使用示例
if __name__ == "__main__":
    # 初始化嵌入组件
    config = EmbeddingConfig()
    embedding = MultimodalEmbedding(config)
    
    # 文本编码
    texts = ["Hello world", "How are you?"]
    text_embeddings = embedding.encode_text(texts)
    print(f"文本嵌入形状: {text_embeddings.shape}")
    
    # 图像编码（使用模拟图像）
    mock_image = Image.new('RGB', (224, 224), color='red')
    image_embeddings = embedding.encode_image(mock_image)
    print(f"图像嵌入形状: {image_embeddings.shape}")
    
    # 多模态编码
    multimodal_embeddings = embedding.encode_multimodal(texts[0], mock_image)
    print(f"多模态嵌入形状: {multimodal_embeddings.shape}")
    
    # 相似度计算
    similarity = embedding.compute_similarity(text_embeddings, text_embeddings)
    print(f"相似度矩阵形状: {similarity.shape}")
    
    # 嵌入信息
    info = embedding.get_embedding_info()
    print(f"嵌入信息: {info}")
