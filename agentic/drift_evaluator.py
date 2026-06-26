"""Evaluator agent for taxi drift-to-retrain decisions."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal

from .drift_monitor import DriftSignal
from .policy import DataQualityGate, RetrainGuardrail


@dataclass
class DriftDecision:
    """Decision produced by the evaluator agent."""

    action: Literal["ignore", "alert", "retrain"]
    confidence: float
    risk_level: Literal["low", "medium"]
    reasoning: str
    promotion_allowed: bool
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "promotion_allowed": self.promotion_allowed,
            "timestamp": self.timestamp,
        }


class TaxiDriftEvaluator:
    """Multi-factor evaluator modeled after agentic_GEM's DriftEvaluator."""

    def __init__(
        self,
        alert_threshold: float = 0.1,
        retrain_threshold: float = 0.3,
        broad_drift_ratio: float = 0.4,
    ):
        self.alert_threshold = alert_threshold
        self.retrain_threshold = retrain_threshold
        self.broad_drift_ratio = broad_drift_ratio
        self.decision_history = []

    def evaluate(
        self,
        drift: DriftSignal,
        data_quality: DataQualityGate,
        guardrail: RetrainGuardrail,
    ) -> DriftDecision:
        reasons = []
        action: Literal["ignore", "alert", "retrain"] = "ignore"
        confidence = 0.75

        if not data_quality.passed:
            action = "alert"
            confidence = 0.9
            reasons.append(f"data quality gate failed: {data_quality.reason}")
        elif guardrail.retrain_in_progress:
            action = "alert"
            confidence = 0.85
            reasons.append("retrain already in progress")
        elif guardrail.cooldown_active:
            action = "alert"
            confidence = 0.85
            reasons.append(f"cooldown active for {guardrail.cooldown_remaining_minutes:.1f} minutes")
        elif drift.max_drift_score < self.alert_threshold:
            action = "ignore"
            confidence = 0.9
            reasons.append(
                f"max drift {drift.max_drift_score:.3f} below alert threshold {self.alert_threshold:.3f}"
            )
        else:
            drift_ratio = 0.0
            if drift.total_features_checked > 0:
                drift_ratio = drift.drifted_features_count / drift.total_features_checked

            if drift.max_drift_score >= self.retrain_threshold:
                action = "retrain"
                confidence = 0.82
                reasons.append(
                    f"max drift {drift.max_drift_score:.3f} exceeds retrain threshold {self.retrain_threshold:.3f}"
                )
            elif drift_ratio >= self.broad_drift_ratio:
                action = "retrain"
                confidence = 0.78
                reasons.append(
                    f"broad drift across {drift.drifted_features_count}/{drift.total_features_checked} features"
                )
            else:
                action = "alert"
                confidence = 0.72
                reasons.append(
                    f"drift detected but below retrain threshold: max={drift.max_drift_score:.3f}"
                )

        if action == "retrain" and not guardrail.allows_retrain:
            action = "alert"
            confidence = max(confidence, 0.85)
            reasons.append("retrain blocked by operational guardrail")

        decision = DriftDecision(
            action=action,
            confidence=round(confidence, 2),
            risk_level="medium" if action == "retrain" else "low",
            reasoning=" | ".join(reasons),
            promotion_allowed=False,
            timestamp=datetime.now().isoformat(),
        )
        self.decision_history.append(decision)
        return decision
