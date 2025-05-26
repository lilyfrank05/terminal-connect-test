import pytest
import json
from datetime import datetime, timedelta
import os


def test_postbacks_page_loads(client):
    """Test that the postbacks page loads correctly."""
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"Postback Messages" in response.data


def test_postback_receiving(client, app):
    """Test receiving a postback message."""
    # Sample postback data
    postback_data = {
        "status": "success",
        "merchantReference": "test-ref",
        "transactionId": "txn_123456",
    }

    # Send postback
    response = client.post("/postback", json=postback_data)
    assert response.status_code == 200
    assert response.json == {"status": "success"}

    # Check if postback was stored
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"test-ref" in response.data
    assert b"success" in response.data


def test_postback_with_masked_headers(client, app):
    """Test that sensitive headers are masked in postbacks."""
    # Sample postback data
    postback_data = {"status": "success", "merchantReference": "test-ref"}

    # Send postback with sensitive headers
    headers = {
        "Authorization": "Bearer secret-token",
        "authorization": "Basic secret-credentials",
    }

    response = client.post("/postback", json=postback_data, headers=headers)
    assert response.status_code == 200

    # Check if headers were masked
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"***MASKED***" in response.data
    assert b"secret-token" not in response.data
    assert b"secret-credentials" not in response.data


def test_postback_clear_daily(client, app):
    """Test that postbacks are cleared daily."""
    # Ensure test files are clean
    postbacks_file = app.config["POSTBACKS_FILE"]
    meta_file = postbacks_file + ".meta"

    # Clean up any existing files
    if os.path.exists(postbacks_file):
        os.remove(postbacks_file)
    if os.path.exists(meta_file):
        os.remove(meta_file)

    # Sample postback data
    postback_data = {"status": "success", "merchantReference": "test-ref"}

    # Send postback
    response = client.post("/postback", json=postback_data)
    assert response.status_code == 200

    # Check if postback was stored
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"test-ref" in response.data

    # Simulate a new day by modifying the meta file to yesterday
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    with open(meta_file, "w") as f:
        f.write(yesterday)

    # Check if postbacks were cleared (before sending a new postback)
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"No postback messages received yet" in response.data
    assert b"test-ref" not in response.data

    # Send another postback to trigger new day logic
    response = client.post("/postback", json=postback_data)
    assert response.status_code == 200

    # Check if only the new postback is present
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"test-ref" in response.data


def test_postback_max_limit(client, app):
    """Test that postbacks are limited to 50 entries."""
    # Send 51 postbacks
    for i in range(51):
        postback_data = {"status": "success", "merchantReference": f"test-ref-{i}"}
        response = client.post("/postback", json=postback_data)
        assert response.status_code == 200

    # Check if only the last 50 postbacks are stored
    response = client.get("/postbacks")
    assert response.status_code == 200
    assert b"test-ref-0" not in response.data  # First postback should be removed
    assert b"test-ref-50" in response.data  # Last postback should be present
