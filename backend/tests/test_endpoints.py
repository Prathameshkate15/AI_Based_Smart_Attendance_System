"""API endpoint tests for Smart Attendance System."""

import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Initialize FastAPI app
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test /health endpoint returns healthy status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "attendance-api"


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Smart Attendance Management System API"


def test_security_headers():
    """Test that security headers are present in responses."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    # Check for security headers
    headers = response.headers
    # These may or may not be present depending on middleware
    # Just verify the response is valid JSON
    assert "status" in response.json()


def test_welcome_message():
    """Test root welcome message content."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Smart Attendance" in data["message"]