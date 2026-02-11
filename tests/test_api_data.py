"""Tests for data analysis and drift API endpoints."""

import pytest


class TestDataStats:
    def test_stats_returns_200(self, api_client):
        resp = api_client.get("/data/stats")
        assert resp.status_code == 200

    def test_stats_has_total_rows(self, api_client):
        data = api_client.get("/data/stats").json()
        assert data["total_rows"] > 0

    def test_stats_has_fare_and_tips(self, api_client):
        stats = api_client.get("/data/stats").json()["data"]
        assert "fare" in stats
        assert "tips" in stats
        assert stats["fare"]["mean"] > 0

    def test_stats_has_hourly(self, api_client):
        stats = api_client.get("/data/stats").json()["data"]
        assert "hourly" in stats
        assert len(stats["hourly"]) == 24

    def test_stats_has_payment_type(self, api_client):
        stats = api_client.get("/data/stats").json()["data"]
        assert "by_payment_type" in stats
        assert len(stats["by_payment_type"]) > 0

    def test_stats_has_company(self, api_client):
        stats = api_client.get("/data/stats").json()["data"]
        assert "by_company" in stats
        assert len(stats["by_company"]) > 0


class TestDataDrift:
    def test_drift_returns_200(self, api_client):
        resp = api_client.get("/data/drift")
        assert resp.status_code == 200

    def test_drift_has_summary(self, api_client):
        data = api_client.get("/data/drift").json()
        s = data["summary"]
        assert "total_features_checked" in s
        assert "drifted_features_count" in s
        assert "baseline_rows" in s
        assert "current_rows" in s
        assert s["baseline_rows"] > 0

    def test_drift_has_feature_details(self, api_client):
        data = api_client.get("/data/drift").json()
        details = data["feature_details"]
        assert len(details) > 0
        for feat, info in details.items():
            assert "drift_score" in info
            assert "is_drifted" in info
            assert "drift_type" in info
            assert isinstance(info["drift_score"], (int, float))
            assert isinstance(info["is_drifted"], bool)

    def test_drift_has_recommendations(self, api_client):
        data = api_client.get("/data/drift").json()
        assert "recommendations" in data
        assert len(data["recommendations"]) > 0
