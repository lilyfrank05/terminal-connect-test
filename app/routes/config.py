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
from ..utils.validation import validate_url
from .user import login_required, user_only_required
from app import db
from app.models.user import Configuration, User


bp = Blueprint("config", __name__)


@bp.route("/")
@login_required
def index():
    # If a user is logged in but has no config in session, load their first one
    if "user_id" in session and not session.get("MID"):
        config = Configuration.query.filter_by(user_id=session["user_id"]).first()
        if config:
            return redirect(url_for("config.load_config", config_id=config.id))
    return redirect(url_for("config.config"))


@bp.route("/config", methods=["GET", "POST"])
@login_required
def config():
    user_configs = []
    if "user_id" in session:
        user_configs = Configuration.query.filter_by(user_id=session["user_id"]).all()

    if request.method == "POST":
        # Validate required fields
        required_fields = ["mid", "tid", "api_key"]
        missing_fields = [
            field for field in required_fields if not request.form.get(field)
        ]
        if missing_fields:
            for field in missing_fields:
                flash(f"{field.upper()} is required", "error")
            return redirect(url_for("config.config"))

        # Prepare config data from form
        postback_url = request.form.get("postback_url", "").strip()

        # Validate postback URL if provided
        if postback_url:
            is_valid, error = validate_url(postback_url)
            if not is_valid:
                flash(error, "danger")
                return redirect(url_for("config.config"))

        # If postback URL is empty, use the default built-in endpoint
        if not postback_url:
            postback_url = url_for("postbacks.postback", _external=True)

        config_data = {
            "environment": request.form.get("environment", "sandbox"),
            "mid": request.form.get("mid", ""),
            "tid": request.form.get("tid", ""),
            "api_key": request.form.get("api_key", ""),
            "postback_url": postback_url,
        }

        # If user is logged in, save to DB. Otherwise, save to session.
        if "user_id" in session:
            # Enforce a limit of 10 configurations per user
            if Configuration.query.filter_by(user_id=session["user_id"]).count() >= 10:
                flash(
                    "You have reached the maximum of 10 saved configurations.", "danger"
                )
                return redirect(url_for("config.config"))

            config_name = request.form.get("config_name")
            if not config_name:
                flash("Configuration Name is required.", "danger")
                return redirect(url_for("config.config"))

            new_config = Configuration(
                user_id=session["user_id"], name=config_name, data=config_data
            )
            db.session.add(new_config)
            db.session.commit()
            flash(f"Configuration '{config_name}' saved successfully.", "success")
        else:  # Guest user
            session["ENVIRONMENT"] = config_data["environment"]
            session["BASE_URL"] = ENVIRONMENT_URLS[config_data["environment"]]
            session["MID"] = config_data["mid"]
            session["TID"] = config_data["tid"]
            session["API_KEY"] = config_data["api_key"]
            session["POSTBACK_URL"] = config_data["postback_url"]
            flash("Configuration updated successfully for this session.", "success")

        return redirect(url_for("config.config"))

    # GET request logic
    if "user_id" in session:
        # For a logged-in user, the form is for creating a *new* config.
        # The loaded config is in the session.
        pass

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
        user_configs=user_configs,
    )


@bp.route("/config/load/<int:config_id>")
@user_only_required
def load_config(config_id):
    config = db.get_or_404(Configuration, config_id)
    if config.user_id != session["user_id"]:
        return "Unauthorized", 403

    # Load config data into session
    session["active_config_id"] = config.id
    session["ENVIRONMENT"] = config.data.get("environment", "sandbox")
    session["BASE_URL"] = ENVIRONMENT_URLS[session["ENVIRONMENT"]]
    session["MID"] = config.data.get("mid", "")
    session["TID"] = config.data.get("tid", "")
    session["API_KEY"] = config.data.get("api_key", "")
    session["POSTBACK_URL"] = config.data.get(
        "postback_url", url_for("postbacks.postback", _external=True)
    )
    flash(f"Loaded configuration '{config.name}'.", "info")
    return redirect(url_for("config.config"))


@bp.route("/config/delete/<int:config_id>", methods=["POST"])
@user_only_required
def delete_config(config_id):
    config = db.get_or_404(Configuration, config_id)
    if config.user_id != session["user_id"]:
        return "Unauthorized", 403

    # If deleting the active config, clear it from session
    if session.get("active_config_id") == config.id:
        session.pop("active_config_id", None)
        session.pop("MID", None)  # Clear a key field to indicate no active config

    db.session.delete(config)
    db.session.commit()
    flash(f"Configuration '{config.name}' deleted.", "success")
    return redirect(url_for("config.config"))


@bp.route("/config/update/<int:config_id>", methods=["POST"])
@user_only_required
def update_config(config_id):
    config = db.get_or_404(Configuration, config_id)
    if config.user_id != session["user_id"]:
        return "Unauthorized", 403

    config_name = request.form.get(f"config_name_{config_id}")
    if not config_name:
        flash("Configuration name cannot be empty.", "danger")
        return redirect(url_for("config.config"))

    # Handle postback URL - use default if empty
    postback_url = request.form.get(f"postback_url_{config_id}", "").strip()

    # Validate postback URL if provided
    if postback_url:
        is_valid, error = validate_url(postback_url)
        if not is_valid:
            flash(error, "danger")
            return redirect(url_for("config.config"))

    if not postback_url:
        postback_url = url_for("postbacks.postback", _external=True)

    # Make a copy of the config data to ensure SQLAlchemy detects the change
    updated_data = dict(config.data)
    updated_data["environment"] = request.form.get(f"environment_{config_id}")
    updated_data["mid"] = request.form.get(f"mid_{config_id}")
    updated_data["tid"] = request.form.get(f"tid_{config_id}")
    updated_data["api_key"] = request.form.get(f"api_key_{config_id}")
    updated_data["postback_url"] = postback_url

    # Update name and data
    config.name = config_name
    config.data = updated_data

    db.session.commit()

    # Reload the config into the session if it was the active one
    if session.get("active_config_id") == config.id:
        return redirect(url_for("config.load_config", config_id=config.id))

    flash(f"Configuration '{config.name}' updated.", "success")
    return redirect(url_for("config.config"))
