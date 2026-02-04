"""
CARL API Regression Tests

These tests run against a deployed CARL environment to verify key functionality
is working correctly after deployment.
"""

import json
import os
import time
import pytest
import requests


# Get API endpoint from environment variable (set by CI)
API_ENDPOINT = os.environ.get("CARL_API_ENDPOINT", "")


def skip_if_no_endpoint():
    """Skip test if no API endpoint configured."""
    if not API_ENDPOINT:
        pytest.skip("CARL_API_ENDPOINT not set - skipping API tests")


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self):
        """Health endpoint should return 200 OK."""
        skip_if_no_endpoint()

        response = requests.get(f"{API_ENDPOINT}/health", timeout=10)
        assert response.status_code == 200

    def test_health_response_format(self):
        """Health endpoint should return JSON with status field."""
        skip_if_no_endpoint()

        response = requests.get(f"{API_ENDPOINT}/health", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "ok", "OK"]


class TestSlackEndpoint:
    """Tests for the /slack endpoint."""

    def test_slack_url_verification(self):
        """Slack endpoint should respond to URL verification challenge."""
        skip_if_no_endpoint()

        payload = {
            "type": "url_verification",
            "challenge": "test_challenge_12345"
        }

        response = requests.post(
            f"{API_ENDPOINT}/slack",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        # Should return the challenge
        assert response.status_code == 200
        # Response might be plain text or JSON
        if response.headers.get("Content-Type", "").startswith("application/json"):
            data = response.json()
            assert data.get("challenge") == "test_challenge_12345"
        else:
            assert response.text == "test_challenge_12345"

    def test_slack_rejects_invalid_signature(self):
        """Slack endpoint should reject requests without valid signature."""
        skip_if_no_endpoint()

        # Send request without proper Slack signature
        payload = {
            "type": "event_callback",
            "event": {"type": "message", "text": "test"}
        }

        response = requests.post(
            f"{API_ENDPOINT}/slack",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Signature": "invalid",
                "X-Slack-Request-Timestamp": str(int(time.time()))
            },
            timeout=10
        )

        # Should reject with 401 or 403
        assert response.status_code in [401, 403, 400]


class TestAPIResponseTimes:
    """Tests for API response time requirements."""

    def test_health_responds_quickly(self):
        """Health endpoint should respond within 1 second."""
        skip_if_no_endpoint()

        start = time.time()
        response = requests.get(f"{API_ENDPOINT}/health", timeout=5)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0, f"Health check took {elapsed:.2f}s (expected < 1s)"

    def test_slack_endpoint_responds_quickly(self):
        """Slack endpoint should acknowledge within 3 seconds (Slack requirement)."""
        skip_if_no_endpoint()

        payload = {"type": "url_verification", "challenge": "timing_test"}

        start = time.time()
        response = requests.post(
            f"{API_ENDPOINT}/slack",
            json=payload,
            timeout=5
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 3.0, f"Slack endpoint took {elapsed:.2f}s (expected < 3s for Slack)"


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_for_unknown_endpoint(self):
        """Unknown endpoints should return 404."""
        skip_if_no_endpoint()

        response = requests.get(f"{API_ENDPOINT}/nonexistent", timeout=10)
        assert response.status_code == 404

    def test_invalid_json_handling(self):
        """Endpoint should handle invalid JSON gracefully."""
        skip_if_no_endpoint()

        response = requests.post(
            f"{API_ENDPOINT}/slack",
            data="not valid json",
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        # Should return 400 Bad Request, not 500
        assert response.status_code in [400, 401, 403]
