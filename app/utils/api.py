import requests
from flask import current_app, flash, session
import os
import certifi

from .validation import validate_config
from .helpers import get_postback_url

ENVIRONMENT_URLS = {
    "production": "https://api-terminal-gateway.tillpayments.com/devices",
    "sandbox": "https://api-terminal-gateway.tillvision.show/devices",
    "dev-test": "https://api-terminal-gateway.tillpayments.dev/devices",
}

# Use system CA bundle for Docker compatibility, fallback to certifi for local development
VERIFY_PATH = (
    "/etc/ssl/certs/ca-certificates.crt"
    if os.path.exists("/etc/ssl/certs/ca-certificates.crt")
    else certifi.where()
)


def _get_timeout_seconds():
    """Return configured API request timeout in seconds (default 60)."""
    try:
        timeout_val = int(current_app.config.get("API_REQUEST_TIMEOUT", 60))
        # enforce sane bounds: 1s - 300s
        if timeout_val < 1:
            return 60
        if timeout_val > 300:
            return 300
        return timeout_val
    except Exception:
        return 60


def make_api_request(endpoint, method="POST", payload=None):
    """Helper function to make API requests with proper headers and error handling"""
    if not validate_config():
        return None, "Missing configuration values"

    # Get values from session, with defaults as fallback
    defaults = current_app.config["DEFAULT_CONFIG"]
    api_key = session.get("API_KEY", defaults["API_KEY"])
    base_url = session.get("BASE_URL", defaults["BASE_URL"])
    postback_url = get_postback_url()

    headers = {"Content-Type": "application/json", "x-api-key": api_key}

    url = f"{base_url}{endpoint}"

    # Add postback URL to payload if it's a payment, refund, or reversal request
    if payload and endpoint.endswith(("/payment", "/refund", "/reversal")):
        payload["postbackUrl"] = postback_url
        # Log for debugging delay functionality
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Added postback URL to {endpoint}: {postback_url}")

    try:
        timeout_seconds = _get_timeout_seconds()
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
            verify=VERIFY_PATH,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, f"Request timed out after {timeout_seconds} seconds"
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e.response, "json"):
            try:
                error_data = e.response.json()
                error_message = error_data.get("message", str(e))
            except:
                pass
        return None, error_message


def process_intent(intent_id):
    """Helper function for the second API call to process the intent"""
    if not validate_config():
        return None, "Missing configuration values"

    # Get values from session, with defaults as fallback
    defaults = current_app.config["DEFAULT_CONFIG"]
    mid = session.get("MID", defaults["MID"])
    tid = session.get("TID", defaults["TID"])

    endpoint = f"/merchant/{mid}/intent/{intent_id}/process"
    payload = {"tid": tid}

    response_data, error = make_api_request(endpoint, payload=payload)
    return response_data, error
