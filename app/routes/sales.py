from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..utils.api import make_api_request, process_intent
from ..utils.helpers import generate_merchant_reference
from ..utils.validation import validate_amount, validate_config

bp = Blueprint("sales", __name__)


@bp.route("/sale", methods=["GET", "POST"])
def sale():
    if request.method == "POST":
        if not validate_config():
            return redirect(url_for("config.config"))

        # Validate amount
        amount_str = request.form.get("amount", "0")
        is_valid, error_message = validate_amount(amount_str)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("sales.sale"))

        amount = float(amount_str)
        merchant_reference = request.form.get("merchant_reference")
        if not merchant_reference:
            flash("Merchant reference is required", "danger")
            return redirect(url_for("sales.sale"))

        # First API call to create payment intent
        endpoint = f"/merchant/{session['MID']}/intent/payment"
        payload = {
            "subTotal": int(amount * 100),
            "merchantReference": merchant_reference,
        }

        response_data, error = make_api_request(endpoint, payload=payload)

        if error:
            flash(f"Error creating payment intent: {error}", "danger")
            return redirect(url_for("sales.sale"))

        # Second API call to process the intent
        intent_id = response_data["intentId"]
        _, process_error = process_intent(intent_id)
        if process_error:
            flash(
                f"Process failed for Intent ID {intent_id}: {process_error}", "danger"
            )
        else:
            flash(f"Successfully processed Intent ID: {intent_id}", "success")
        return redirect(url_for("sales.sale"))

    return render_template(
        "sale.html", default_merchant_reference=generate_merchant_reference()
    )
