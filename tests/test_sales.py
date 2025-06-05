import pytest
import requests_mock

# from flask import session  # Unused, remove


def test_sale_page_loads(client):
    """Test that the sale page loads correctly."""
    response = client.get("/sale")
    assert response.status_code == 200
    assert b"Sale" in response.data


def test_sale_without_config(client):
    """Test sale attempt without configuration."""
    with requests_mock.Mocker() as m:
        # Mock the request to avoid TLS certificate issues
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/payment",
            json={"message": "Missing configuration"},
            status_code=400,
        )

        response = client.post(
            "/sale", data={"amount": "10.00", "merchant_reference": "test-ref"}
        )
        assert response.status_code == 302  # Redirect after error

        # Follow the redirect to get the flash message
        response = client.get(response.headers["Location"])
        assert response.status_code == 200
        assert b"Error creating payment intent: Missing configuration" in response.data


def test_sale_with_invalid_amount(client, mock_config):
    """Test sale with invalid amount."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Test with invalid amount
    response = client.post(
        "/sale", data={"amount": "invalid", "merchant_reference": "test-ref"}
    )
    assert response.status_code == 302

    # Follow the redirect to get the flash message
    response = client.get(response.headers["Location"])
    assert response.status_code == 200
    assert b"Invalid amount format" in response.data


def test_sale_success(client, mock_config, mock_intent_response, mock_process_response):
    """Test successful sale transaction."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API responses
    with requests_mock.Mocker() as m:
        # Mock intent creation
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/payment",
            json=mock_intent_response,
        )

        # Mock intent processing
        m.post(
            f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
            json=mock_process_response,
        )

        # Make sale request
        response = client.post(
            "/sale", data={"amount": "10.00", "merchant_reference": "test-ref"}
        )
        assert response.status_code == 302  # Redirect after successful sale

        # Follow the redirect to get the flash message
        response = client.get(response.headers["Location"])
        assert response.status_code == 200
        assert b"Successfully processed Intent ID" in response.data


def test_sale_api_error(client, mock_config):
    """Test sale with API error."""
    # Set up configuration
    client.post("/config", data=mock_config)

    # Mock API error
    with requests_mock.Mocker() as m:
        m.post(
            "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/payment",
            status_code=400,
            json={"message": "API Error"},
        )

        # Make sale request
        response = client.post(
            "/sale", data={"amount": "10.00", "merchant_reference": "test-ref"}
        )
        assert response.status_code == 302  # Redirect after error

        # Follow the redirect to get the flash message
        response = client.get(response.headers["Location"])
        assert response.status_code == 200
        assert b"API Error" in response.data
