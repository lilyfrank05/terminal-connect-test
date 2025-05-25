from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..utils.api import make_api_request, process_intent
from ..utils.helpers import generate_merchant_reference
from ..utils.validation import is_valid_uuid, validate_config

bp = Blueprint("reversals", __name__)


@bp.route("/reversal", methods=["GET", "POST"])
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
            flash("Parent Intent ID is required", "danger")
            return redirect(url_for("reversals.reversal"))

        # Validate parent intent ID format
        if not is_valid_uuid(parent_intent_id):
            flash("Parent Intent ID must be a valid UUID v4", "danger")
            return redirect(url_for("reversals.reversal"))

        # First API call to create reversal intent
        endpoint = f"/merchant/{session['MID']}/intent/reversal"
        payload = {
            "merchantReference": merchant_reference,
            "parentIntentId": parent_intent_id,
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating reversal intent: {error}", "danger")
            return redirect(url_for("reversals.reversal"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        process_intent(intent_id)

        return redirect(url_for("reversals.reversal"))

    return render_template(
        "reversal.html", default_merchant_reference=generate_merchant_reference()
    )
