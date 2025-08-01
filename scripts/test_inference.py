#!/usr/bin/env python3
"""
KFServing 在线推理测试脚本
测试推理服务的各种功能
"""

import sys
import os
import time
import asyncio
from typing import List, Dict

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.inference_client import KFServingInferenceClient

def test_health_check(client: KFServingInferenceClient):
    """测试健康检查"""
    print("🏥 测试健康检查...")
    is_healthy = client.health_check()
    if is_healthy:
        print("✅ KFServing 服务健康")
    else:
        print("❌ KFServing 服务不可用")
    return is_healthy

def test_single_prediction(client: KFServingInferenceClient):
    """测试单次推理"""
    print("\n🎯 测试单次推理...")
    
    try:
        # 测试数据
        user_ids = [1, 2, 3]
        movie_ids = [101, 102, 103]
        
        print(f"📊 输入数据: 用户={user_ids}, 电影={movie_ids}")
        
        # 执行推理
        start_time = time.time()
        results = client.predict(user_ids, movie_ids)
        end_time = time.time()
        
        # 显示结果
        print(f"⏱️ 推理耗时: {(end_time - start_time)*1000:.2f}ms")
        print("🎯 推理结果:")
        
        for result in results:
            print(f"  用户 {result['user_id']} 对电影 {result['movie_id']}:")
            print(f"    推荐分数: {result['prediction_score']:.3f}")
            print(f"    是否推荐: {'是' if result['recommendation'] else '否'}")
            print(f"    置信度: {result['confidence']:.3f}")
            print(f"    时间戳: {result['timestamp']}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ 单次推理测试失败: {e}")
        return False

def test_batch_prediction(client: KFServingInferenceClient):
    """测试批量推理"""
    print("\n📦 测试批量推理...")
    
    try:
        # 构建批量请求
        batch_requests = [
            {"user_ids": [1, 2], "movie_ids": [101, 102]},
            {"user_ids": [3, 4], "movie_ids": [103, 104]},
            {"user_ids": [5, 6], "movie_ids": [105, 106]},
        ]
        
        print(f"📊 批量请求数量: {len(batch_requests)}")
        
        # 执行批量推理
        start_time = time.time()
        results = client.batch_predict(batch_requests, batch_size=2)
        end_time = time.time()
        
        print(f"⏱️ 批量推理耗时: {(end_time - start_time)*1000:.2f}ms")
        print(f"🎯 批量推理结果数量: {len(results)}")
        
        # 显示部分结果
        for i, result in enumerate(results[:3]):  # 只显示前3个
            print(f"  结果 {i+1}: 用户{result['user_id']} -> 电影{result['movie_id']} = {result['prediction_score']:.3f}")
        
        if len(results) > 3:
            print(f"  ... 还有 {len(results) - 3} 个结果")
        
        return True
        
    except Exception as e:
        print(f"❌ 批量推理测试失败: {e}")
        return False

async def test_async_prediction(client: KFServingInferenceClient):
    """测试异步推理"""
    print("\n⚡ 测试异步推理...")
    
    try:
        user_ids = [10, 11, 12]
        movie_ids = [201, 202, 203]
        
        print(f"📊 异步输入数据: 用户={user_ids}, 电影={movie_ids}")
        
        # 执行异步推理
        start_time = time.time()
        results = await client.predict_async(user_ids, movie_ids)
        end_time = time.time()
        
        print(f"⏱️ 异步推理耗时: {(end_time - start_time)*1000:.2f}ms")
        print(f"🎯 异步推理结果数量: {len(results)}")
        
        # 显示结果
        for result in results:
            print(f"  用户 {result['user_id']} -> 电影 {result['movie_id']}: {result['prediction_score']:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 异步推理测试失败: {e}")
        return False

def test_performance(client: KFServingInferenceClient, num_requests: int = 10):
    """性能测试"""
    print(f"\n🚀 性能测试 ({num_requests} 次请求)...")
    
    try:
        total_time = 0
        successful_requests = 0
        
        for i in range(num_requests):
            user_ids = [i + 1]
            movie_ids = [100 + i]
            
            try:
                start_time = time.time()
                results = client.predict(user_ids, movie_ids)
                end_time = time.time()
                
                total_time += (end_time - start_time)
                successful_requests += 1
                
                if (i + 1) % 5 == 0:
                    print(f"  完成 {i + 1}/{num_requests} 次请求...")
                    
            except Exception as e:
                print(f"  请求 {i + 1} 失败: {e}")
        
        if successful_requests > 0:
            avg_latency = (total_time / successful_requests) * 1000
            qps = successful_requests / total_time if total_time > 0 else 0
            
            print(f"📊 性能测试结果:")
            print(f"  成功请求: {successful_requests}/{num_requests}")
            print(f"  平均延迟: {avg_latency:.2f}ms")
            print(f"  QPS: {qps:.2f}")
            print(f"  成功率: {(successful_requests/num_requests)*100:.1f}%")
        
        return successful_requests > 0
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False

def test_error_handling(client: KFServingInferenceClient):
    """测试错误处理"""
    print("\n🛠️ 测试错误处理...")
    
    test_cases = [
        {
            "name": "空输入",
            "user_ids": [],
            "movie_ids": []
        },
        {
            "name": "不匹配长度",
            "user_ids": [1, 2],
            "movie_ids": [101]
        },
        {
            "name": "无效ID",
            "user_ids": [-1],
            "movie_ids": [-1]
        }
    ]
    
    for test_case in test_cases:
        try:
            print(f"  测试 {test_case['name']}...")
            results = client.predict(test_case['user_ids'], test_case['movie_ids'])
            print(f"    ✅ 处理成功: {len(results)} 个结果")
        except Exception as e:
            print(f"    ⚠️ 预期错误: {str(e)[:50]}...")

def main():
    """主测试函数"""
    print("🧪 KFServing 在线推理测试套件")
    print("=" * 50)
    
    # 初始化客户端
    print("🔧 初始化推理客户端...")
    client = KFServingInferenceClient(
        service_url="http://localhost:8080",  # 本地测试地址
        feast_repo_path="./feast/feature_repo"
    )
    
    # 测试套件
    tests = [
        ("健康检查", lambda: test_health_check(client)),
        ("单次推理", lambda: test_single_prediction(client)),
        ("批量推理", lambda: test_batch_prediction(client)),
        ("异步推理", lambda: asyncio.run(test_async_prediction(client))),
        ("性能测试", lambda: test_performance(client, 5)),
        ("错误处理", lambda: test_error_handling(client))
    ]
    
    # 执行测试
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            if test_func():
                passed += 1
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    # 测试总结
    print(f"\n{'='*50}")
    print(f"🎯 测试总结: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！KFServing 在线推理服务运行正常")
    else:
        print("⚠️ 部分测试失败，请检查服务配置")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
