import pytest
from app import create_app
import os
import tempfile
import json


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    # Create a temporary file to store postbacks
    fd, path = tempfile.mkstemp()
    os.close(fd)

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "DEFAULT_CONFIG": {
                "ENVIRONMENT": "sandbox",
                "BASE_URL": "https://api-terminal-gateway.tillvision.show/devices",
                "MID": "test-mid",
                "TID": "test-tid",
                "API_KEY": "test-api-key",
            },
        }
    )

    # Override the postbacks file path for testing
    app.config["POSTBACKS_FILE"] = path

    yield app

    # Clean up
    os.unlink(path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "environment": "sandbox",
        "mid": "test-mid",
        "tid": "test-tid",
        "api_key": "test-api-key",
        "postback_url": "http://localhost:5001/postback",
    }


@pytest.fixture
def mock_intent_response():
    """Mock API response for intent creation."""
    return {"intentId": "123e4567-e89b-12d3-a456-426614174000", "status": "created"}


@pytest.fixture
def mock_process_response():
    """Mock API response for intent processing."""
    return {
        "status": "success",
        "transactionId": "txn_123456",
        "merchantReference": "test-ref",
    }
