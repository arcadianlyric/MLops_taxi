#!/usr/bin/env python3
"""
Loki Log Aggregation Integration
Centralized logging for MLOps platform
"""

import logging
import json
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import socket
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LokiClient:
    """Client for sending logs to Loki"""
    
    def __init__(self, loki_url: str = "http://localhost:3100"):
        """
        Initialize Loki client
        
        Args:
            loki_url: Loki server URL
        """
        self.loki_url = loki_url.rstrip('/')
        self.push_url = f"{self.loki_url}/loki/api/v1/push"
        self.query_url = f"{self.loki_url}/loki/api/v1/query"
        self.query_range_url = f"{self.loki_url}/loki/api/v1/query_range"
        self.hostname = socket.gethostname()
        
    def push_log(self, 
                 message: str, 
                 labels: Dict[str, str] = None,
                 level: str = "info",
                 timestamp: int = None) -> bool:
        """
        Push a log entry to Loki
        
        Args:
            message: Log message
            labels: Log labels (job, instance, etc.)
            level: Log level
            timestamp: Unix timestamp in nanoseconds
            
        Returns:
            bool: Success status
        """
        try:
            # Default labels
            default_labels = {
                "job": "mlops-taxi",
                "instance": self.hostname,
                "level": level
            }
            
            if labels:
                default_labels.update(labels)
            
            # Convert labels to Loki format
            label_str = ",".join([f'{k}="{v}"' for k, v in default_labels.items()])
            
            # Timestamp in nanoseconds
            if timestamp is None:
                timestamp = int(time.time() * 1e9)
            
            # Prepare payload
            payload = {
                "streams": [
                    {
                        "stream": default_labels,
                        "values": [
                            [str(timestamp), message]
                        ]
                    }
                ]
            }
            
            # Send to Loki
            response = requests.post(
                self.push_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 204:
                return True
            else:
                logger.error(f"Failed to push log: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Loki connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error pushing log: {e}")
            return False
    
    def query_logs(self, 
                   query: str, 
                   limit: int = 100,
                   start: datetime = None,
                   end: datetime = None) -> List[Dict[str, Any]]:
        """
        Query logs from Loki
        
        Args:
            query: LogQL query string
            limit: Maximum number of results
            start: Start time
            end: End time
            
        Returns:
            list: Log entries
        """
        try:
            params = {
                "query": query,
                "limit": limit
            }
            
            if start and end:
                params["start"] = int(start.timestamp() * 1e9)
                params["end"] = int(end.timestamp() * 1e9)
                url = self.query_range_url
            else:
                url = self.query_url
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_query_response(data)
            else:
                logger.error(f"Query failed: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error querying logs: {e}")
            return []
    
    def _parse_query_response(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse Loki query response"""
        logs = []
        
        try:
            if data.get("status") == "success":
                result = data.get("data", {}).get("result", [])
                
                for stream in result:
                    labels = stream.get("stream", {})
                    values = stream.get("values", [])
                    
                    for value in values:
                        timestamp_ns, message = value
                        logs.append({
                            "timestamp": datetime.fromtimestamp(int(timestamp_ns) / 1e9).isoformat(),
                            "message": message,
                            "labels": labels
                        })
            
            return logs
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return []
    
    def check_health(self) -> Dict[str, Any]:
        """Check Loki server health"""
        try:
            response = requests.get(f"{self.loki_url}/ready", timeout=5)
            
            return {
                "available": response.status_code == 200,
                "url": self.loki_url,
                "status_code": response.status_code
            }
            
        except requests.exceptions.RequestException:
            return {
                "available": False,
                "url": self.loki_url,
                "error": "Connection failed"
            }


class LokiHandler(logging.Handler):
    """Custom logging handler for Loki"""
    
    def __init__(self, loki_url: str, labels: Dict[str, str] = None):
        """
        Initialize Loki logging handler
        
        Args:
            loki_url: Loki server URL
            labels: Default labels for all logs
        """
        super().__init__()
        self.client = LokiClient(loki_url)
        self.default_labels = labels or {}
        
    def emit(self, record: logging.LogRecord):
        """Emit a log record to Loki"""
        try:
            # Format the message
            message = self.format(record)
            
            # Prepare labels
            labels = self.default_labels.copy()
            labels.update({
                "level": record.levelname.lower(),
                "logger": record.name,
                "module": record.module
            })
            
            # Push to Loki
            self.client.push_log(message, labels=labels)
            
        except Exception:
            self.handleError(record)


class MLOpsPlatformLogger:
    """Centralized logger for MLOps platform"""
    
    def __init__(self, loki_url: str = "http://localhost:3100"):
        """
        Initialize platform logger
        
        Args:
            loki_url: Loki server URL
        """
        self.loki_client = LokiClient(loki_url)
        self.component_loggers = {}
        
    def get_logger(self, component: str, labels: Dict[str, str] = None) -> logging.Logger:
        """
        Get a logger for a specific component
        
        Args:
            component: Component name (api, ui, tfx, etc.)
            labels: Additional labels
            
        Returns:
            logging.Logger: Configured logger
        """
        if component in self.component_loggers:
            return self.component_loggers[component]
        
        # Create logger
        logger = logging.getLogger(f"mlops.{component}")
        logger.setLevel(logging.INFO)
        
        # Add Loki handler
        component_labels = {"component": component}
        if labels:
            component_labels.update(labels)
        
        loki_handler = LokiHandler(self.loki_client.loki_url, labels=component_labels)
        loki_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(loki_handler)
        
        # Also add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(console_handler)
        
        self.component_loggers[component] = logger
        return logger
    
    def log_api_request(self, 
                       endpoint: str, 
                       method: str, 
                       status_code: int,
                       duration_ms: float,
                       user_id: str = None):
        """Log API request"""
        message = f"API {method} {endpoint} - {status_code} - {duration_ms:.2f}ms"
        
        labels = {
            "component": "api",
            "endpoint": endpoint,
            "method": method,
            "status_code": str(status_code)
        }
        
        if user_id:
            labels["user_id"] = user_id
        
        self.loki_client.push_log(message, labels=labels, level="info")
    
    def log_pipeline_event(self,
                          pipeline_name: str,
                          component: str,
                          event: str,
                          status: str,
                          details: Dict[str, Any] = None):
        """Log TFX pipeline event"""
        message = f"Pipeline {pipeline_name} - {component} - {event} - {status}"
        
        if details:
            message += f" - {json.dumps(details)}"
        
        labels = {
            "component": "tfx",
            "pipeline": pipeline_name,
            "pipeline_component": component,
            "event": event,
            "status": status
        }
        
        level = "error" if status == "failed" else "info"
        self.loki_client.push_log(message, labels=labels, level=level)
    
    def log_model_event(self,
                       model_name: str,
                       event: str,
                       version: str = None,
                       metrics: Dict[str, float] = None):
        """Log model-related event"""
        message = f"Model {model_name} - {event}"
        
        if version:
            message += f" - version {version}"
        
        if metrics:
            message += f" - metrics: {json.dumps(metrics)}"
        
        labels = {
            "component": "model",
            "model_name": model_name,
            "event": event
        }
        
        if version:
            labels["version"] = version
        
        self.loki_client.push_log(message, labels=labels, level="info")
    
    def log_data_drift(self,
                      feature: str,
                      drift_score: float,
                      threshold: float,
                      is_drifted: bool):
        """Log data drift detection"""
        message = f"Data Drift - {feature} - score: {drift_score:.3f} - threshold: {threshold}"
        
        labels = {
            "component": "monitoring",
            "type": "data_drift",
            "feature": feature,
            "is_drifted": str(is_drifted)
        }
        
        level = "warning" if is_drifted else "info"
        self.loki_client.push_log(message, labels=labels, level=level)
    
    def query_component_logs(self, 
                            component: str, 
                            hours: int = 1,
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Query logs for a specific component"""
        query = f'{{component="{component}"}}'
        end = datetime.now()
        start = end - timedelta(hours=hours)
        
        return self.loki_client.query_logs(query, limit=limit, start=start, end=end)
    
    def query_error_logs(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Query error logs"""
        query = '{level="error"}'
        end = datetime.now()
        start = end - timedelta(hours=hours)
        
        return self.loki_client.query_logs(query, limit=limit, start=start, end=end)
    
    def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get log statistics"""
        try:
            # Query all logs
            query = '{job="mlops-taxi"}'
            end = datetime.now()
            start = end - timedelta(hours=hours)
            
            logs = self.loki_client.query_logs(query, limit=1000, start=start, end=end)
            
            # Calculate statistics
            stats = {
                "total_logs": len(logs),
                "time_range_hours": hours,
                "by_level": {},
                "by_component": {},
                "error_count": 0
            }
            
            for log in logs:
                labels = log.get("labels", {})
                level = labels.get("level", "unknown")
                component = labels.get("component", "unknown")
                
                # Count by level
                stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
                
                # Count by component
                stats["by_component"][component] = stats["by_component"].get(component, 0) + 1
                
                # Count errors
                if level == "error":
                    stats["error_count"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}


# FastAPI integration example
def setup_fastapi_logging(app, loki_url: str = "http://localhost:3100"):
    """Setup Loki logging for FastAPI application"""
    platform_logger = MLOpsPlatformLogger(loki_url)
    
    @app.middleware("http")
    async def log_requests(request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        platform_logger.log_api_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms
        )
        
        return response
    
    return platform_logger


if __name__ == "__main__":
    # Example usage
    loki = LokiClient("http://localhost:3100")
    
    # Check health
    health = loki.check_health()
    print(f"Loki Health: {json.dumps(health, indent=2)}")
    
    # Push a test log
    if health["available"]:
        success = loki.push_log(
            "Test log message from MLOps platform",
            labels={"component": "test", "environment": "dev"},
            level="info"
        )
        print(f"Log pushed: {success}")
    
    # Example with platform logger
    platform_logger = MLOpsPlatformLogger()
    
    # Log different events
    platform_logger.log_api_request("/predict", "POST", 200, 45.3)
    platform_logger.log_pipeline_event("taxi_pipeline", "Trainer", "training_started", "running")
    platform_logger.log_model_event("taxi_model", "deployed", version="v1.0", metrics={"accuracy": 0.77})
    platform_logger.log_data_drift("trip_miles", 0.35, 0.3, True)
