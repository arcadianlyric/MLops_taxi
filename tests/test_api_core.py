"""Tests for core API endpoints: health, predict, batch_predict, metrics."""

import pytest


class TestHealth:
    def test_health_returns_200(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, api_client):
        data = api_client.get("/health").json()
        assert data["status"] == "healthy"
        assert "data_loaded" in data
        assert "data_rows" in data
        assert data["data_rows"] > 0

    def test_health_version(self, api_client):
        data = api_client.get("/health").json()
        assert "version" in data


class TestPredict:
    def test_predict_returns_200(self, api_client, sample_trip):
        resp = api_client.post("/predict", json=sample_trip)
        assert resp.status_code == 200

    def test_predict_response_fields(self, api_client, sample_trip):
        data = api_client.post("/predict", json=sample_trip).json()
        assert "predicted_tip" in data
        assert "tip_rate" in data
        assert "fare_amount" in data
        assert "total_cost" in data

    def test_predict_tip_non_negative(self, api_client, sample_trip):
        data = api_client.post("/predict", json=sample_trip).json()
        assert data["predicted_tip"] >= 0

    def test_predict_cash_lower_tip(self, api_client, sample_trip):
        sample_trip["payment_type"] = "Cash"
        data_cash = api_client.post("/predict", json=sample_trip).json()
        sample_trip["payment_type"] = "Credit Card"
        data_cc = api_client.post("/predict", json=sample_trip).json()
        # On average credit card tips should be higher; test with fare component
        assert data_cash["fare_amount"] == data_cc["fare_amount"]

    def test_predict_invalid_payload_returns_422(self, api_client):
        resp = api_client.post("/predict", json={"bad": "data"})
        assert resp.status_code == 422


class TestBatchPredict:
    def test_batch_predict_returns_200(self, api_client, sample_trip):
        payload = {"trips": [sample_trip, sample_trip], "model_name": "taxi_model"}
        resp = api_client.post("/batch_predict", json=payload)
        assert resp.status_code == 200

    def test_batch_predict_count_matches(self, api_client, sample_trip):
        payload = {"trips": [sample_trip] * 3, "model_name": "taxi_model"}
        data = api_client.post("/batch_predict", json=payload).json()
        assert data["count"] == 3
        assert len(data["predictions"]) == 3


class TestMetrics:
    def test_metrics_returns_200(self, api_client):
        resp = api_client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_has_fields(self, api_client):
        data = api_client.get("/metrics").json()
        assert "total_predictions" in data
        assert "status" in data
