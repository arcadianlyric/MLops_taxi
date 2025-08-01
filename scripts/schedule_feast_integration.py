#!/usr/bin/env python3
"""
Feast 集成调度脚本
模拟生产环境中的特征工程调度（如 Airflow DAG、Kubeflow Pipeline、Cron Job）
"""

import os
import sys
import time
import logging
import schedule
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import yaml
import json

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from feast.feast_integration_pipeline import FeastIntegrationPipeline


class FeastScheduler:
    """
    Feast 特征工程调度器
    
    模拟生产环境中的调度系统，如：
    - Apache Airflow DAG
    - Kubeflow Pipeline
    - Kubernetes CronJob
    - Jenkins Pipeline
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化调度器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or "feast/integration_config.yaml"
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化管道
        self.pipeline = FeastIntegrationPipeline(self.config_path)
        
        # 调度状态
        self.is_running = False
        self.last_run_time = None
        self.last_run_status = None
        self.run_count = 0
        self.error_count = 0
        
        # 设置日志
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.warning(f"加载配置失败，使用默认配置: {e}")
            return {
                "scheduling": {
                    "feature_refresh_interval": "1h",
                    "materialization_interval": "6h"
                }
            }
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get("monitoring", {}).get("logging", {})
        
        log_level = getattr(logging, log_config.get("level", "INFO"))
        log_format = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_file = log_config.get("file", "logs/feast_scheduler.log")
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 配置日志
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def run_feature_refresh(self):
        """运行特征刷新任务"""
        self.logger.info("开始运行特征刷新任务")
        
        start_time = datetime.now()
        
        try:
            # 运行 Feast 集成管道
            success = self.pipeline.run_pipeline()
            
            # 更新状态
            self.last_run_time = start_time
            self.last_run_status = "success" if success else "failed"
            self.run_count += 1
            
            if not success:
                self.error_count += 1
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if success:
                self.logger.info(f"特征刷新任务完成，耗时: {duration:.2f} 秒")
            else:
                self.logger.error(f"特征刷新任务失败，耗时: {duration:.2f} 秒")
            
            # 记录指标
            self._record_metrics(success, duration)
            
        except Exception as e:
            self.error_count += 1
            self.last_run_status = "error"
            self.logger.error(f"特征刷新任务异常: {e}")
    
    def run_materialization(self):
        """运行特征物化任务"""
        self.logger.info("开始运行特征物化任务")
        
        try:
            # 这里可以调用 Feast 的物化功能
            # 在实际环境中，这会触发 feast materialize 命令
            self.logger.info("特征物化任务完成")
            
        except Exception as e:
            self.logger.error(f"特征物化任务失败: {e}")
    
    def _record_metrics(self, success: bool, duration: float):
        """记录指标"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "duration_seconds": duration,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / self.run_count if self.run_count > 0 else 0
        }
        
        # 保存指标到文件
        metrics_file = "logs/feast_metrics.json"
        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
        
        try:
            # 读取现有指标
            if os.path.exists(metrics_file):
                with open(metrics_file, 'r') as f:
                    all_metrics = json.load(f)
            else:
                all_metrics = []
            
            # 添加新指标
            all_metrics.append(metrics)
            
            # 保留最近100条记录
            all_metrics = all_metrics[-100:]
            
            # 保存指标
            with open(metrics_file, 'w') as f:
                json.dump(all_metrics, f, indent=2)
                
        except Exception as e:
            self.logger.warning(f"保存指标失败: {e}")
    
    def setup_schedule(self):
        """设置调度任务"""
        scheduling_config = self.config.get("scheduling", {})
        
        # 特征刷新间隔
        refresh_interval = scheduling_config.get("feature_refresh_interval", "1h")
        
        # 物化间隔
        materialization_interval = scheduling_config.get("materialization_interval", "6h")
        
        # 解析间隔并设置调度
        if refresh_interval.endswith('h'):
            hours = int(refresh_interval[:-1])
            schedule.every(hours).hours.do(self.run_feature_refresh)
            self.logger.info(f"设置特征刷新调度: 每 {hours} 小时")
        elif refresh_interval.endswith('m'):
            minutes = int(refresh_interval[:-1])
            schedule.every(minutes).minutes.do(self.run_feature_refresh)
            self.logger.info(f"设置特征刷新调度: 每 {minutes} 分钟")
        
        if materialization_interval.endswith('h'):
            hours = int(materialization_interval[:-1])
            schedule.every(hours).hours.do(self.run_materialization)
            self.logger.info(f"设置特征物化调度: 每 {hours} 小时")
        
        # 添加健康检查任务
        schedule.every(10).minutes.do(self.health_check)
        self.logger.info("设置健康检查调度: 每 10 分钟")
    
    def health_check(self):
        """健康检查"""
        try:
            status = self.pipeline.get_pipeline_status()
            
            # 检查关键组件
            if not status.get("feast_available", False):
                self.logger.warning("Feast 不可用")
            
            if not status.get("redis_connected", False):
                self.logger.warning("Redis 连接失败")
            
            # 检查错误率
            error_rate = self.error_count / self.run_count if self.run_count > 0 else 0
            error_threshold = self.config.get("monitoring", {}).get("alerts", {}).get("error_rate_threshold", 0.05)
            
            if error_rate > error_threshold:
                self.logger.warning(f"错误率过高: {error_rate:.2%} > {error_threshold:.2%}")
            
            self.logger.debug("健康检查完成")
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
    
    def start_scheduler(self):
        """启动调度器"""
        if self.is_running:
            self.logger.warning("调度器已在运行")
            return
        
        self.is_running = True
        self.logger.info("启动 Feast 特征工程调度器")
        
        # 设置调度
        self.setup_schedule()
        
        # 立即运行一次
        self.logger.info("执行初始特征刷新")
        self.run_feature_refresh()
        
        # 启动调度循环
        def scheduler_loop():
            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # 每分钟检查一次
                except Exception as e:
                    self.logger.error(f"调度循环异常: {e}")
                    time.sleep(60)
        
        # 在后台线程中运行调度器
        scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler_thread.start()
        
        self.logger.info("调度器启动完成")
    
    def stop_scheduler(self):
        """停止调度器"""
        if not self.is_running:
            self.logger.warning("调度器未在运行")
            return
        
        self.is_running = False
        schedule.clear()
        self.logger.info("调度器已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            "is_running": self.is_running,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_run_status": self.last_run_status,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / self.run_count if self.run_count > 0 else 0,
            "pipeline_status": self.pipeline.get_pipeline_status()
        }


def main():
    """主函数 - 模拟生产环境调度"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Feast 特征工程调度器")
    parser.add_argument("--config", default="feast/integration_config.yaml", help="配置文件路径")
    parser.add_argument("--mode", choices=["daemon", "once"], default="daemon", help="运行模式")
    parser.add_argument("--duration", type=int, default=3600, help="守护进程运行时长（秒）")
    
    args = parser.parse_args()
    
    # 创建调度器
    scheduler = FeastScheduler(args.config)
    
    if args.mode == "once":
        # 运行一次
        print("运行单次特征刷新任务...")
        scheduler.run_feature_refresh()
        
        status = scheduler.get_status()
        print(f"任务状态: {status['last_run_status']}")
        
    else:
        # 守护进程模式
        print(f"启动调度器守护进程，运行 {args.duration} 秒...")
        
        try:
            scheduler.start_scheduler()
            
            # 运行指定时长
            time.sleep(args.duration)
            
        except KeyboardInterrupt:
            print("收到中断信号，停止调度器...")
        
        finally:
            scheduler.stop_scheduler()
            
            # 显示最终状态
            status = scheduler.get_status()
            print(f"调度器状态: {json.dumps(status, indent=2)}")
    
    return 0


if __name__ == "__main__":
    exit(main())
