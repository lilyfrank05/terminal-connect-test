from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..utils.api import ENVIRONMENT_URLS

bp = Blueprint("config", __name__)


@bp.route("/")
def index():
    return redirect(url_for("config.config"))


@bp.route("/config", methods=["GET", "POST"])
def config():
    if request.method == "POST":
        # Validate required fields
        required_fields = ["mid", "tid", "api_key", "postback_url"]
        missing_fields = [
            field for field in required_fields if not request.form.get(field)
        ]

        if missing_fields:
            for field in missing_fields:
                flash(f"{field.upper()} is required", "error")
            return render_template(
                "config.html",
                environment=request.form.get("environment", "sandbox"),
                mid=request.form.get("mid", ""),
                tid=request.form.get("tid", ""),
                api_key=request.form.get("api_key", ""),
                postback_url=request.form.get("postback_url", ""),
            )

        # Update configuration in session
        environment = request.form.get("environment", "sandbox")
        session["ENVIRONMENT"] = environment
        session["BASE_URL"] = ENVIRONMENT_URLS[environment]
        session["MID"] = request.form.get("mid", "")
        session["TID"] = request.form.get("tid", "")
        session["API_KEY"] = request.form.get("api_key", "")
        session["POSTBACK_URL"] = request.form.get(
            "postback_url", url_for("postbacks.postback", _external=True)
        )
        flash("Configuration updated successfully", "success")
        return redirect(url_for("config.config"))

    # Get configuration from session with defaults from environment
    defaults = current_app.config["DEFAULT_CONFIG"]
    postback_url = session.get("POSTBACK_URL") or url_for(
        "postbacks.postback", _external=True
    )
    return render_template(
        "config.html",
        environment=session.get("ENVIRONMENT", defaults["ENVIRONMENT"]),
        mid=session.get("MID", defaults["MID"]),
        tid=session.get("TID", defaults["TID"]),
        api_key=session.get("API_KEY", defaults["API_KEY"]),
        postback_url=postback_url,
    )
