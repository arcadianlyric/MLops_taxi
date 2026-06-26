"""Monitor agent for taxi data drift reports.

This module intentionally consumes the existing /data/drift payload instead of
recomputing drift in a second place. The agent layer summarizes that operational
signal into a compact decision input.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class DriftSignal:
    """Normalized drift signal used by the evaluator agent."""

    overall_drift: bool
    max_drift_score: float
    drifted_features: List[Dict[str, Any]]
    total_features_checked: int
    drifted_features_count: int
    threshold: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_drift": self.overall_drift,
            "max_drift_score": self.max_drift_score,
            "drifted_features": self.drifted_features,
            "total_features_checked": self.total_features_checked,
            "drifted_features_count": self.drifted_features_count,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
        }


class TaxiDriftMonitor:
    """Extract decision-ready drift state from the taxi drift API payload."""

    def monitor(self, drift_payload: Dict[str, Any]) -> DriftSignal:
        summary = drift_payload.get("summary", {})
        feature_details = drift_payload.get("feature_details", {})

        drifted_features: List[Dict[str, Any]] = []
        max_score = 0.0
        for feature, detail in feature_details.items():
            score = float(detail.get("drift_score", 0.0) or 0.0)
            max_score = max(max_score, score)
            if detail.get("is_drifted", False):
                drifted_features.append(
                    {
                        "feature": feature,
                        "score": round(score, 3),
                        "drift_type": detail.get("drift_type", "Unknown"),
                    }
                )

        return DriftSignal(
            overall_drift=bool(summary.get("overall_drift_detected", False)),
            max_drift_score=round(max_score, 3),
            drifted_features=sorted(
                drifted_features,
                key=lambda item: item["score"],
                reverse=True,
            ),
            total_features_checked=int(summary.get("total_features_checked", len(feature_details))),
            drifted_features_count=int(summary.get("drifted_features_count", len(drifted_features))),
            threshold=float(summary.get("threshold", 0.1) or 0.1),
            timestamp=summary.get("timestamp", datetime.now().isoformat()),
        )
