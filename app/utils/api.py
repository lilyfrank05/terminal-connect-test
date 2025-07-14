import requests
from flask import current_app, flash, session, url_for
import os
import certifi

from .validation import validate_config

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


def make_api_request(endpoint, method="POST", payload=None):
    """Helper function to make API requests with proper headers and error handling"""
    if not validate_config():
        return None, "Missing configuration values"

    # Get values from session, with defaults as fallback
    defaults = current_app.config["DEFAULT_CONFIG"]
    api_key = session.get("API_KEY", defaults["API_KEY"])
    base_url = session.get("BASE_URL", defaults["BASE_URL"])
    postback_url = session.get("POSTBACK_URL")
    if not postback_url:
        # Generate default postback URL based on user authentication
        if session.get("user_id"):
            postback_url = url_for(
                "postbacks.postback", user_id=session["user_id"], _external=True
            )
        else:
            postback_url = url_for("postbacks.postback", _external=True)

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
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=60,  # 60 seconds timeout
            verify=VERIFY_PATH,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, "Request timed out after 60 seconds"
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
