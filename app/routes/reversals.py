from flask import Blueprint, flash, redirect, render_template, request, session, url_for
import json

from ..utils.api import make_api_request, process_intent
from ..utils.helpers import generate_merchant_reference
from ..utils.validation import is_valid_uuid, validate_config
from .user import login_required

bp = Blueprint("reversals", __name__)


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


@bp.route("/reversal", methods=["GET", "POST"])
@login_required
def reversal():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("config.config"))

        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("reversals.reversal"))

        parent_intent_id = request.form.get("parent_intent_id")
        if not parent_intent_id:
            flash("Original Sale Reference is required", "danger")
            return redirect(url_for("reversals.reversal"))

        # Validate parent intent ID format
        if not is_valid_uuid(parent_intent_id):
            flash("Original Sale Reference must be a valid UUID v4", "danger")
            return redirect(url_for("reversals.reversal"))

        # Check if via_pinpad checkbox is checked
        via_pinpad = "via_pinpad" in request.form

        # First API call to create reversal intent
        endpoint = f"/merchant/{session['MID']}/intent/reversal"
        payload = {
            "merchantReference": merchant_reference,
            "parentIntentId": parent_intent_id,
            "postbackUrl": get_postback_url(),
        }

        # If via_pinpad is not checked, get transaction details first
        if not via_pinpad:
            details_endpoint = f"/merchant/{session['MID']}/intent/{parent_intent_id}"
            details_data, details_error = make_api_request(
                details_endpoint, method="GET"
            )
            if details_error:
                flash(f"Error getting transaction details: {details_error}", "danger")
                return redirect(url_for("reversals.reversal"))
            external_data_str = details_data.get("transactionDetails", {}).get(
                "externalData"
            )
            if not external_data_str:
                flash("Could not find externalData in transaction details", "danger")
                return redirect(url_for("reversals.reversal"))
            try:
                external_data = json.loads(external_data_str)
            except Exception:
                flash("Error parsing transaction details", "danger")
                return redirect(url_for("reversals.reversal"))
            payload["transactionDetails"] = {
                "gatewayReferenceNumber": external_data["gatewayReferenceNumber"],
                "originalAmount": external_data["originalAmount"],
                "originalApprovalCode": external_data["originalApprovalCode"],
                "originalTransactionType": external_data["originalTransactionType"],
                "mid": external_data["hostMerchantId"],
                "tid": external_data["hostTerminalId"],
            }
            payload["isNonPinpad"] = True

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating reversal intent: {error}", "danger")
            return redirect(url_for("reversals.reversal"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]

        # In a reversal, the intent is always processed immediately.
        _, process_error = process_intent(intent_id)
        if process_error:
            flash(
                f"Process failed for Intent ID {intent_id}: {process_error}", "danger"
            )
        else:
            flash(f"Successfully processed Intent ID: {intent_id}", "success")
        return redirect(url_for("reversals.reversal"))

    return render_template(
        "reversal.html", default_merchant_reference=generate_merchant_reference()
    )
