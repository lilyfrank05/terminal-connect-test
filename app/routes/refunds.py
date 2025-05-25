import json
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..utils.api import make_api_request, process_intent
from ..utils.helpers import generate_merchant_reference
from ..utils.validation import validate_amount, validate_config, is_valid_uuid

bp = Blueprint("refunds", __name__)


@bp.route("/unlinked-refund", methods=["GET", "POST"])
def unlinked_refund():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("config.config"))

        # Validate amount
        amount_str = request.form.get("amount", "0")
        is_valid, error_message = validate_amount(amount_str)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("refunds.unlinked_refund"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("refunds.unlinked_refund"))

        # First API call to create refund intent
        endpoint = f"/merchant/{session['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating refund intent: {error}", "danger")
            return redirect(url_for("refunds.unlinked_refund"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        process_intent(intent_id)

        return redirect(url_for("refunds.unlinked_refund"))

    return render_template(
        "unlinked_refund.html", default_merchant_reference=generate_merchant_reference()
    )


@bp.route("/linked-refund", methods=["GET", "POST"])
def linked_refund():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("config.config"))

        # Validate amount
        amount_str = request.form.get("amount", "0")
        is_valid, error_message = validate_amount(amount_str)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("refunds.linked_refund"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("refunds.linked_refund"))

        parent_intent_id = request.form.get("parent_intent_id")
        if not parent_intent_id:
            flash("Parent Intent ID is required", "danger")
            return redirect(url_for("refunds.linked_refund"))

        # Validate parent intent ID format
        if not is_valid_uuid(parent_intent_id):
            flash("Parent Intent ID must be a valid UUID v4", "danger")
            return redirect(url_for("refunds.linked_refund"))

        via_pinpad = request.form.get("via_pinpad", "yes") == "yes"

        if not via_pinpad:
            # First get the parent intent details
            endpoint = f"/merchant/{session['MID']}/intent/{parent_intent_id}"
            response_data, error = make_api_request(endpoint, method="GET")

            if error:
                flash(f"Error fetching parent intent details: {error}", "danger")
                return redirect(url_for("refunds.linked_refund"))

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
                return redirect(url_for("refunds.linked_refund"))

        # Create refund intent
        endpoint = f"/merchant/{session['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
            "parentIntentId": parent_intent_id,
        }

        if not via_pinpad:
            payload["isNonPinpadRefund"] = True
            payload["transactionDetails"] = transaction_details

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating linked refund intent: {error}", "danger")
            return redirect(url_for("refunds.linked_refund"))

        # Get the intent ID from the response
        intent_id = response_data["intentId"]

        if via_pinpad:
            # Process via pinpad (existing flow)
            process_intent(intent_id)
        else:
            # When not using pinpad, we don't need to make the second API call
            flash(f"Refund intent {intent_id} created successfully!", "success")

        return redirect(url_for("refunds.linked_refund"))

    return render_template(
        "linked_refund.html", default_merchant_reference=generate_merchant_reference()
    )
