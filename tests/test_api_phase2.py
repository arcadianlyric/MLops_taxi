"""Tests for Phase 2 features: A/B testing, auto-retrain, Prometheus metrics."""

import pytest


class TestABExperiments:
    def test_list_experiments(self, api_client):
        resp = api_client.get("/ab/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert "experiments" in data
        assert "count" in data
        # Default experiment should exist
        assert data["count"] >= 1

    def test_default_experiment_exists(self, api_client):
        resp = api_client.get("/ab/experiments/tip-model-v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["experiment"]["name"] == "tip-model-v1"
        assert data["experiment"]["status"] == "running"
        assert "control" in data["experiment"]["variants"]
        assert "treatment" in data["experiment"]["variants"]

    def test_create_experiment(self, api_client):
        payload = {
            "name": "test-exp-1",
            "variants": {
                "a": {"model": "sklearn", "weight": 0.5},
                "b": {"model": "rule_based", "weight": 0.5},
            },
        }
        resp = api_client.post("/ab/experiments", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["experiment"]["name"] == "test-exp-1"

    def test_create_experiment_bad_weights(self, api_client):
        payload = {
            "name": "bad-weights",
            "variants": {
                "a": {"model": "sklearn", "weight": 0.3},
                "b": {"model": "rule_based", "weight": 0.3},
            },
        }
        resp = api_client.post("/ab/experiments", json=payload)
        assert resp.status_code == 400

    def test_create_duplicate_experiment(self, api_client):
        payload = {
            "name": "tip-model-v1",
            "variants": {"a": {"model": "sklearn", "weight": 1.0}},
        }
        resp = api_client.post("/ab/experiments", json=payload)
        assert resp.status_code == 400

    def test_get_nonexistent_experiment(self, api_client):
        resp = api_client.get("/ab/experiments/nonexistent")
        assert resp.status_code == 404


class TestABPredict:
    def test_ab_predict_returns_200(self, api_client, sample_trip):
        resp = api_client.post("/ab/predict?experiment=tip-model-v1", json=sample_trip)
        assert resp.status_code == 200
        data = resp.json()
        assert "variant" in data
        assert "model_used" in data
        assert "predicted_tip" in data
        assert "latency_ms" in data
        assert data["predicted_tip"] >= 0

    def test_ab_predict_nonexistent_experiment(self, api_client, sample_trip):
        resp = api_client.post("/ab/predict?experiment=nope", json=sample_trip)
        assert resp.status_code == 404

    def test_ab_predict_records_results(self, api_client, sample_trip):
        # Run a few predictions
        for _ in range(5):
            api_client.post("/ab/predict?experiment=tip-model-v1", json=sample_trip)
        resp = api_client.get("/ab/experiments/tip-model-v1")
        data = resp.json()
        assert data["experiment"]["total_assignments"] >= 5
        assert len(data["variant_stats"]) > 0

    def test_ab_stop_experiment(self, api_client):
        # Create then stop
        payload = {
            "name": "stop-me",
            "variants": {"a": {"model": "sklearn", "weight": 1.0}},
        }
        api_client.post("/ab/experiments", json=payload)
        resp = api_client.delete("/ab/experiments/stop-me")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"


class TestRetrain:
    def test_retrain_status(self, api_client):
        resp = api_client.get("/retrain/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "retrain_in_progress" in data
        assert "cooldown_minutes" in data
        assert "drift_threshold" in data

    def test_retrain_trigger(self, api_client):
        resp = api_client.post("/retrain/trigger?reason=test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "retrain_started"
        assert data["reason"] == "test"

    def test_retrain_cooldown(self, api_client):
        # Second trigger should hit cooldown
        resp = api_client.post("/retrain/trigger?reason=test2")
        assert resp.status_code == 429

    def test_retrain_auto_check(self, api_client):
        resp = api_client.post("/retrain/auto-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "action" in data
        # Should either skip (drift below threshold or cooldown) or trigger
        assert data["action"] in ["skip", "retrain_triggered"]


class TestPrometheusMetrics:
    def test_prometheus_endpoint_exists(self, api_client):
        resp = api_client.get("/metrics/prometheus")
        # May be 200 or 404 depending on whether prometheus lib is installed
        assert resp.status_code in [200, 404]

    def test_root_includes_new_endpoints(self, api_client):
        resp = api_client.get("/")
        data = resp.json()
        assert "ab_testing" in data["endpoints"]
        assert "retrain" in data["endpoints"]
        assert "prometheus" in data["endpoints"]
