import logging
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
from ..utils.auth import optional_jwt_user
from ..models import db, UserConfig, User


bp = Blueprint("config", __name__)


@bp.route("/")
@optional_jwt_user
def index(user):
    # If a user is logged in but has no config in session, load their first one
    if "user_id" in session and not session.get("MID"):
        config = db.session.execute(
            db.select(UserConfig).filter_by(user_id=session["user_id"])
        ).scalar_one_or_none()
        if config:
            return redirect(url_for("config.load_config", config_id=config.id))
    return redirect(url_for("config.config"))


@bp.route("/config", methods=["GET", "POST"])
@optional_jwt_user
def config(user):
    user_configs = []
    if "user_id" in session:
        user_configs = db.session.execute(
            db.select(UserConfig)
            .filter_by(user_id=session["user_id"])
            .order_by(UserConfig.display_order, UserConfig.created_at)
        ).scalars().all()

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

        # Validate postback delay
        postback_delay_raw = request.form.get("postback_delay", "0").strip()
        logger = logging.getLogger(__name__)
        logger.info(f"Processing postback_delay from form: '{postback_delay_raw}'")
        
        try:
            postback_delay = int(postback_delay_raw) if postback_delay_raw else 0
            logger.info(f"Parsed postback_delay: {postback_delay}")
            if postback_delay < 0 or postback_delay > 600:
                logger.warning(f"Invalid postback_delay value: {postback_delay} (must be 0-600)")
                flash("Postback delay must be between 0 and 600 seconds (10 minutes).", "danger")
                return redirect(url_for("config.config"))
        except ValueError:
            logger.error(f"Invalid postback_delay format: '{postback_delay_raw}'")
            flash("Postback delay must be a valid number.", "danger")
            return redirect(url_for("config.config"))

        # If postback URL is empty, use the default built-in endpoint
        if not postback_url:
            if "user_id" in session:
                # User-specific postback URL for authenticated users
                postback_url = url_for(
                    "postbacks.postback", user_id=session["user_id"], _external=True
                )
            else:
                # Generic postback URL for guests
                postback_url = url_for("postbacks.postback", _external=True)
        
        # Append delay query parameter if delay is configured
        if postback_delay > 0:
            # Add delay parameter to the postback URL
            separator = "&" if "?" in postback_url else "?"
            postback_url = f"{postback_url}{separator}delay={postback_delay}"
            logger.info(f"Added delay parameter to postback URL: {postback_url}")

        config_data = {
            "environment": request.form.get("environment", "sandbox"),
            "mid": request.form.get("mid", ""),
            "tid": request.form.get("tid", ""),
            "api_key": request.form.get("api_key", ""),
            "postback_url": postback_url,
            "postback_delay": postback_delay,
        }

        # If user is logged in, save to DB. Otherwise, save to session.
        if "user_id" in session:
            # Check if user can add more configs based on their role
            current_user = db.session.get(User, session["user_id"])
            if not current_user.can_add_config():
                max_configs = 50 if current_user.role == "admin" else 10
                flash(
                    f"You have reached the maximum of {max_configs} saved configurations.", "danger"
                )
                return redirect(url_for("config.config"))

            config_name = request.form.get("config_name")
            if not config_name:
                flash("Configuration Name is required.", "danger")
                return redirect(url_for("config.config"))

            # Get the next display order
            max_order = db.session.execute(
                db.select(db.func.max(UserConfig.display_order)).filter_by(user_id=session["user_id"])
            ).scalar() or 0
            
            new_config = UserConfig(
                user_id=session["user_id"],
                name=config_name,
                environment=config_data["environment"],
                base_url=ENVIRONMENT_URLS[config_data["environment"]],
                mid=config_data["mid"],
                tid=config_data["tid"],
                api_key=config_data["api_key"],
                postback_url=config_data["postback_url"],
                postback_delay=config_data["postback_delay"],
                display_order=max_order + 1,
            )
            db.session.add(new_config)
            db.session.commit()
            logger.info(f"Authenticated user config saved: id={new_config.id}, postback_delay={new_config.postback_delay}")
            flash(f"Configuration '{config_name}' saved successfully.", "success")
        else:  # Guest user
            session["ENVIRONMENT"] = config_data["environment"]
            session["BASE_URL"] = ENVIRONMENT_URLS[config_data["environment"]]
            session["MID"] = config_data["mid"]
            session["TID"] = config_data["tid"]
            session["API_KEY"] = config_data["api_key"]
            session["POSTBACK_URL"] = config_data["postback_url"]
            session["POSTBACK_DELAY"] = config_data["postback_delay"]
            logger.info(f"Guest user config saved with POSTBACK_DELAY={config_data['postback_delay']} in session")
            flash("Configuration updated successfully for this session.", "success")

        return redirect(url_for("config.config"))

    # GET request logic
    if "user_id" in session:
        # For a logged-in user, the form is for creating a *new* config.
        # The loaded config is in the session.
        pass

    # Get configuration from session with defaults from environment
    defaults = current_app.config["DEFAULT_CONFIG"]
    postback_url = session.get("POSTBACK_URL")
    if not postback_url:
        # Generate appropriate default postback URL based on authentication
        if "user_id" in session:
            # User-specific postback URL for authenticated users
            postback_url = url_for(
                "postbacks.postback", user_id=session["user_id"], _external=True
            )
        else:
            # Generic postback URL for guests
            postback_url = url_for("postbacks.postback", _external=True)
    return render_template(
        "config.html",
        environment=session.get("ENVIRONMENT", defaults["ENVIRONMENT"]),
        mid=session.get("MID", defaults["MID"]),
        tid=session.get("TID", defaults["TID"]),
        api_key=session.get("API_KEY", defaults["API_KEY"]),
        postback_url=postback_url,
        postback_delay=session.get("POSTBACK_DELAY", 0),
        user_configs=user_configs,
    )


