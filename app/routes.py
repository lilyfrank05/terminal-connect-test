import json
import re
from decimal import Decimal, InvalidOperation

import requests
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp = Blueprint("main", __name__)

ENVIRONMENT_URLS = {
    "production": "https://api-terminal-gateway.tillpayments.com/devices",
    "sandbox": "https://api-terminal-gateway.tillvision.show/devices",
}


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


def make_api_request(endpoint, method="POST", payload=None):
    """Helper function to make API requests with proper headers and error handling"""
    if not validate_config():
        return None, "Missing configuration values"

    # Get values from session, with defaults as fallback
    defaults = current_app.config["DEFAULT_CONFIG"]
    api_key = session.get("API_KEY", defaults["API_KEY"])
    base_url = session.get("BASE_URL", defaults["BASE_URL"])

    headers = {"Content-Type": "application/json", "x-api-key": api_key}

    url = f"{base_url}{endpoint}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=60,  # 60 seconds timeout
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

    if error:
        flash(f"Process failed for Intent ID {intent_id}: {error}", "danger")
    else:
        flash(f"Successfully processed Intent ID: {intent_id}", "success")

    return response_data, error


@bp.route("/")
def index():
    return redirect(url_for("main.config"))


@bp.route("/config", methods=["GET", "POST"])
def config():
    if request.method == "POST":
        # Update configuration in session
        environment = request.form.get("environment", "sandbox")
        session["ENVIRONMENT"] = environment
        session["BASE_URL"] = ENVIRONMENT_URLS[environment]
        session["MID"] = request.form.get("mid", "")
        session["TID"] = request.form.get("tid", "")
        session["API_KEY"] = request.form.get("api_key", "")
        session["POSTBACK_URL"] = request.form.get("postback_url", "")
        flash("Configuration updated successfully", "success")
        return redirect(url_for("main.config"))

    # Get configuration from session with defaults from environment
    defaults = current_app.config["DEFAULT_CONFIG"]
    return render_template(
        "config.html",
        environment=session.get("ENVIRONMENT", defaults["ENVIRONMENT"]),
        mid=session.get("MID", defaults["MID"]),
        tid=session.get("TID", defaults["TID"]),
        api_key=session.get("API_KEY", defaults["API_KEY"]),
        postback_url=session.get("POSTBACK_URL", defaults["POSTBACK_URL"]),
    )


@bp.route("/sale", methods=["GET", "POST"])
def sale():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("main.config"))

        # Validate amount
        amount_str = request.form.get("amount", "0")
        is_valid, error_message = validate_amount(amount_str)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("main.sale"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("main.sale"))

        # First API call to create payment intent
        endpoint = f"/merchant/{session['MID']}/intent/payment"
        payload = {
            "subTotal": int(amount * 100),
            "merchantReference": merchant_reference,
            "postbackUrl": session["POSTBACK_URL"],
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating payment intent: {error}", "danger")
            return redirect(url_for("main.sale"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        process_intent(intent_id)

        return redirect(url_for("main.sale"))

    return render_template("sale.html")


@bp.route("/unlinked-refund", methods=["GET", "POST"])
def unlinked_refund():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("main.config"))

        # Validate amount
        amount_str = request.form.get("amount", "0")
        is_valid, error_message = validate_amount(amount_str)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("main.unlinked_refund"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("main.unlinked_refund"))

        # First API call to create refund intent
        endpoint = f"/merchant/{session['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
            "postbackUrl": session["POSTBACK_URL"],
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating refund intent: {error}", "danger")
            return redirect(url_for("main.unlinked_refund"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        process_intent(intent_id)

        return redirect(url_for("main.unlinked_refund"))

    return render_template("unlinked_refund.html")


@bp.route("/linked-refund", methods=["GET", "POST"])
def linked_refund():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("main.config"))

        # Validate amount
        amount_str = request.form.get("amount", "0")
        is_valid, error_message = validate_amount(amount_str)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("main.linked_refund"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("main.linked_refund"))

        parent_intent_id = request.form.get("parent_intent_id")
        if not parent_intent_id:
            flash("Parent Intent ID is required", "danger")
            return redirect(url_for("main.linked_refund"))

        # Validate parent intent ID format
        if not is_valid_uuid(parent_intent_id):
            flash("Parent Intent ID must be a valid UUID v4", "danger")
            return redirect(url_for("main.linked_refund"))

        via_pinpad = request.form.get("via_pinpad", "yes") == "yes"

        if not via_pinpad:
            # First get the parent intent details
            endpoint = f"/merchant/{session['MID']}/intent/{parent_intent_id}"
            response_data, error = make_api_request(endpoint, method="GET")

            if error:
                flash(f"Error fetching parent intent details: {error}", "danger")
                return redirect(url_for("main.linked_refund"))

            # Parse the externalData JSON string
            try:
                external_data = json.loads(
                    response_data["transactionDetails"]["externalData"]
                )
                transaction_details = {
                    "gatewayReferenceNumber": external_data["gatewayReferenceNumber"],
                    "originalAmount": external_data["originalAmount"],
                    "originalApprovalCode": external_data["originalApprovalCode"],
                    "originalTransactionType": external_data["originalTransactionType"],
                    "mid": external_data["hostMerchantId"],
                    "tid": external_data["hostTerminalId"],
                }
            except (KeyError, json.JSONDecodeError) as e:
                flash(f"Error parsing transaction details: {str(e)}", "danger")
                return redirect(url_for("main.linked_refund"))

        # Create refund intent
        endpoint = f"/merchant/{session['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
            "postbackUrl": session["POSTBACK_URL"],
            "parentIntentId": parent_intent_id,
        }

        if not via_pinpad:
            payload["isNonPinpadRefund"] = True
            payload["transactionDetails"] = transaction_details

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating linked refund intent: {error}", "danger")
            return redirect(url_for("main.linked_refund"))

        # Get the intent ID from the response
        intent_id = response_data["intentId"]

        if via_pinpad:
            # Process via pinpad (existing flow)
            process_intent(intent_id)
        else:
            # When not using pinpad, we don't need to make the second API call
            flash(f"Refund intent {intent_id} created successfully!", "success")

        return redirect(url_for("main.linked_refund"))

    return render_template("linked_refund.html")


@bp.route("/reversal", methods=["GET", "POST"])
def reversal():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("main.config"))

        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("main.reversal"))

        parent_intent_id = request.form.get("parent_intent_id")
        if not parent_intent_id:
            flash("Parent Intent ID is required", "danger")
            return redirect(url_for("main.reversal"))

        # Validate parent intent ID format
        if not is_valid_uuid(parent_intent_id):
            flash("Parent Intent ID must be a valid UUID v4", "danger")
            return redirect(url_for("main.reversal"))

        # First API call to create reversal intent
        endpoint = f"/merchant/{session['MID']}/intent/reversal"
        payload = {
            "merchantReference": merchant_reference,
            "postbackUrl": session["POSTBACK_URL"],
            "parentIntentId": parent_intent_id,
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating reversal intent: {error}", "danger")
            return redirect(url_for("main.reversal"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        process_intent(intent_id)

        return redirect(url_for("main.reversal"))

    return render_template("reversal.html")
