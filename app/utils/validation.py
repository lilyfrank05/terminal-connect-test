import re
from decimal import Decimal, InvalidOperation
from flask import current_app, flash, session


def is_valid_uuid(uuid_str):
    """Validate that the string is a valid UUID v4"""
    if not uuid_str:
        return False
    pattern = (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    return bool(re.match(pattern, uuid_str))


def validate_amount(amount_str):
    """Validate that the amount is a positive number with max 2 decimal places"""
    try:
        amount = float(amount_str)
        if amount <= 0:
            return False, "Amount must be greater than zero"
        if amount > 999999.99:
            return False, "Amount must be less than 1,000,000"
        # Check if amount has more than 2 decimal places
        if len(amount_str.split(".")[-1]) > 2:
            return False, "Amount must have at most 2 decimal places"
        return True, None
    except ValueError:
        return False, "Invalid amount format"


def validate_config():
    """Validate that all required configuration values are set"""
    required_configs = ["MID", "TID", "API_KEY", "BASE_URL"]

    # Check session first, then fall back to defaults
    defaults = current_app.config["DEFAULT_CONFIG"]
    missing = []

    for config in required_configs:
        value = session.get(config)
        if not value:  # If not in session, try to get from defaults
            value = defaults.get(config, "")
            if value:  # If found in defaults, store in session
                session[config] = value
            else:
                missing.append(config)

    if missing:
        flash(
            f'Missing configuration: {", ".join(missing)}. Please configure these values first.',
            "danger",
        )
        return False
    return True
