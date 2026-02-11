#!/usr/bin/env python3
"""
DVC (Data Version Control) Integration Component
Manages data versioning and tracking for ML pipelines
"""

import os
import json
import logging
import subprocess
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DVCIntegration:
    """DVC Integration for data version control"""
    
    def __init__(self, repo_path: str = None, remote_url: str = None):
        """
        Initialize DVC integration
        
        Args:
            repo_path: Path to the repository
            remote_url: Remote storage URL (S3, GCS, etc.)
        """
        self.repo_path = repo_path or os.getcwd()
        self.remote_url = remote_url
        self.dvc_dir = os.path.join(self.repo_path, '.dvc')
        self.is_initialized = os.path.exists(self.dvc_dir)
        
    def initialize_dvc(self) -> bool:
        """
        Initialize DVC in the repository
        
        Returns:
            bool: Success status
        """
        try:
            if self.is_initialized:
                logger.info("✅ DVC already initialized")
                return True
            
            # Initialize DVC
            result = subprocess.run(
                ['dvc', 'init'],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("✅ DVC initialized successfully")
                self.is_initialized = True
                
                # Configure remote if provided
                if self.remote_url:
                    self.add_remote('default', self.remote_url)
                
                return True
            else:
                logger.error(f"❌ DVC initialization failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("❌ DVC not installed. Install with: pip install dvc")
            return False
        except Exception as e:
            logger.error(f"❌ DVC initialization error: {e}")
            return False
    
    def add_remote(self, name: str, url: str) -> bool:
        """
        Add a remote storage location
        
        Args:
            name: Remote name
            url: Remote URL (s3://bucket, gs://bucket, etc.)
            
        Returns:
            bool: Success status
        """
        try:
            result = subprocess.run(
                ['dvc', 'remote', 'add', '-d', name, url],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Remote '{name}' added: {url}")
                return True
            else:
                logger.error(f"❌ Failed to add remote: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error adding remote: {e}")
            return False
    
    def track_data(self, data_path: str, commit_message: str = None) -> Dict[str, Any]:
        """
        Track a data file or directory with DVC
        
        Args:
            data_path: Path to data file or directory
            commit_message: Optional commit message
            
        Returns:
            dict: Tracking information
        """
        try:
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"Data path not found: {data_path}")
            
            # Add file to DVC
            result = subprocess.run(
                ['dvc', 'add', data_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise Exception(f"DVC add failed: {result.stderr}")
            
            # Get file hash
            dvc_file = f"{data_path}.dvc"
            with open(dvc_file, 'r') as f:
                dvc_metadata = json.load(f) if dvc_file.endswith('.json') else {}
            
            # Calculate file hash
            file_hash = self._calculate_hash(data_path)
            
            tracking_info = {
                'data_path': data_path,
                'dvc_file': dvc_file,
                'file_hash': file_hash,
                'timestamp': datetime.now().isoformat(),
                'commit_message': commit_message or f"Track {os.path.basename(data_path)}",
                'status': 'tracked'
            }
            
            logger.info(f"✅ Data tracked: {data_path}")
            return tracking_info
            
        except Exception as e:
            logger.error(f"❌ Error tracking data: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def push_data(self, data_path: str = None) -> bool:
        """
        Push data to remote storage
        
        Args:
            data_path: Optional specific file to push
            
        Returns:
            bool: Success status
        """
        try:
            cmd = ['dvc', 'push']
            if data_path:
                cmd.append(data_path)
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Data pushed to remote")
                return True
            else:
                logger.error(f"❌ Push failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error pushing data: {e}")
            return False
    
    def pull_data(self, data_path: str = None) -> bool:
        """
        Pull data from remote storage
        
        Args:
            data_path: Optional specific file to pull
            
        Returns:
            bool: Success status
        """
        try:
            cmd = ['dvc', 'pull']
            if data_path:
                cmd.append(data_path)
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Data pulled from remote")
                return True
            else:
                logger.error(f"❌ Pull failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error pulling data: {e}")
            return False
    
    def get_data_version(self, data_path: str) -> Optional[str]:
        """
        Get the version hash of tracked data
        
        Args:
            data_path: Path to data file
            
        Returns:
            str: Version hash or None
        """
        try:
            dvc_file = f"{data_path}.dvc"
            if not os.path.exists(dvc_file):
                return None
            
            with open(dvc_file, 'r') as f:
                content = f.read()
                # Extract md5 hash from DVC file
                for line in content.split('\n'):
                    if 'md5:' in line:
                        return line.split('md5:')[1].strip()
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting version: {e}")
            return None
    
    def list_tracked_data(self) -> List[Dict[str, Any]]:
        """
        List all DVC-tracked data files
        
        Returns:
            list: List of tracked files with metadata
        """
        try:
            tracked_files = []
            
            for root, dirs, files in os.walk(self.repo_path):
                for file in files:
                    if file.endswith('.dvc'):
                        dvc_file = os.path.join(root, file)
                        data_file = dvc_file[:-4]  # Remove .dvc extension
                        
                        tracked_files.append({
                            'data_file': data_file,
                            'dvc_file': dvc_file,
                            'version': self.get_data_version(data_file),
                            'exists': os.path.exists(data_file)
                        })
            
            return tracked_files
            
        except Exception as e:
            logger.error(f"❌ Error listing tracked data: {e}")
            return []
    
    def checkout_version(self, data_path: str, version: str) -> bool:
        """
        Checkout a specific version of data
        
        Args:
            data_path: Path to data file
            version: Git commit hash or tag
            
        Returns:
            bool: Success status
        """
        try:
            # Checkout git version first
            result = subprocess.run(
                ['git', 'checkout', version, f"{data_path}.dvc"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise Exception(f"Git checkout failed: {result.stderr}")
            
            # Pull the data
            return self.pull_data(data_path)
            
        except Exception as e:
            logger.error(f"❌ Error checking out version: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get DVC status information
        
        Returns:
            dict: Status information
        """
        try:
            result = subprocess.run(
                ['dvc', 'status'],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            return {
                'initialized': self.is_initialized,
                'repo_path': self.repo_path,
                'remote_url': self.remote_url,
                'status_output': result.stdout,
                'tracked_files': len(self.list_tracked_data())
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting status: {e}")
            return {'error': str(e)}
    
    def _calculate_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of a file"""
        if os.path.isdir(file_path):
            return "directory"
        
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return "error"


# Example usage for TFX Pipeline integration
class TFXDVCIntegration:
    """DVC integration specifically for TFX pipelines"""
    
    def __init__(self, pipeline_root: str, dvc_remote: str = None):
        self.pipeline_root = pipeline_root
        self.dvc = DVCIntegration(repo_path=pipeline_root, remote_url=dvc_remote)
        
    def track_pipeline_data(self, data_path: str) -> Dict[str, Any]:
        """Track TFX pipeline input data"""
        return self.dvc.track_data(
            data_path,
            commit_message=f"Track TFX pipeline data: {os.path.basename(data_path)}"
        )
    
    def track_pipeline_artifacts(self, artifacts_dir: str) -> Dict[str, Any]:
        """Track TFX pipeline output artifacts"""
        return self.dvc.track_data(
            artifacts_dir,
            commit_message="Track TFX pipeline artifacts"
        )
    
    def version_model(self, model_path: str, version: str) -> Dict[str, Any]:
        """Version a trained model"""
        tracking_info = self.dvc.track_data(
            model_path,
            commit_message=f"Model version {version}"
        )
        tracking_info['model_version'] = version
        return tracking_info


if __name__ == "__main__":
    # Example usage
    dvc = DVCIntegration(repo_path=".")
    
    # Initialize DVC
    dvc.initialize_dvc()
    
    # Track data
    # tracking_info = dvc.track_data("tfx_pipeline/data/simple/data.csv")
    # print(json.dumps(tracking_info, indent=2))
    
    # Get status
    status = dvc.get_status()
    print(json.dumps(status, indent=2))
