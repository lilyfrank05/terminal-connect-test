import re
from flask import current_app, flash, session
import uuid


def is_valid_uuid(uuid_str):
    """Validate that the string is a valid UUID v4"""
    if not uuid_str:
        return False
    try:
        val = uuid.UUID(uuid_str, version=4)
    except (ValueError, AttributeError, TypeError):
        return False
    # Ensure the version is exactly 4
    return val.version == 4 and str(val) == uuid_str.lower()


def validate_amount(amount_str):
    """Validate that the amount is a positive number with max 2 decimal places"""
    try:
        amount = float(amount_str)
        if amount <= 0:
            return False, "Amount must be greater than zero"
        if amount > 999999.99:
            return False, "Amount must be less than 1,000,000"
        # Check if amount has more than 2 decimal places
        decimal_parts = amount_str.split(".")
        if len(decimal_parts) == 2 and len(decimal_parts[1]) > 2:
            return False, "Amount must have at most 2 decimal places"
        return True, None
    except ValueError:
        return False, "Invalid amount format"


def ensure_config_session():
    """Load configuration defaults into session if not already set.

    Call this before validate_config() in route handlers that access
    session['MID'] directly (instead of session.get('MID', defaults)).
    """
    required_configs = ["MID", "TID", "API_KEY", "BASE_URL"]
    defaults = current_app.config["DEFAULT_CONFIG"]
    for config in required_configs:
        if not session.get(config):
            value = defaults.get(config, "")
            if value:
                session[config] = value


def validate_config():
    """Validate that all required configuration values are set.

    Does not modify session. Use ensure_config_session() first if you need
    defaults loaded into session.
    """
    required_configs = ["MID", "TID", "API_KEY", "BASE_URL"]

    defaults = current_app.config["DEFAULT_CONFIG"]
    missing = []

    for config in required_configs:
        value = session.get(config)
        if not value:
            value = defaults.get(config, "")
            if not value:
                missing.append(config)

    if missing:
        flash(
            f'Missing configuration: {", ".join(missing)}. Please configure these values first.',
            "danger",
        )
        return False
    return True


def validate_url(url_str):
    """Validate that the string is a valid HTTP/HTTPS URL"""
    if not url_str:
        return True, None  # Empty URL is allowed (will use default)

    # Basic URL pattern validation
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    if not url_pattern.match(url_str):
        return False, "Invalid URL format. Please use http:// or https://"

    return True, None
