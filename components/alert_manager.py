#!/usr/bin/env python3
"""
Alert Manager Integration
Manages alerts and notifications for MLOps platform
"""

import logging
import json
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


class Alert:
    """Alert data model"""
    
    def __init__(self,
                 name: str,
                 severity: AlertSeverity,
                 message: str,
                 labels: Dict[str, str] = None,
                 annotations: Dict[str, str] = None):
        """
        Initialize alert
        
        Args:
            name: Alert name
            severity: Alert severity
            message: Alert message
            labels: Alert labels
            annotations: Additional annotations
        """
        self.name = name
        self.severity = severity
        self.message = message
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.status = AlertStatus.FIRING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.alert_id = f"{name}_{int(self.created_at.timestamp())}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "message": self.message,
            "status": self.status.value,
            "labels": self.labels,
            "annotations": self.annotations,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def acknowledge(self):
        """Acknowledge the alert"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.updated_at = datetime.now()
    
    def resolve(self):
        """Resolve the alert"""
        self.status = AlertStatus.RESOLVED
        self.updated_at = datetime.now()


class AlertManagerClient:
    """Client for Prometheus AlertManager"""
    
    def __init__(self, alertmanager_url: str = "http://localhost:9093"):
        """
        Initialize AlertManager client
        
        Args:
            alertmanager_url: AlertManager URL
        """
        self.alertmanager_url = alertmanager_url.rstrip('/')
        self.api_url = f"{self.alertmanager_url}/api/v2"
        
    def send_alert(self, alert: Alert) -> bool:
        """
        Send alert to AlertManager
        
        Args:
            alert: Alert object
            
        Returns:
            bool: Success status
        """
        try:
            # Convert to AlertManager format
            payload = [{
                "labels": {
                    "alertname": alert.name,
                    "severity": alert.severity.value,
                    **alert.labels
                },
                "annotations": {
                    "summary": alert.message,
                    **alert.annotations
                },
                "startsAt": alert.created_at.isoformat(),
                "generatorURL": f"mlops-platform/{alert.alert_id}"
            }]
            
            response = requests.post(
                f"{self.api_url}/alerts",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code in [200, 202]:
                logger.info(f"✅ Alert sent: {alert.name}")
                return True
            else:
                logger.error(f"❌ Failed to send alert: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"AlertManager connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    def get_alerts(self, 
                   filter_labels: Dict[str, str] = None,
                   active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get alerts from AlertManager
        
        Args:
            filter_labels: Filter by labels
            active_only: Only return active alerts
            
        Returns:
            list: List of alerts
        """
        try:
            params = {}
            if filter_labels:
                params["filter"] = ",".join([f'{k}="{v}"' for k, v in filter_labels.items()])
            if active_only:
                params["active"] = "true"
            
            response = requests.get(
                f"{self.api_url}/alerts",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get alerts: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    def silence_alert(self, 
                     matcher: Dict[str, str],
                     duration_hours: int = 24,
                     comment: str = None) -> Optional[str]:
        """
        Create a silence for matching alerts
        
        Args:
            matcher: Label matcher
            duration_hours: Silence duration in hours
            comment: Silence comment
            
        Returns:
            str: Silence ID or None
        """
        try:
            starts_at = datetime.now()
            ends_at = starts_at + timedelta(hours=duration_hours)
            
            payload = {
                "matchers": [
                    {"name": k, "value": v, "isRegex": False}
                    for k, v in matcher.items()
                ],
                "startsAt": starts_at.isoformat(),
                "endsAt": ends_at.isoformat(),
                "createdBy": "mlops-platform",
                "comment": comment or f"Silenced for {duration_hours} hours"
            }
            
            response = requests.post(
                f"{self.api_url}/silences",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                silence_id = response.json().get("silenceID")
                logger.info(f"✅ Silence created: {silence_id}")
                return silence_id
            else:
                logger.error(f"Failed to create silence: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating silence: {e}")
            return None
    
    def check_health(self) -> Dict[str, Any]:
        """Check AlertManager health"""
        try:
            response = requests.get(f"{self.alertmanager_url}/-/healthy", timeout=5)
            
            return {
                "available": response.status_code == 200,
                "url": self.alertmanager_url,
                "status_code": response.status_code
            }
            
        except requests.exceptions.RequestException:
            return {
                "available": False,
                "url": self.alertmanager_url,
                "error": "Connection failed"
            }


class MLOpsAlertManager:
    """Alert manager for MLOps platform"""
    
    def __init__(self, 
                 alertmanager_url: str = None,
                 email_config: Dict[str, str] = None,
                 slack_webhook: str = None):
        """
        Initialize MLOps alert manager
        
        Args:
            alertmanager_url: AlertManager URL
            email_config: Email configuration
            slack_webhook: Slack webhook URL
        """
        self.alertmanager = AlertManagerClient(alertmanager_url) if alertmanager_url else None
        self.email_config = email_config
        self.slack_webhook = slack_webhook
        self.active_alerts = {}
        
    def create_alert(self,
                    name: str,
                    severity: AlertSeverity,
                    message: str,
                    component: str,
                    labels: Dict[str, str] = None,
                    annotations: Dict[str, str] = None) -> Alert:
        """
        Create and send an alert
        
        Args:
            name: Alert name
            severity: Alert severity
            message: Alert message
            component: Component name
            labels: Additional labels
            annotations: Additional annotations
            
        Returns:
            Alert: Created alert
        """
        # Prepare labels
        alert_labels = {"component": component}
        if labels:
            alert_labels.update(labels)
        
        # Create alert
        alert = Alert(name, severity, message, alert_labels, annotations)
        
        # Store alert
        self.active_alerts[alert.alert_id] = alert
        
        # Send to AlertManager
        if self.alertmanager:
            self.alertmanager.send_alert(alert)
        
        # Send notifications
        self._send_notifications(alert)
        
        return alert
    
    def _send_notifications(self, alert: Alert):
        """Send alert notifications via configured channels"""
        # Send email
        if self.email_config and alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            self._send_email_alert(alert)
        
        # Send Slack notification
        if self.slack_webhook:
            self._send_slack_alert(alert)
    
    def _send_email_alert(self, alert: Alert) -> bool:
        """Send alert via email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config.get('from')
            msg['To'] = self.email_config.get('to')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.name}"
            
            body = f"""
MLOps Platform Alert

Alert: {alert.name}
Severity: {alert.severity.value}
Status: {alert.status.value}
Component: {alert.labels.get('component', 'unknown')}
Time: {alert.created_at.isoformat()}

Message:
{alert.message}

Labels:
{json.dumps(alert.labels, indent=2)}
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(
                self.email_config.get('smtp_host', 'localhost'),
                self.email_config.get('smtp_port', 587)
            )
            server.starttls()
            
            if self.email_config.get('username'):
                server.login(
                    self.email_config['username'],
                    self.email_config['password']
                )
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Email alert sent: {alert.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_slack_alert(self, alert: Alert) -> bool:
        """Send alert to Slack"""
        try:
            # Determine color based on severity
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9900",
                AlertSeverity.ERROR: "#ff0000",
                AlertSeverity.CRITICAL: "#8b0000"
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "#808080"),
                    "title": f"{alert.severity.value.upper()}: {alert.name}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Component",
                            "value": alert.labels.get('component', 'unknown'),
                            "short": True
                        },
                        {
                            "title": "Status",
                            "value": alert.status.value,
                            "short": True
                        },
                        {
                            "title": "Time",
                            "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": False
                        }
                    ],
                    "footer": "MLOps Platform",
                    "ts": int(alert.created_at.timestamp())
                }]
            }
            
            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Slack alert sent: {alert.name}")
                return True
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            return False
    
    # Predefined alert methods for common scenarios
    
    def alert_data_drift(self, feature: str, drift_score: float, threshold: float):
        """Alert for data drift detection"""
        return self.create_alert(
            name="DataDriftDetected",
            severity=AlertSeverity.WARNING,
            message=f"Data drift detected in feature '{feature}': score {drift_score:.3f} exceeds threshold {threshold}",
            component="monitoring",
            labels={"feature": feature, "type": "data_drift"},
            annotations={
                "drift_score": str(drift_score),
                "threshold": str(threshold),
                "recommendation": "Review data quality and consider model retraining"
            }
        )
    
    def alert_model_performance_degradation(self, 
                                           model_name: str,
                                           metric: str,
                                           current_value: float,
                                           threshold: float):
        """Alert for model performance degradation"""
        return self.create_alert(
            name="ModelPerformanceDegradation",
            severity=AlertSeverity.ERROR,
            message=f"Model '{model_name}' performance degraded: {metric}={current_value:.3f} below threshold {threshold}",
            component="model",
            labels={"model": model_name, "metric": metric},
            annotations={
                "current_value": str(current_value),
                "threshold": str(threshold),
                "recommendation": "Investigate model performance and consider retraining"
            }
        )
    
    def alert_pipeline_failure(self, 
                              pipeline_name: str,
                              component: str,
                              error_message: str):
        """Alert for pipeline failure"""
        return self.create_alert(
            name="PipelineFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"Pipeline '{pipeline_name}' failed at component '{component}': {error_message}",
            component="tfx",
            labels={"pipeline": pipeline_name, "pipeline_component": component},
            annotations={
                "error": error_message,
                "recommendation": "Check pipeline logs and component configuration"
            }
        )
    
    def alert_api_high_latency(self, 
                              endpoint: str,
                              latency_ms: float,
                              threshold_ms: float):
        """Alert for API high latency"""
        return self.create_alert(
            name="APIHighLatency",
            severity=AlertSeverity.WARNING,
            message=f"API endpoint '{endpoint}' experiencing high latency: {latency_ms:.1f}ms (threshold: {threshold_ms}ms)",
            component="api",
            labels={"endpoint": endpoint},
            annotations={
                "latency_ms": str(latency_ms),
                "threshold_ms": str(threshold_ms),
                "recommendation": "Check API performance and resource utilization"
            }
        )
    
    def alert_resource_exhaustion(self, 
                                 resource_type: str,
                                 usage_percent: float,
                                 threshold_percent: float):
        """Alert for resource exhaustion"""
        return self.create_alert(
            name="ResourceExhaustion",
            severity=AlertSeverity.CRITICAL,
            message=f"{resource_type} usage at {usage_percent:.1f}% (threshold: {threshold_percent}%)",
            component="infrastructure",
            labels={"resource_type": resource_type},
            annotations={
                "usage_percent": str(usage_percent),
                "threshold_percent": str(threshold_percent),
                "recommendation": "Scale resources or optimize usage"
            }
        )
    
    def get_active_alerts(self, 
                         severity: AlertSeverity = None,
                         component: str = None) -> List[Alert]:
        """Get active alerts with optional filtering"""
        alerts = list(self.active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if component:
            alerts = [a for a in alerts if a.labels.get('component') == component]
        
        return [a for a in alerts if a.status == AlertStatus.FIRING]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledge()
            logger.info(f"Alert acknowledged: {alert_id}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolve()
            logger.info(f"Alert resolved: {alert_id}")
            return True
        return False
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of all alerts"""
        alerts = list(self.active_alerts.values())
        
        summary = {
            "total_alerts": len(alerts),
            "by_severity": {},
            "by_status": {},
            "by_component": {},
            "active_count": 0
        }
        
        for alert in alerts:
            # Count by severity
            severity = alert.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            
            # Count by status
            status = alert.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # Count by component
            component = alert.labels.get('component', 'unknown')
            summary["by_component"][component] = summary["by_component"].get(component, 0) + 1
            
            # Count active
            if alert.status == AlertStatus.FIRING:
                summary["active_count"] += 1
        
        return summary


if __name__ == "__main__":
    # Example usage
    alert_manager = MLOpsAlertManager()
    
    # Create different types of alerts
    alert_manager.alert_data_drift("trip_miles", 0.45, 0.3)
    alert_manager.alert_model_performance_degradation("taxi_model", "accuracy", 0.65, 0.75)
    alert_manager.alert_pipeline_failure("taxi_pipeline", "Trainer", "Out of memory")
    alert_manager.alert_api_high_latency("/predict", 1500, 1000)
    
    # Get alert summary
    summary = alert_manager.get_alert_summary()
    print(json.dumps(summary, indent=2))
    
    # Get active alerts
    active_alerts = alert_manager.get_active_alerts()
    print(f"\nActive alerts: {len(active_alerts)}")
    for alert in active_alerts:
        print(f"  - {alert.name}: {alert.message}")
