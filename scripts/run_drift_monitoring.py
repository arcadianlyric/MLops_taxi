#!/usr/bin/env python3
"""
数据漂移监控运行脚本
集成 TFX Pipeline 数据漂移监控组件与 Streamlit UI
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from tfx.orchestration.beam.beam_dag_runner import BeamDagRunner
from examples.data_drift_monitoring_example import create_drift_monitoring_pipeline


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('drift_monitoring.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def prepare_data_for_drift_monitoring(logger):
    """准备数据漂移监控所需的数据"""
    
    # 数据目录
    data_dir = project_root / 'data'
    baseline_dir = data_dir / 'baseline'
    current_dir = data_dir / 'current'
    
    # 创建目录
    baseline_dir.mkdir(parents=True, exist_ok=True)
    current_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查是否有现有数据
    taxi_data_path = project_root / 'data' / 'taxi_data.csv'
    
    if taxi_data_path.exists():
        logger.info(f"找到现有数据文件: {taxi_data_path}")
        
        # 复制到基线目录（模拟训练数据）
        import shutil
        shutil.copy2(taxi_data_path, baseline_dir / 'taxi_data.csv')
        
        # 生成当前数据（模拟生产数据，添加一些噪声）
        generate_current_data(taxi_data_path, current_dir / 'taxi_data.csv', logger)
        
    else:
        logger.warning("未找到现有数据文件，生成模拟数据")
        generate_mock_data(baseline_dir, current_dir, logger)


def generate_current_data(baseline_path, current_path, logger):
    """基于基线数据生成当前数据（添加漂移）"""
    
    try:
        import pandas as pd
        import numpy as np
        
        # 读取基线数据
        df = pd.read_csv(baseline_path)
        logger.info(f"基线数据形状: {df.shape}")
        
        # 添加数据漂移
        df_current = df.copy()
        
        # 数值特征添加漂移
        if 'trip_miles' in df_current.columns:
            df_current['trip_miles'] *= np.random.normal(1.1, 0.1, len(df_current))
        
        if 'fare' in df_current.columns:
            df_current['fare'] *= np.random.normal(1.05, 0.05, len(df_current))
        
        if 'trip_seconds' in df_current.columns:
            df_current['trip_seconds'] *= np.random.normal(0.95, 0.1, len(df_current))
        
        # 分类特征添加漂移
        if 'payment_type' in df_current.columns:
            # 改变支付方式分布
            mask = np.random.random(len(df_current)) < 0.2
            df_current.loc[mask, 'payment_type'] = 'Credit Card'
        
        # 保存当前数据
        df_current.to_csv(current_path, index=False)
        logger.info(f"当前数据已保存到: {current_path}")
        
    except Exception as e:
        logger.error(f"生成当前数据时出错: {e}")
        raise


def generate_mock_data(baseline_dir, current_dir, logger):
    """生成模拟数据"""
    
    try:
        import pandas as pd
        import numpy as np
        
        # 生成模拟 Chicago Taxi 数据
        n_samples = 1000
        
        # 基线数据
        baseline_data = {
            'trip_miles': np.random.exponential(3, n_samples),
            'fare': np.random.exponential(8, n_samples),
            'trip_seconds': np.random.exponential(600, n_samples),
            'pickup_latitude': np.random.normal(41.88, 0.1, n_samples),
            'pickup_longitude': np.random.normal(-87.63, 0.1, n_samples),
            'dropoff_latitude': np.random.normal(41.89, 0.1, n_samples),
            'dropoff_longitude': np.random.normal(-87.62, 0.1, n_samples),
            'payment_type': np.random.choice(['Credit Card', 'Cash', 'No Charge'], n_samples, p=[0.7, 0.25, 0.05]),
            'company': np.random.choice(['Flash Cab', 'Taxi Affiliation Services', 'Yellow Cab'], n_samples, p=[0.4, 0.35, 0.25]),
            'trip_start_hour': np.random.randint(0, 24, n_samples)
        }
        
        df_baseline = pd.DataFrame(baseline_data)
        df_baseline.to_csv(baseline_dir / 'taxi_data.csv', index=False)
        
        # 当前数据（添加漂移）
        current_data = baseline_data.copy()
        current_data['trip_miles'] = np.random.exponential(3.5, n_samples)  # 漂移
        current_data['fare'] = np.random.exponential(9, n_samples)  # 漂移
        current_data['payment_type'] = np.random.choice(['Credit Card', 'Cash', 'No Charge'], n_samples, p=[0.8, 0.15, 0.05])  # 漂移
        
        df_current = pd.DataFrame(current_data)
        df_current.to_csv(current_dir / 'taxi_data.csv', index=False)
        
        logger.info(f"模拟数据已生成: 基线 {baseline_dir}, 当前 {current_dir}")
        
    except Exception as e:
        logger.error(f"生成模拟数据时出错: {e}")
        raise


def run_drift_monitoring_pipeline(logger):
    """运行数据漂移监控 Pipeline"""
    
    try:
        # Pipeline 配置
        pipeline_name = 'chicago_taxi_drift_monitoring'
        pipeline_root = project_root / 'pipelines' / pipeline_name
        metadata_path = project_root / 'metadata' / pipeline_name / 'metadata.db'
        
        # 数据路径
        baseline_data_root = str(project_root / 'data' / 'baseline')
        current_data_root = str(project_root / 'data' / 'current')
        
        # 创建目录
        pipeline_root.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Beam 参数
        beam_pipeline_args = [
            '--direct_running_mode=multi_processing',
            '--direct_num_workers=0',
        ]
        
        logger.info("创建数据漂移监控 Pipeline...")
        
        # 创建 Pipeline
        drift_pipeline = create_drift_monitoring_pipeline(
            pipeline_name=pipeline_name,
            pipeline_root=str(pipeline_root),
            baseline_data_root=baseline_data_root,
            current_data_root=current_data_root,
            metadata_path=str(metadata_path),
            beam_pipeline_args=beam_pipeline_args
        )
        
        logger.info("运行数据漂移监控 Pipeline...")
        
        # 运行 Pipeline
        BeamDagRunner().run(drift_pipeline)
        
        logger.info("数据漂移监控 Pipeline 运行完成！")
        
        # 查找并复制结果到 UI 可访问的位置
        copy_results_for_ui(pipeline_root, logger)
        
    except Exception as e:
        logger.error(f"运行数据漂移监控 Pipeline 时出错: {e}")
        raise


def copy_results_for_ui(pipeline_root, logger):
    """复制漂移监控结果到 UI 可访问的位置"""
    
    try:
        # 查找漂移报告文件
        drift_report_files = list(pipeline_root.rglob('drift_report.json'))
        drift_metrics_files = list(pipeline_root.rglob('drift_metrics.json'))
        
        # UI 结果目录
        ui_results_dir = project_root / 'ui' / 'drift_results'
        ui_results_dir.mkdir(exist_ok=True)
        
        if drift_report_files:
            import shutil
            latest_report = max(drift_report_files, key=lambda x: x.stat().st_mtime)
            shutil.copy2(latest_report, ui_results_dir / 'latest_drift_report.json')
            logger.info(f"漂移报告已复制到: {ui_results_dir / 'latest_drift_report.json'}")
        
        if drift_metrics_files:
            import shutil
            latest_metrics = max(drift_metrics_files, key=lambda x: x.stat().st_mtime)
            shutil.copy2(latest_metrics, ui_results_dir / 'latest_drift_metrics.json')
            logger.info(f"漂移指标已复制到: {ui_results_dir / 'latest_drift_metrics.json'}")
        
        # 生成 UI 配置文件
        ui_config = {
            'last_update': datetime.now().isoformat(),
            'drift_report_path': str(ui_results_dir / 'latest_drift_report.json'),
            'drift_metrics_path': str(ui_results_dir / 'latest_drift_metrics.json'),
            'pipeline_root': str(pipeline_root)
        }
        
        with open(ui_results_dir / 'config.json', 'w') as f:
            json.dump(ui_config, f, indent=2)
        
        logger.info("UI 配置文件已生成")
        
    except Exception as e:
        logger.error(f"复制结果文件时出错: {e}")


def main():
    """主函数"""
    
    parser = argparse.ArgumentParser(description='运行数据漂移监控')
    parser.add_argument('--skip-pipeline', action='store_true', help='跳过 Pipeline 运行，仅准备数据')
    parser.add_argument('--mock-data', action='store_true', help='使用模拟数据')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging()
    
    try:
        logger.info("开始数据漂移监控流程...")
        
        # 准备数据
        logger.info("准备数据...")
        prepare_data_for_drift_monitoring(logger)
        
        if not args.skip_pipeline:
            # 运行 Pipeline
            logger.info("运行数据漂移监控 Pipeline...")
            run_drift_monitoring_pipeline(logger)
        else:
            logger.info("跳过 Pipeline 运行")
        
        logger.info("数据漂移监控流程完成！")
        logger.info("现在可以在 Streamlit UI 中查看结果：http://localhost:8501")
        
    except Exception as e:
        logger.error(f"数据漂移监控流程失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
