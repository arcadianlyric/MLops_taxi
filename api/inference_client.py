#!/usr/bin/env python3
"""
KFServing 在线推理客户端
实现与 KFServing 推理服务的交互
"""

import json
import requests
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import asyncio
import aiohttp
from feast import FeatureStore

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KFServingInferenceClient:
    """KFServing 在线推理客户端"""
    
    def __init__(self, 
                 service_url: str = "http://movie-recommendation-model.default.svc.cluster.local",
                 feast_repo_path: str = "./feast/feature_repo",
                 timeout: int = 30):
        """
        初始化推理客户端
        
        Args:
            service_url: KFServing 服务地址
            feast_repo_path: Feast 特征仓库路径
            timeout: 请求超时时间
        """
        self.service_url = service_url
        self.predict_url = f"{service_url}/v1/models/movie-recommendation:predict"
        self.timeout = timeout
        
        # 初始化 Feast 客户端
        try:
            self.feast_store = FeatureStore(repo_path=feast_repo_path)
            logger.info("✅ Feast 特征仓库连接成功")
        except Exception as e:
            logger.warning(f"⚠️ Feast 连接失败: {e}")
            self.feast_store = None
    
    def get_features_from_feast(self, user_ids: List[int], movie_ids: List[int]) -> Dict[str, Any]:
        """
        从 Feast 获取特征
        
        Args:
            user_ids: 用户ID列表
            movie_ids: 电影ID列表
            
        Returns:
            特征字典
        """
        if not self.feast_store:
            logger.warning("Feast 未连接，使用模拟特征")
            return self._get_mock_features(user_ids, movie_ids)
        
        try:
            # 构建实体数据
            entity_df = pd.DataFrame({
                "user_id": user_ids,
                "movie_id": movie_ids,
                "event_timestamp": [datetime.now()] * len(user_ids)
            })
            
            # 获取特征
            features = self.feast_store.get_online_features(
                features=[
                    "user_features:age",
                    "user_features:gender", 
                    "user_features:occupation",
                    "movie_features:genre",
                    "movie_features:year",
                    "movie_features:rating_avg"
                ],
                entity_df=entity_df
            ).to_dict()
            
            logger.info(f"✅ 从 Feast 获取 {len(user_ids)} 条特征")
            return features
            
        except Exception as e:
            logger.error(f"❌ Feast 特征获取失败: {e}")
            return self._get_mock_features(user_ids, movie_ids)
    
    def _get_mock_features(self, user_ids: List[int], movie_ids: List[int]) -> Dict[str, Any]:
        """生成模拟特征数据"""
        return {
            "user_age": [25 + (uid % 40) for uid in user_ids],
            "user_gender": [uid % 2 for uid in user_ids],
            "user_occupation": [uid % 21 for uid in user_ids],
            "movie_genre": [mid % 19 for mid in movie_ids],
            "movie_year": [1990 + (mid % 30) for mid in movie_ids],
            "movie_rating_avg": [3.0 + (mid % 3) for mid in movie_ids]
        }
    
    def preprocess_features(self, features: Dict[str, Any]) -> np.ndarray:
        """
        预处理特征数据
        
        Args:
            features: 原始特征字典
            
        Returns:
            预处理后的特征数组
        """
        # 特征标准化和编码
        feature_vector = []
        
        # 用户特征
        user_age = np.array(features.get("user_age", [25]))
        user_gender = np.array(features.get("user_gender", [0]))
        user_occupation = np.array(features.get("user_occupation", [0]))
        
        # 电影特征  
        movie_genre = np.array(features.get("movie_genre", [0]))
        movie_year = np.array(features.get("movie_year", [2000]))
        movie_rating = np.array(features.get("movie_rating_avg", [3.5]))
        
        # 组合特征向量
        feature_vector = np.column_stack([
            user_age / 100.0,  # 年龄标准化
            user_gender,       # 性别 (0/1)
            user_occupation / 21.0,  # 职业标准化
            movie_genre / 19.0,      # 类型标准化
            (movie_year - 1900) / 100.0,  # 年份标准化
            movie_rating / 5.0       # 评分标准化
        ])
        
        return feature_vector.astype(np.float32)
    
    def predict(self, user_ids: List[int], movie_ids: List[int]) -> Dict[str, Any]:
        """
        执行在线推理
        
        Args:
            user_ids: 用户ID列表
            movie_ids: 电影ID列表
            
        Returns:
            推理结果
        """
        try:
            # 1. 获取特征
            logger.info(f"🔍 获取特征: users={user_ids}, movies={movie_ids}")
            features = self.get_features_from_feast(user_ids, movie_ids)
            
            # 2. 预处理特征
            processed_features = self.preprocess_features(features)
            
            # 3. 构建推理请求
            request_data = {
                "instances": processed_features.tolist()
            }
            
            # 4. 发送推理请求
            logger.info(f"🚀 发送推理请求到: {self.predict_url}")
            response = requests.post(
                self.predict_url,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            # 5. 解析响应
            predictions = response.json()
            
            # 6. 后处理结果
            processed_predictions = self._postprocess_predictions(
                predictions, user_ids, movie_ids
            )
            
            logger.info(f"✅ 推理完成，返回 {len(processed_predictions)} 个结果")
            return processed_predictions
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 推理请求失败: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 推理过程出错: {e}")
            raise
    
    def _postprocess_predictions(self, 
                                predictions: Dict[str, Any], 
                                user_ids: List[int], 
                                movie_ids: List[int]) -> List[Dict[str, Any]]:
        """后处理推理结果"""
        results = []
        prediction_scores = predictions.get("predictions", [])
        
        for i, (user_id, movie_id, score) in enumerate(zip(user_ids, movie_ids, prediction_scores)):
            # 如果是多输出模型，取第一个输出
            if isinstance(score, list):
                score = score[0] if score else 0.0
            
            results.append({
                "user_id": user_id,
                "movie_id": movie_id,
                "prediction_score": float(score),
                "recommendation": score > 0.5,  # 阈值可配置
                "confidence": abs(float(score) - 0.5) * 2,  # 置信度
                "timestamp": datetime.now().isoformat()
            })
        
        return results
    
    async def predict_async(self, user_ids: List[int], movie_ids: List[int]) -> Dict[str, Any]:
        """异步推理接口"""
        try:
            # 获取特征
            features = self.get_features_from_feast(user_ids, movie_ids)
            processed_features = self.preprocess_features(features)
            
            request_data = {
                "instances": processed_features.tolist()
            }
            
            # 异步HTTP请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.predict_url,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response.raise_for_status()
                    predictions = await response.json()
            
            processed_predictions = self._postprocess_predictions(
                predictions, user_ids, movie_ids
            )
            
            return processed_predictions
            
        except Exception as e:
            logger.error(f"❌ 异步推理失败: {e}")
            raise
    
    def batch_predict(self, requests: List[Dict[str, List[int]]], batch_size: int = 32) -> List[Dict[str, Any]]:
        """批量推理"""
        all_results = []
        
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            
            # 合并批次数据
            batch_user_ids = []
            batch_movie_ids = []
            
            for req in batch:
                batch_user_ids.extend(req["user_ids"])
                batch_movie_ids.extend(req["movie_ids"])
            
            # 执行批量推理
            try:
                batch_results = self.predict(batch_user_ids, batch_movie_ids)
                all_results.extend(batch_results)
                logger.info(f"✅ 批次 {i//batch_size + 1} 推理完成")
            except Exception as e:
                logger.error(f"❌ 批次 {i//batch_size + 1} 推理失败: {e}")
                continue
        
        return all_results
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            health_url = f"{self.service_url}/v1/models/movie-recommendation"
            response = requests.get(health_url, timeout=10)
            return response.status_code == 200
        except:
            return False

# 使用示例
if __name__ == "__main__":
    # 初始化客户端
    client = KFServingInferenceClient()
    
    # 健康检查
    if client.health_check():
        print("✅ KFServing 服务健康")
    else:
        print("❌ KFServing 服务不可用")
    
    # 单次推理示例
    try:
        results = client.predict(
            user_ids=[1, 2, 3],
            movie_ids=[101, 102, 103]
        )
        
        print("🎯 推理结果:")
        for result in results:
            print(f"用户 {result['user_id']} 对电影 {result['movie_id']} 的推荐分数: {result['prediction_score']:.3f}")
            
    except Exception as e:
        print(f"❌ 推理失败: {e}")
