import re
from decimal import Decimal, InvalidOperation
from flask import current_app, flash, session


def is_valid_uuid(uuid_string):
    """Validate that a string is a valid UUID v4"""
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    return bool(uuid_pattern.match(uuid_string))


def validate_amount(amount_str):
    """Validate amount has at most 2 decimal places and is positive"""
    try:
        # Convert to Decimal for precise decimal place checking
        amount = Decimal(amount_str)

        # Check if positive
        if amount <= 0:
            return False, "Amount must be greater than 0"

        # Check decimal places
        decimal_places = abs(amount.as_tuple().exponent)
        if decimal_places > 2:
            return False, "Amount cannot have more than 2 decimal places"

        return True, None
    except InvalidOperation:
        return False, "Invalid amount value"


def validate_config():
    """Validate that all required configuration values are set"""
    required_configs = ["MID", "TID", "API_KEY", "POSTBACK_URL", "BASE_URL"]

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
