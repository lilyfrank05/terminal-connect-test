import pytest
from flask import session


def test_config_page_loads(client):
    """Test that the configuration page loads correctly."""
    response = client.get("/config")
    assert response.status_code == 200
    assert b"Terminal Connect Configuration" in response.data


def test_config_update(client, mock_config):
    """Test updating configuration."""
    response = client.post("/config", data=mock_config)
    assert response.status_code == 302  # Redirect after successful update

    # Check that values are stored in session
    with client.session_transaction() as session:
        assert session["ENVIRONMENT"] == mock_config["environment"]
        assert session["MID"] == mock_config["mid"]
        assert session["TID"] == mock_config["tid"]
        assert session["API_KEY"] == mock_config["api_key"]
        assert session["POSTBACK_URL"] == mock_config["postback_url"]


def test_config_validation(client):
    """Test configuration validation."""
    # Test with missing required fields
    response = client.post("/config", data={})
    assert response.status_code == 200  # Returns to form
    assert b"MID is required" in response.data
    assert b"TID is required" in response.data
    assert b"API_KEY is required" in response.data
    assert b"POSTBACK_URL is required" in response.data


def test_config_environment_switch(client):
    """Test switching between sandbox and production environments."""
    # Test sandbox environment
    response = client.post(
        "/config",
        data={
            "environment": "sandbox",
            "mid": "test-mid",
            "tid": "test-tid",
            "api_key": "test-api-key",
            "postback_url": "http://localhost:5001/postback",
        },
    )
    assert response.status_code == 302

    with client.session_transaction() as session:
        assert (
            session["BASE_URL"]
            == "https://api-terminal-gateway.tillvision.show/devices"
        )

    # Test production environment
    response = client.post(
        "/config",
        data={
            "environment": "production",
            "mid": "test-mid",
            "tid": "test-tid",
            "api_key": "test-api-key",
            "postback_url": "http://localhost:5001/postback",
        },
    )
    assert response.status_code == 302

    with client.session_transaction() as session:
        assert (
            session["BASE_URL"]
            == "https://api-terminal-gateway.tillpayments.com/devices"
        )
