"""Tests for the agentic drift-to-retrain control loop."""

from datetime import datetime


def _drift_payload(max_score=0.4, drifted=True):
    return {
        "summary": {
            "timestamp": datetime.now().isoformat(),
            "overall_drift_detected": drifted,
            "threshold": 0.1,
            "total_features_checked": 3,
            "drifted_features_count": 1 if drifted else 0,
            "baseline_rows": 100,
            "current_rows": 100,
        },
        "feature_details": {
            "fare": {
                "drift_score": max_score if drifted else 0.02,
                "is_drifted": drifted,
                "drift_type": "Medium" if drifted else "No",
            },
            "trip_miles": {
                "drift_score": 0.03,
                "is_drifted": False,
                "drift_type": "No",
            },
            "trip_seconds": {
                "drift_score": 0.04,
                "is_drifted": False,
                "drift_type": "No",
            },
        },
    }


def _status(last_retrain=None, in_progress=False):
    return {
        "last_retrain": last_retrain,
        "retrain_in_progress": in_progress,
        "cooldown_minutes": 30,
        "drift_threshold": 0.3,
        "model_meta": {"test_r2": 0.79, "test_mae": 0.36},
    }


def test_agent_recommends_retrain_without_promotion():
    from agentic.orchestrator import TaxiDriftRetrainOrchestrator

    orchestrator = TaxiDriftRetrainOrchestrator()
    result = orchestrator.run(_drift_payload(max_score=0.45), _status())

    assert result["action"] == "retrain_recommended"
    assert result["promotion_allowed"] is False
    assert result["retrain_result"]["executed"] is False
    assert result["evaluation_decision"]["action"] == "retrain"


def test_agent_ignores_low_drift():
    from agentic.orchestrator import TaxiDriftRetrainOrchestrator

    orchestrator = TaxiDriftRetrainOrchestrator()
    result = orchestrator.run(_drift_payload(drifted=False), _status())

    assert result["action"] == "ignore"
    assert result["retrain_result"] is None


def test_agent_blocks_retrain_during_cooldown():
    from agentic.orchestrator import TaxiDriftRetrainOrchestrator

    orchestrator = TaxiDriftRetrainOrchestrator()
    result = orchestrator.run(
        _drift_payload(max_score=0.6),
        _status(last_retrain=datetime.now().isoformat()),
        execute_retrain=True,
    )

    assert result["action"] == "alert"
    assert result["retrain_result"] is None
    assert result["retrain_guardrail"]["cooldown_active"] is True


def test_agent_executes_retrain_when_explicitly_enabled():
    from agentic.orchestrator import TaxiDriftRetrainOrchestrator
    from agentic.retrainer import TaxiRetrainerAgent

    calls = []

    def fake_trigger(reason):
        calls.append(reason)
        return {"status": "retrain_started", "reason": reason}

    orchestrator = TaxiDriftRetrainOrchestrator(
        retrainer=TaxiRetrainerAgent(trigger_fn=fake_trigger)
    )
    result = orchestrator.run(_drift_payload(max_score=0.5), _status(), execute_retrain=True)

    assert result["action"] == "retrain_triggered"
    assert result["retrain_result"]["executed"] is True
    assert calls and calls[0].startswith("agentic_drift")


def test_agentic_api_endpoint_dry_run(api_client):
    resp = api_client.post("/agentic/drift-retrain/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "action" in data
    assert "trace" in data
    assert data["promotion_allowed"] is False
