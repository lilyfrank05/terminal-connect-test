import pytest
import requests_mock


def test_reversal_page_loads(client):
    """Test that the reversal page loads correctly."""
    response = client.get("/reversal")
    assert response.status_code == 200
    assert b"Reversal" in response.data


def test_reversal_success(
    client, mock_config, mock_intent_response, mock_process_response
):
    """Test successful reversal transaction."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API responses
    with requests_mock.Mocker() as m:
        # Mock intent creation
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
            json=mock_intent_response,
        )

        # Mock intent processing
        m.post(
            f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
            json=mock_process_response,
        )

        # Make reversal request
        response = client.post(
            "/reversal",
            data={
                "merchant_reference": "test-ref",
                "parent_intent_id": "550e8400-e29b-41d4-a716-446655440000",
            },
        )
        assert response.status_code == 302  # Redirect after successful reversal

        # Check flashed messages in the session immediately after POST
        with client.session_transaction() as sess:
            flashed = sess.get("_flashes", [])
            assert any(
                "Successfully processed Intent ID" in msg for cat, msg in flashed
            )


def test_reversal_without_parent_id(client, mock_config):
    """Test reversal without parent intent ID."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Make reversal request without parent intent ID
    response = client.post(
        "/reversal",
        data={"merchant_reference": "test-ref"},
    )
    assert response.status_code == 302  # Redirect after error

    # Follow the redirect to get the flash message
    response = client.get(response.headers["Location"])
    assert response.status_code == 200
    assert b"Original Sale Reference is required" in response.data


def test_reversal_with_invalid_parent_id(client, mock_config):
    """Test reversal with invalid parent intent ID."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Make reversal request with invalid parent intent ID
    response = client.post(
        "/reversal",
        data={
            "merchant_reference": "test-ref",
            "parent_intent_id": "invalid-uuid",
        },
    )
    assert response.status_code == 302  # Redirect after error

    # Follow the redirect to get the flash message
    response = client.get(response.headers["Location"])
    assert response.status_code == 200
    assert b"Original Sale Reference must be a valid UUID v4" in response.data


def test_reversal_api_error(client, mock_config):
    """Test reversal with API error."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API error
    with requests_mock.Mocker() as m:
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
            status_code=400,
            json={"message": "API Error"},
        )

        # Make reversal request
        response = client.post(
            "/reversal",
            data={
                "merchant_reference": "test-ref",
                "parent_intent_id": "550e8400-e29b-41d4-a716-446655440000",
            },
        )
        assert response.status_code == 302  # Redirect after error

        # Check flashed messages in the session immediately after POST
        with client.session_transaction() as sess:
            flashed = sess.get("_flashes", [])
            assert any("API Error" in msg for cat, msg in flashed)
