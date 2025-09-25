"""
Multimodal Retriever Component for RAG System
支持文本、图像和跨模态检索
"""

import os
import logging
from typing import Dict, List, Optional, Union, Tuple, Any
import numpy as np
import json
from dataclasses import dataclass
from pathlib import Path
import faiss
import pickle
from PIL import Image
import torch

from .multimodal_embedding import MultimodalEmbedding, EmbeddingConfig

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    """检索结果"""
    id: str
    content: Any
    score: float
    metadata: Dict = None

@dataclass
class RetrieverConfig:
    """检索器配置"""
    index_type: str = "flat"  # 'flat', 'ivf', 'hnsw'
    similarity_metric: str = "cosine"  # 'cosine', 'euclidean', 'dot_product'
    top_k: int = 10
    threshold: float = 0.0
    use_gpu: bool = False
    nprobe: int = 10  # for IVF index
    ef_search: int = 64  # for HNSW index

class MultimodalRetriever:
    """多模态检索组件"""
    
    def __init__(self, 
                 embedding_component: MultimodalEmbedding = None,
                 config: RetrieverConfig = None,
                 index_dir: str = "indexes"):
        """
        初始化多模态检索器
        
        Args:
            embedding_component: 嵌入组件
            config: 检索器配置
            index_dir: 索引存储目录
        """
        self.config = config or RetrieverConfig()
        self.embedding = embedding_component or MultimodalEmbedding()
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(exist_ok=True)
        
        # 初始化索引
        self.text_index = None
        self.image_index = None
        self.multimodal_index = None
        
        # 存储数据
        self.text_data = []
        self.image_data = []
        self.multimodal_data = []
        
        # 索引映射
        self.text_id_to_idx = {}
        self.image_id_to_idx = {}
        self.multimodal_id_to_idx = {}
        
        logger.info("多模态检索器初始化完成")
    
    def build_text_index(self, 
                        texts: List[str], 
                        text_ids: List[str] = None,
                        metadata: List[Dict] = None) -> None:
        """
        构建文本索引
        
        Args:
            texts: 文本列表
            text_ids: 文本ID列表
            metadata: 元数据列表
        """
        logger.info(f"构建文本索引，文本数量: {len(texts)}")
        
        # 生成嵌入
        embeddings = self.embedding.batch_encode_text(texts)
        
        # 构建FAISS索引
        dimension = embeddings.shape[1]
        self.text_index = self._create_faiss_index(dimension, len(embeddings))
        self.text_index.add(embeddings.astype(np.float32))
        
        # 存储数据
        self.text_data = []
        for i, text in enumerate(texts):
            text_id = text_ids[i] if text_ids else f"text_{i}"
            self.text_id_to_idx[text_id] = i
            self.text_data.append({
                'id': text_id,
                'content': text,
                'metadata': metadata[i] if metadata else {}
            })
        
        # 保存索引
        self._save_index('text', self.text_index, self.text_data, self.text_id_to_idx)
        logger.info("文本索引构建完成")
    
    def build_image_index(self, 
                         images: List[Union[str, Image.Image]], 
                         image_ids: List[str] = None,
                         metadata: List[Dict] = None) -> None:
        """
        构建图像索引
        
        Args:
            images: 图像列表（路径或PIL Image对象）
            image_ids: 图像ID列表
            metadata: 元数据列表
        """
        logger.info(f"构建图像索引，图像数量: {len(images)}")
        
        # 生成嵌入
        embeddings = self.embedding.batch_encode_image(images)
        
        # 构建FAISS索引
        dimension = embeddings.shape[1]
        self.image_index = self._create_faiss_index(dimension, len(embeddings))
        self.image_index.add(embeddings.astype(np.float32))
        
        # 存储数据
        self.image_data = []
        for i, image in enumerate(images):
            image_id = image_ids[i] if image_ids else f"image_{i}"
            self.image_id_to_idx[image_id] = i
            self.image_data.append({
                'id': image_id,
                'content': image,
                'metadata': metadata[i] if metadata else {}
            })
        
        # 保存索引
        self._save_index('image', self.image_index, self.image_data, self.image_id_to_idx)
        logger.info("图像索引构建完成")
    
    def build_multimodal_index(self, 
                              texts: List[str],
                              images: List[Union[str, Image.Image]],
                              multimodal_ids: List[str] = None,
                              metadata: List[Dict] = None) -> None:
        """
        构建多模态索引
        
        Args:
            texts: 文本列表
            images: 图像列表
            multimodal_ids: 多模态数据ID列表
            metadata: 元数据列表
        """
        logger.info(f"构建多模态索引，数据数量: {len(texts)}")
        
        if len(texts) != len(images):
            raise ValueError("文本和图像数量必须相等")
        
        # 生成多模态嵌入
        embeddings = []
        for text, image in zip(texts, images):
            embedding = self.embedding.encode_multimodal(text, image)
            embeddings.append(embedding[0])  # 取第一个元素（单个样本）
        
        embeddings = np.array(embeddings)
        
        # 构建FAISS索引
        dimension = embeddings.shape[1]
        self.multimodal_index = self._create_faiss_index(dimension, len(embeddings))
        self.multimodal_index.add(embeddings.astype(np.float32))
        
        # 存储数据
        self.multimodal_data = []
        for i, (text, image) in enumerate(zip(texts, images)):
            multimodal_id = multimodal_ids[i] if multimodal_ids else f"multimodal_{i}"
            self.multimodal_id_to_idx[multimodal_id] = i
            self.multimodal_data.append({
                'id': multimodal_id,
                'text': text,
                'image': image,
                'metadata': metadata[i] if metadata else {}
            })
        
        # 保存索引
        self._save_index('multimodal', self.multimodal_index, self.multimodal_data, self.multimodal_id_to_idx)
        logger.info("多模态索引构建完成")
    
    def retrieve_text(self, 
                     query: str, 
                     top_k: int = None,
                     threshold: float = None) -> List[RetrievalResult]:
        """
        文本检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            threshold: 相似度阈值
            
        Returns:
            检索结果列表
        """
        if self.text_index is None:
            logger.warning("文本索引未构建，尝试加载...")
            self._load_index('text')
        
        if self.text_index is None:
            return []
        
        top_k = top_k or self.config.top_k
        threshold = threshold or self.config.threshold
        
        # 生成查询嵌入
        query_embedding = self.embedding.encode_text(query)
        
        # 搜索
        scores, indices = self.text_index.search(
            query_embedding.astype(np.float32), top_k
        )
        
        # 构建结果
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and score >= threshold:
                data = self.text_data[idx]
                results.append(RetrievalResult(
                    id=data['id'],
                    content=data['content'],
                    score=float(score),
                    metadata=data['metadata']
                ))
        
        return results
    
    def retrieve_image(self, 
                      query_image: Union[str, Image.Image], 
                      top_k: int = None,
                      threshold: float = None) -> List[RetrievalResult]:
        """
        图像检索
        
        Args:
            query_image: 查询图像
            top_k: 返回结果数量
            threshold: 相似度阈值
            
        Returns:
            检索结果列表
        """
        if self.image_index is None:
            logger.warning("图像索引未构建，尝试加载...")
            self._load_index('image')
        
        if self.image_index is None:
            return []
        
        top_k = top_k or self.config.top_k
        threshold = threshold or self.config.threshold
        
        # 生成查询嵌入
        query_embedding = self.embedding.encode_image(query_image)
        
        # 搜索
        scores, indices = self.image_index.search(
            query_embedding.astype(np.float32), top_k
        )
        
        # 构建结果
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and score >= threshold:
                data = self.image_data[idx]
                results.append(RetrievalResult(
                    id=data['id'],
                    content=data['content'],
                    score=float(score),
                    metadata=data['metadata']
                ))
        
        return results
    
    def retrieve_cross_modal(self, 
                           text_query: str = None,
                           image_query: Union[str, Image.Image] = None,
                           top_k: int = None,
                           threshold: float = None) -> List[RetrievalResult]:
        """
        跨模态检索
        
        Args:
            text_query: 文本查询
            image_query: 图像查询
            top_k: 返回结果数量
            threshold: 相似度阈值
            
        Returns:
            检索结果列表
        """
        if self.multimodal_index is None:
            logger.warning("多模态索引未构建，尝试加载...")
            self._load_index('multimodal')
        
        if self.multimodal_index is None:
            return []
        
        if text_query is None and image_query is None:
            raise ValueError("至少需要提供文本查询或图像查询")
        
        top_k = top_k or self.config.top_k
        threshold = threshold or self.config.threshold
        
        # 生成查询嵌入
        if text_query and image_query:
            query_embedding = self.embedding.encode_multimodal(text_query, image_query)
        elif text_query:
            # 文本到多模态检索
            query_embedding = self.embedding.encode_text(text_query, model_type="clip")
            # 扩展维度以匹配多模态嵌入
            query_embedding = np.concatenate([query_embedding, np.zeros_like(query_embedding)], axis=-1)
        else:
            # 图像到多模态检索
            query_embedding = self.embedding.encode_image(image_query, model_type="clip")
            # 扩展维度以匹配多模态嵌入
            query_embedding = np.concatenate([np.zeros_like(query_embedding), query_embedding], axis=-1)
        
        # 搜索
        scores, indices = self.multimodal_index.search(
            query_embedding.astype(np.float32), top_k
        )
        
        # 构建结果
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and score >= threshold:
                data = self.multimodal_data[idx]
                results.append(RetrievalResult(
                    id=data['id'],
                    content={'text': data['text'], 'image': data['image']},
                    score=float(score),
                    metadata=data['metadata']
                ))
        
        return results
    
    def hybrid_retrieve(self, 
                       query: str,
                       query_image: Union[str, Image.Image] = None,
                       weights: Dict[str, float] = None,
                       top_k: int = None) -> List[RetrievalResult]:
        """
        混合检索（结合多种检索策略）
        
        Args:
            query: 文本查询
            query_image: 图像查询
            weights: 各检索策略权重
            top_k: 返回结果数量
            
        Returns:
            检索结果列表
        """
        weights = weights or {'text': 0.5, 'image': 0.3, 'multimodal': 0.2}
        top_k = top_k or self.config.top_k
        
        all_results = {}
        
        # 文本检索
        if 'text' in weights and weights['text'] > 0:
            text_results = self.retrieve_text(query, top_k * 2)
            for result in text_results:
                key = f"text_{result.id}"
                all_results[key] = RetrievalResult(
                    id=result.id,
                    content=result.content,
                    score=result.score * weights['text'],
                    metadata={**result.metadata, 'source': 'text'}
                )
        
        # 图像检索
        if query_image and 'image' in weights and weights['image'] > 0:
            image_results = self.retrieve_image(query_image, top_k * 2)
            for result in image_results:
                key = f"image_{result.id}"
                all_results[key] = RetrievalResult(
                    id=result.id,
                    content=result.content,
                    score=result.score * weights['image'],
                    metadata={**result.metadata, 'source': 'image'}
                )
        
        # 跨模态检索
        if 'multimodal' in weights and weights['multimodal'] > 0:
            multimodal_results = self.retrieve_cross_modal(query, query_image, top_k * 2)
            for result in multimodal_results:
                key = f"multimodal_{result.id}"
                all_results[key] = RetrievalResult(
                    id=result.id,
                    content=result.content,
                    score=result.score * weights['multimodal'],
                    metadata={**result.metadata, 'source': 'multimodal'}
                )
        
        # 按分数排序并返回top_k
        sorted_results = sorted(all_results.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:top_k]
    
    def _create_faiss_index(self, dimension: int, num_vectors: int) -> faiss.Index:
        """创建FAISS索引"""
        if self.config.index_type == "flat":
            if self.config.similarity_metric == "cosine":
                index = faiss.IndexFlatIP(dimension)  # Inner Product for cosine
            else:
                index = faiss.IndexFlatL2(dimension)
        elif self.config.index_type == "ivf":
            nlist = min(100, max(1, num_vectors // 100))  # 聚类中心数量
            quantizer = faiss.IndexFlatL2(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
            index.nprobe = self.config.nprobe
        elif self.config.index_type == "hnsw":
            index = faiss.IndexHNSWFlat(dimension, 32)
            index.hnsw.efSearch = self.config.ef_search
        else:
            raise ValueError(f"不支持的索引类型: {self.config.index_type}")
        
        # GPU支持
        if self.config.use_gpu and faiss.get_num_gpus() > 0:
            index = faiss.index_cpu_to_gpu(faiss.StandardGpuResources(), 0, index)
        
        return index
    
    def _save_index(self, index_type: str, index: faiss.Index, data: List, id_mapping: Dict):
        """保存索引和数据"""
        index_path = self.index_dir / f"{index_type}_index.faiss"
        data_path = self.index_dir / f"{index_type}_data.pkl"
        mapping_path = self.index_dir / f"{index_type}_mapping.pkl"
        
        # 保存FAISS索引
        if self.config.use_gpu:
            # 将GPU索引转回CPU再保存
            cpu_index = faiss.index_gpu_to_cpu(index)
            faiss.write_index(cpu_index, str(index_path))
        else:
            faiss.write_index(index, str(index_path))
        
        # 保存数据和映射
        with open(data_path, 'wb') as f:
            pickle.dump(data, f)
        
        with open(mapping_path, 'wb') as f:
            pickle.dump(id_mapping, f)
        
        logger.info(f"已保存{index_type}索引到 {index_path}")
    
    def _load_index(self, index_type: str) -> bool:
        """加载索引和数据"""
        index_path = self.index_dir / f"{index_type}_index.faiss"
        data_path = self.index_dir / f"{index_type}_data.pkl"
        mapping_path = self.index_dir / f"{index_type}_mapping.pkl"
        
        if not all(p.exists() for p in [index_path, data_path, mapping_path]):
            logger.warning(f"{index_type}索引文件不存在")
            return False
        
        try:
            # 加载FAISS索引
            index = faiss.read_index(str(index_path))
            
            # GPU支持
            if self.config.use_gpu and faiss.get_num_gpus() > 0:
                index = faiss.index_cpu_to_gpu(faiss.StandardGpuResources(), 0, index)
            
            # 加载数据和映射
            with open(data_path, 'rb') as f:
                data = pickle.load(f)
            
            with open(mapping_path, 'rb') as f:
                id_mapping = pickle.load(f)
            
            # 设置属性
            if index_type == 'text':
                self.text_index = index
                self.text_data = data
                self.text_id_to_idx = id_mapping
            elif index_type == 'image':
                self.image_index = index
                self.image_data = data
                self.image_id_to_idx = id_mapping
            elif index_type == 'multimodal':
                self.multimodal_index = index
                self.multimodal_data = data
                self.multimodal_id_to_idx = id_mapping
            
            logger.info(f"已加载{index_type}索引")
            return True
            
        except Exception as e:
            logger.error(f"加载{index_type}索引失败: {str(e)}")
            return False
    
    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        stats = {}
        
        if self.text_index:
            stats['text'] = {
                'total_vectors': self.text_index.ntotal,
                'dimension': self.text_index.d,
                'is_trained': self.text_index.is_trained
            }
        
        if self.image_index:
            stats['image'] = {
                'total_vectors': self.image_index.ntotal,
                'dimension': self.image_index.d,
                'is_trained': self.image_index.is_trained
            }
        
        if self.multimodal_index:
            stats['multimodal'] = {
                'total_vectors': self.multimodal_index.ntotal,
                'dimension': self.multimodal_index.d,
                'is_trained': self.multimodal_index.is_trained
            }
        
        return stats

# 使用示例
if __name__ == "__main__":
    # 初始化检索器
    retriever = MultimodalRetriever()
    
    # 构建文本索引
    texts = ["Hello world", "How are you?", "Machine learning is great"]
    retriever.build_text_index(texts)
    
    # 文本检索
    results = retriever.retrieve_text("Hello")
    print(f"文本检索结果: {len(results)}")
    for result in results:
        print(f"  - {result.id}: {result.content} (score: {result.score:.3f})")
    
    # 获取索引统计
    stats = retriever.get_index_stats()
    print(f"索引统计: {stats}")
