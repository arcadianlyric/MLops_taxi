"""Shared pytest fixtures for the taxi MLOps test suite."""

import os
import sys
import pytest

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "api"))


@pytest.fixture(scope="session")
def api_client():
    """Create a TestClient for the FastAPI app (session-scoped)."""
    from fastapi.testclient import TestClient
    from api.taxi_full_api import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_trip():
    """Return a valid single-trip payload."""
    return {
        "trip_miles": 5.2,
        "trip_seconds": 900,
        "fare": 12.50,
        "pickup_latitude": 41.8781,
        "pickup_longitude": -87.6298,
        "dropoff_latitude": 41.8881,
        "dropoff_longitude": -87.6198,
        "pickup_hour": 14,
        "pickup_day_of_week": 2,
        "trip_start_day": 15,
        "trip_start_month": 6,
        "pickup_community_area": 8,
        "dropoff_community_area": 24,
        "pickup_census_tract": 170301,
        "dropoff_census_tract": 170401,
        "payment_type": "Credit Card",
        "company": "Flash Cab",
        "passenger_count": 1,
    }
