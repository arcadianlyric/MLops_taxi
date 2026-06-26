"""Agentic drift-to-retrain orchestrator for the taxi MLOps project."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .drift_evaluator import TaxiDriftEvaluator
from .drift_monitor import TaxiDriftMonitor
from .policy import TaxiRetrainPolicy
from .retrainer import TaxiRetrainerAgent


class TaxiDriftRetrainOrchestrator:
    """Run monitor -> policy -> evaluate -> optional retrain.

    This mirrors agentic_GEM's agent loop while preserving a taxi-specific
    guardrail: retraining can be automated, but model promotion is never
    automated by this agent.
    """

    def __init__(
        self,
        monitor: Optional[TaxiDriftMonitor] = None,
        evaluator: Optional[TaxiDriftEvaluator] = None,
        policy: Optional[TaxiRetrainPolicy] = None,
        retrainer: Optional[TaxiRetrainerAgent] = None,
    ):
        self.monitor = monitor or TaxiDriftMonitor()
        self.evaluator = evaluator or TaxiDriftEvaluator()
        self.policy = policy or TaxiRetrainPolicy()
        self.retrainer = retrainer or TaxiRetrainerAgent()
        self.run_history: List[Dict[str, Any]] = []

    def run(
        self,
        drift_payload: Dict[str, Any],
        retrain_status: Dict[str, Any],
        execute_retrain: bool = False,
    ) -> Dict[str, Any]:
        trace = []

        drift_signal = self.monitor.monitor(drift_payload)
        trace.append(
            {
                "agent": "TaxiDriftMonitor",
                "step": "monitor",
                "status": "ok",
                "summary": {
                    "max_drift_score": drift_signal.max_drift_score,
                    "drifted_features_count": drift_signal.drifted_features_count,
                },
            }
        )

        data_quality = self.policy.evaluate_data_quality(drift_payload)
        guardrail = self.policy.evaluate_retrain_guardrail(retrain_status)
        trace.append(
            {
                "agent": "TaxiRetrainPolicy",
                "step": "guardrails",
                "status": "ok" if data_quality.passed and guardrail.allows_retrain else "blocked_or_watch",
                "summary": {
                    "data_quality": data_quality.status,
                    "cooldown_active": guardrail.cooldown_active,
                    "retrain_in_progress": guardrail.retrain_in_progress,
                },
            }
        )

        decision = self.evaluator.evaluate(drift_signal, data_quality, guardrail)
        trace.append(
            {
                "agent": "TaxiDriftEvaluator",
                "step": "decide",
                "status": decision.action,
                "summary": {
                    "confidence": decision.confidence,
                    "risk_level": decision.risk_level,
                    "promotion_allowed": decision.promotion_allowed,
                },
            }
        )

        retrain_result = None
        action = decision.action
        if decision.action == "retrain":
            reason = f"agentic_drift:max_score={drift_signal.max_drift_score}"
            retrain_result = self.retrainer.trigger(reason=reason, execute=execute_retrain)
            action = "retrain_triggered" if retrain_result.executed else "retrain_recommended"
            trace.append(
                {
                    "agent": "TaxiRetrainerAgent",
                    "step": "act",
                    "status": retrain_result.status,
                    "summary": {
                        "executed": retrain_result.executed,
                        "promotion_allowed": False,
                    },
                }
            )

        result = {
            "action": action,
            "execute_retrain": execute_retrain,
            "drift_signal": drift_signal.to_dict(),
            "data_quality_gate": data_quality.to_dict(),
            "retrain_guardrail": guardrail.to_dict(),
            "evaluation_decision": decision.to_dict(),
            "retrain_result": retrain_result.to_dict() if retrain_result else None,
            "promotion_allowed": False,
            "promotion_policy": "blocked: retrain agent never promotes models automatically",
            "trace": trace,
            "timestamp": datetime.now().isoformat(),
        }
        self.run_history.append(result)
        return result

    def get_run_history(self, last_n: int = 10) -> List[Dict[str, Any]]:
        return self.run_history[-last_n:]
