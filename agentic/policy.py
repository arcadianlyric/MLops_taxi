"""Policy checks for safe agentic retraining decisions."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class DataQualityGate:
    """Minimal gate that blocks retrain when the drift report is unusable."""

    status: str
    reason: str
    baseline_rows: int
    current_rows: int
    total_features_checked: int

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "baseline_rows": self.baseline_rows,
            "current_rows": self.current_rows,
            "total_features_checked": self.total_features_checked,
        }


@dataclass
class RetrainGuardrail:
    """Operational guardrail state for retraining."""

    retrain_in_progress: bool
    cooldown_active: bool
    cooldown_remaining_minutes: float
    last_retrain: Optional[str]
    drift_threshold: float

    @property
    def allows_retrain(self) -> bool:
        return not self.retrain_in_progress and not self.cooldown_active

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retrain_in_progress": self.retrain_in_progress,
            "cooldown_active": self.cooldown_active,
            "cooldown_remaining_minutes": round(self.cooldown_remaining_minutes, 2),
            "last_retrain": self.last_retrain,
            "drift_threshold": self.drift_threshold,
        }


class TaxiRetrainPolicy:
    """Risk policy for the auto drift retrain agent.

    Drift may trigger retraining, but never production promotion. Promotion
    remains a separate high-risk action that requires evaluation and approval.
    """

    def evaluate_data_quality(self, drift_payload: Dict[str, Any]) -> DataQualityGate:
        summary = drift_payload.get("summary", {})
        baseline_rows = int(summary.get("baseline_rows", 0) or 0)
        current_rows = int(summary.get("current_rows", 0) or 0)
        total_features = int(summary.get("total_features_checked", 0) or 0)

        if baseline_rows <= 0 or current_rows <= 0:
            return DataQualityGate("fail", "baseline/current split has no rows", baseline_rows, current_rows, total_features)
        if total_features <= 0:
            return DataQualityGate("fail", "no features available for drift check", baseline_rows, current_rows, total_features)
        return DataQualityGate("pass", "drift report has usable baseline/current data", baseline_rows, current_rows, total_features)

    def evaluate_retrain_guardrail(self, retrain_status: Dict[str, Any]) -> RetrainGuardrail:
        last_retrain = retrain_status.get("last_retrain")
        cooldown_minutes = float(retrain_status.get("cooldown_minutes", 0) or 0)
        cooldown_remaining = 0.0

        if last_retrain:
            try:
                last_dt = datetime.fromisoformat(last_retrain)
                elapsed_minutes = (datetime.now() - last_dt).total_seconds() / 60
                cooldown_remaining = max(0.0, cooldown_minutes - elapsed_minutes)
            except ValueError:
                cooldown_remaining = cooldown_minutes

        return RetrainGuardrail(
            retrain_in_progress=bool(retrain_status.get("retrain_in_progress", False)),
            cooldown_active=cooldown_remaining > 0,
            cooldown_remaining_minutes=cooldown_remaining,
            last_retrain=last_retrain,
            drift_threshold=float(retrain_status.get("drift_threshold", 0.3) or 0.3),
        )
