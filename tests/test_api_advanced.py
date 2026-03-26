"""Tests for advanced feature API endpoints: Feast, Kafka, MLflow, MLMD."""

import pytest


class TestFeast:
    def test_feast_info(self, api_client):
        resp = api_client.get("/feast/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["total_features"] > 0

    def test_feast_feature_views(self, api_client):
        resp = api_client.get("/feast/feature-views")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        for view in data["data"]:
            assert "name" in view
            assert "features" in view

    def test_feast_feature_services(self, api_client):
        resp = api_client.get("/feast/feature-services")
        assert resp.status_code == 200
        assert resp.json()["count"] > 0

    def test_feast_online_features(self, api_client):
        payload = {"entity_ids": ["trip_001", "trip_002"], "feature_service": "v1"}
        resp = api_client.post("/feast/online-features", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_count"] == 2

    def test_feast_historical_features(self, api_client):
        payload = {"features": ["fare", "tips", "trip_miles"]}
        resp = api_client.post("/feast/historical-features", json=payload)
        assert resp.status_code == 200


class TestKafka:
    def test_kafka_info(self, api_client):
        resp = api_client.get("/kafka/info")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["topic_count"] > 0

    def test_kafka_topics(self, api_client):
        resp = api_client.get("/kafka/topics")
        assert resp.status_code == 200
        assert resp.json()["count"] > 0

    def test_kafka_topic_detail(self, api_client):
        resp = api_client.get("/kafka/topics/taxi-raw-data")
        assert resp.status_code == 200

    def test_kafka_stream_processors(self, api_client):
        resp = api_client.get("/kafka/stream-processors")
        assert resp.status_code == 200
        procs = resp.json()["data"]
        assert len(procs) > 0
        for p in procs:
            assert "processor_name" in p
            assert "status" in p


class TestMLflow:
    def test_mlflow_info(self, api_client):
        resp = api_client.get("/mlflow/info")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] in ("connected", "mock_mode")

    def test_mlflow_experiments(self, api_client):
        resp = api_client.get("/mlflow/experiments")
        assert resp.status_code == 200
        assert resp.json()["count"] > 0

    def test_mlflow_models(self, api_client):
        resp = api_client.get("/mlflow/models")
        assert resp.status_code == 200
        models = resp.json()["data"]
        assert len(models) > 0
        assert "name" in models[0]

    def test_mlflow_model_predict(self, api_client):
        payload = {
            "model_name": "chicago-taxi-fare-predictor",
            "model_version": "3",
            "model_stage": "Production",
            "input_data": {"fare": 15.0, "trip_miles": 5.0},
        }
        resp = api_client.post("/mlflow/models/predict", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "prediction" in data
        assert "confidence" in data


class TestMLMD:
    def test_mlmd_info(self, api_client):
        resp = api_client.get("/mlmd/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["total_artifacts"] > 0

    def test_mlmd_lineage_graph(self, api_client):
        resp = api_client.get("/mlmd/lineage/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert data["metadata"]["total_nodes"] > 0

    def test_mlmd_artifacts(self, api_client):
        resp = api_client.get("/mlmd/lineage/artifacts")
        assert resp.status_code == 200

    def test_mlmd_executions(self, api_client):
        resp = api_client.get("/mlmd/lineage/executions")
        assert resp.status_code == 200