@bp.route("/config/load/<int:config_id>")
@optional_jwt_user
def load_config(user, config_id):
    config = db.get_or_404(UserConfig, config_id)
    if config.user_id != session["user_id"]:
        return "Unauthorized", 403

    # Load config data into session
    logger = logging.getLogger(__name__)
    session["active_config_id"] = config.id
    session["ENVIRONMENT"] = config.environment
    session["BASE_URL"] = config.base_url
    session["MID"] = config.mid
    session["TID"] = config.tid
    session["API_KEY"] = config.api_key
    session["POSTBACK_DELAY"] = config.postback_delay
    logger.info(f"Loaded config {config.id} into session with POSTBACK_DELAY={config.postback_delay}")
    
    # Handle postback URL with delay parameter
    if config.postback_url:
        postback_url = config.postback_url
    else:
        # Generate user-specific postback URL for authenticated users
        if "user_id" in session:
            postback_url = url_for(
                "postbacks.postback", user_id=session["user_id"], _external=True
            )
        else:
            postback_url = url_for("postbacks.postback", _external=True)
    
    # Append delay query parameter if delay is configured
    if config.postback_delay > 0:
        # Remove existing delay parameter if present
        if "delay=" in postback_url:
            import re
            postback_url = re.sub(r'[?&]delay=\d+', '', postback_url)
        
        # Add delay parameter to the postback URL
        separator = "&" if "?" in postback_url else "?"
        postback_url = f"{postback_url}{separator}delay={config.postback_delay}"
        logger.info(f"Added delay parameter to loaded postback URL: {postback_url}")
    
    session["POSTBACK_URL"] = postback_url
    flash(f"Loaded configuration '{config.name}'.", "info")
    return redirect(url_for("config.config"))


@bp.route("/config/delete/<int:config_id>", methods=["POST"])
@optional_jwt_user
def delete_config(user, config_id):
    config = db.get_or_404(UserConfig, config_id)
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
@optional_jwt_user
def update_config(user, config_id):
    config = db.get_or_404(UserConfig, config_id)
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

    # Handle postback delay validation
    postback_delay = request.form.get(f"postback_delay_{config_id}", "0").strip()
    try:
        postback_delay = int(postback_delay) if postback_delay else 0
        if postback_delay < 0 or postback_delay > 600:
            flash("Postback delay must be between 0 and 600 seconds (10 minutes).", "danger")
            return redirect(url_for("config.config"))
    except ValueError:
        flash("Postback delay must be a valid number.", "danger")
        return redirect(url_for("config.config"))

    if not postback_url:
        if "user_id" in session:
            # User-specific postback URL for authenticated users
            postback_url = url_for(
                "postbacks.postback", user_id=session["user_id"], _external=True
            )
        else:
            # Generic postback URL for guests
            postback_url = url_for("postbacks.postback", _external=True)
    
    # Append delay query parameter if delay is configured
    if postback_delay > 0:
        # Remove existing delay parameter if present
        if "delay=" in postback_url:
            import re
            postback_url = re.sub(r'[?&]delay=\d+', '', postback_url)
        
        # Add delay parameter to the postback URL
        separator = "&" if "?" in postback_url else "?"
        postback_url = f"{postback_url}{separator}delay={postback_delay}"
        logger = logging.getLogger(__name__)
        logger.info(f"Added delay parameter to updated postback URL: {postback_url}")

    # Update config fields
    config.name = config_name
    config.environment = request.form.get(f"environment_{config_id}")
    config.base_url = ENVIRONMENT_URLS.get(config.environment, "")
    config.mid = request.form.get(f"mid_{config_id}")
    config.tid = request.form.get(f"tid_{config_id}")
    config.api_key = request.form.get(f"api_key_{config_id}")
    config.postback_url = postback_url
    config.postback_delay = postback_delay

    db.session.commit()

    # Reload the config into the session if it was the active one
    if session.get("active_config_id") == config.id:
        return redirect(url_for("config.load_config", config_id=config.id))

    flash(f"Configuration '{config.name}' updated.", "success")
    return redirect(url_for("config.config"))


@bp.route("/config/reorder", methods=["POST"])
@optional_jwt_user
def reorder_configs(user):
    """Reorder saved configurations."""
    if "user_id" not in session:
        return "Unauthorized", 403
    
    try:
        # Get the new order from the request
        config_ids = request.json.get("config_ids", [])
        
        if not config_ids:
            return {"success": False, "error": "No configuration IDs provided"}, 400
        
        # Verify all configs belong to the user
        user_configs = db.session.execute(
            db.select(UserConfig).filter(
                UserConfig.id.in_(config_ids),
                UserConfig.user_id == session["user_id"]
            )
        ).scalars().all()
        
        if len(user_configs) != len(config_ids):
            return {"success": False, "error": "Invalid configuration IDs"}, 400
        
        # Update display order for each config
        for index, config_id in enumerate(config_ids):
            config = next(c for c in user_configs if c.id == config_id)
            config.display_order = index
        
        db.session.commit()
        return {"success": True}
        
    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}, 500
