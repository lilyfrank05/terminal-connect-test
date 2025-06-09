import json
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..utils.api import make_api_request, process_intent
from ..utils.helpers import generate_merchant_reference
from ..utils.validation import validate_amount, validate_config, is_valid_uuid
from .user import login_required

bp = Blueprint("refunds", __name__)


def get_postback_url():
    """Get postback URL from session or generate appropriate one"""
    postback_url = session.get("POSTBACK_URL")
    if not postback_url:
        # Check if user is authenticated for user-specific postback
        if session.get("user_id"):
            postback_url = url_for(
                "postbacks.user_postback", user_id=session["user_id"], _external=True
            )
        else:
            postback_url = url_for("postbacks.postback", _external=True)
    return postback_url


@bp.route("/unlinked-refund", methods=["GET", "POST"])
@login_required
def unlinked_refund():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("config.config"))

        amount_str = request.form.get("amount", "0")
        if not amount_str:
            flash("Amount is required", "danger")
            return redirect(url_for("refunds.unlinked_refund"))

        is_valid, error = validate_amount(amount_str)
        if not is_valid:
            flash(error or "Invalid amount format", "danger")
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
            "postbackUrl": get_postback_url(),
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating refund intent: {error}", "danger")
            return redirect(url_for("refunds.unlinked_refund"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        _, process_error = process_intent(intent_id)
        if process_error:
            flash(
                f"Process failed for Intent ID {intent_id}: {process_error}", "danger"
            )
        else:
            flash(f"Successfully processed Intent ID: {intent_id}", "success")
        return redirect(url_for("refunds.unlinked_refund"))

    return render_template(
        "unlinked-refund.html", default_merchant_reference=generate_merchant_reference()
    )


@bp.route("/linked-refund", methods=["GET", "POST"])
@login_required
def linked_refund():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("config.config"))

        amount_str = request.form.get("amount", "0")
        if not amount_str:
            flash("Amount is required", "danger")
            return redirect(url_for("refunds.linked_refund"))

        is_valid, error = validate_amount(amount_str)
        if not is_valid:
            flash(error or "Invalid amount format", "danger")
            return redirect(url_for("refunds.linked_refund"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("refunds.linked_refund"))

        parent_intent_id = request.form.get("parent_intent_id")
        if not parent_intent_id:
            flash("Original Sale Reference is required", "danger")
            return redirect(url_for("refunds.linked_refund"))

        # Validate parent intent ID format
        if not is_valid_uuid(parent_intent_id):
            flash("Original Sale Reference must be a valid UUID v4", "danger")
            return redirect(url_for("refunds.linked_refund"))

        # Check if via_pinpad checkbox is checked
        via_pinpad = "via_pinpad" in request.form

        # First API call to create refund intent
        endpoint = f"/merchant/{session['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
            "parentIntentId": parent_intent_id,
            "postbackUrl": get_postback_url(),
        }

        # If viaPinpad is not true, get transaction details first
        if not via_pinpad:
            # Get transaction details for the parent intent
            details_endpoint = f"/merchant/{session['MID']}/intent/{parent_intent_id}"
            details_data, details_error = make_api_request(
                details_endpoint, method="GET"
            )

            if details_error:
                flash(f"Error getting transaction details: {details_error}", "danger")
                return redirect(url_for("refunds.linked_refund"))

            # Parse externalData string into dictionary
            external_data_str = details_data.get("transactionDetails", {}).get(
                "externalData"
            )
            if not external_data_str:
                flash("Could not find externalData in transaction details", "danger")
                return redirect(url_for("refunds.linked_refund"))
            try:
                external_data = json.loads(external_data_str)
            except json.JSONDecodeError:
                flash("Error parsing transaction details", "danger")
                return redirect(url_for("refunds.linked_refund"))

            # Add transaction details and isNonPinpadRefund to the payload
            payload["transactionDetails"] = {
                "gatewayReferenceNumber": external_data["gatewayReferenceNumber"],
                "originalAmount": external_data["originalAmount"],
                "originalApprovalCode": external_data["originalApprovalCode"],
                "originalTransactionType": external_data["originalTransactionType"],
                "mid": external_data["hostMerchantId"],
                "tid": external_data["hostTerminalId"],
            }
            payload["isNonPinpadRefund"] = True

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating refund intent: {error}", "danger")
            return redirect(url_for("refunds.linked_refund"))

        # Get the intent ID
        intent_id = response_data["intentId"]

        # Only process the intent if via_pinpad is true
        if via_pinpad:
            _, process_error = process_intent(intent_id)
            if process_error:
                flash(
                    f"Process failed for Intent ID {intent_id}: {process_error}",
                    "danger",
                )
                return redirect(url_for("refunds.linked_refund"))
            else:
                flash(f"Successfully processed Intent ID: {intent_id}", "success")
        else:
            flash(f"Successfully created refund Intent ID: {intent_id}", "success")
        return redirect(url_for("refunds.linked_refund"))

    return render_template(
        "linked-refund.html", default_merchant_reference=generate_merchant_reference()
    )
