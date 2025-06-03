import pytest
import requests_mock
from flask import session


def test_unlinked_refund_page_loads(client):
    """Test that the unlinked refund page loads correctly."""
    response = client.get("/unlinked-refund")
    assert response.status_code == 200
    assert b"Unlinked Refund" in response.data


def test_linked_refund_page_loads(client):
    """Test that the linked refund page loads correctly."""
    response = client.get("/linked-refund")
    assert response.status_code == 200
    assert b"Linked Refund" in response.data


def test_unlinked_refund_success(
    client, mock_config, mock_intent_response, mock_process_response
):
    """Test successful unlinked refund transaction."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API responses
    with requests_mock.Mocker() as m:
        # Mock intent creation
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
            json=mock_intent_response,
        )

        # Mock intent processing
        m.post(
            f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
            json=mock_process_response,
        )

        # Make refund request
        response = client.post(
            "/unlinked-refund",
            data={"amount": "10.00", "merchant_reference": "test-ref"},
        )
        assert response.status_code == 302  # Redirect after successful refund

        # Follow the redirect to get the flash message
        response = client.get(response.headers["Location"])
        assert response.status_code == 200
        assert b"Successfully processed Intent ID" in response.data


def test_linked_refund_success(
    client, mock_config, mock_intent_response, mock_process_response
):
    """Test successful linked refund transaction."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API responses
    with requests_mock.Mocker() as m:
        # Mock intent creation
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
            json=mock_intent_response,
        )

        # Mock intent processing
        m.post(
            f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
            json=mock_process_response,
        )

        # Make linked refund request
        response = client.post(
            "/linked-refund",
            data={
                "amount": "10.00",
                "merchant_reference": "test-ref",
                "parent_intent_id": "123e4567-e89b-12d3-a456-426614174000",
                "via_pinpad": "yes",
            },
        )
        assert response.status_code == 302  # Redirect after successful refund

        # Follow the redirect to get the flash message
        response = client.get(response.headers["Location"])
        assert response.status_code == 200
        assert b"Successfully processed Intent ID" in response.data


def test_linked_refund_without_parent_id(client, mock_config):
    """Test linked refund without parent intent ID."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Make linked refund request without parent intent ID
    response = client.post(
        "/linked-refund",
        data={"amount": "10.00", "merchant_reference": "test-ref", "via_pinpad": "yes"},
    )
    assert response.status_code == 302  # Redirect after error

    # Follow the redirect to get the flash message
    response = client.get(response.headers["Location"])
    assert response.status_code == 200
    assert b"Original Sale Reference is required" in response.data


def test_linked_refund_with_invalid_parent_id(client, mock_config):
    """Test linked refund with invalid parent intent ID."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Make linked refund request with invalid parent intent ID
    response = client.post(
        "/linked-refund",
        data={
            "amount": "10.00",
            "merchant_reference": "test-ref",
            "parent_intent_id": "invalid-uuid",
            "via_pinpad": "yes",
        },
    )
    assert response.status_code == 302  # Redirect after error

    # Follow the redirect to get the flash message
    response = client.get(response.headers["Location"])
    assert response.status_code == 200
    assert b"Original Sale Reference must be a valid UUID v4" in response.data


def test_refund_api_error(client, mock_config):
    """Test refund with API error."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API error
    with requests_mock.Mocker() as m:
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
            status_code=400,
            json={"message": "API Error"},
        )

        # Make refund request
        response = client.post(
            "/unlinked-refund",
            data={"amount": "10.00", "merchant_reference": "test-ref"},
        )
        assert response.status_code == 302  # Redirect after error

        # Follow the redirect to get the flash message
        response = client.get(response.headers["Location"])
        assert response.status_code == 200
        assert b"API Error" in response.data
