"""Retrainer agent wrapper.

The retrainer agent separates "decision to retrain" from "model promotion".
It can run in dry-run mode for safe demos and tests.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional


@dataclass
class AgentRetrainResult:
    executed: bool
    status: str
    reason: str
    trigger_response: Optional[Dict[str, Any]]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executed": self.executed,
            "status": self.status,
            "reason": self.reason,
            "trigger_response": self.trigger_response,
            "timestamp": self.timestamp,
        }


class TaxiRetrainerAgent:
    """Execute or simulate retrain after the evaluator allows it."""

    def __init__(self, trigger_fn: Optional[Callable[[str], Dict[str, Any]]] = None):
        self.trigger_fn = trigger_fn

    def trigger(self, reason: str, execute: bool = False) -> AgentRetrainResult:
        if not execute:
            return AgentRetrainResult(
                executed=False,
                status="dry_run",
                reason=reason,
                trigger_response=None,
                timestamp=datetime.now().isoformat(),
            )

        if self.trigger_fn is None:
            return AgentRetrainResult(
                executed=False,
                status="missing_trigger_fn",
                reason=reason,
                trigger_response=None,
                timestamp=datetime.now().isoformat(),
            )

        response = self.trigger_fn(reason)
        return AgentRetrainResult(
            executed=True,
            status="triggered",
            reason=reason,
            trigger_response=response,
            timestamp=datetime.now().isoformat(),
        )
