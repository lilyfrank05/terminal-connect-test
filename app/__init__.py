import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables at module level
load_dotenv()

# Import models
from .models import db

# Default configuration from environment
DEFAULT_CONFIG = {
    "ENVIRONMENT": "sandbox",
    "BASE_URL": "https://api-terminal-gateway.tillvision.show/devices",
    "MID": os.getenv("MID", ""),
    "TID": os.getenv("TID", ""),
    "API_KEY": os.getenv("API_KEY", ""),
}

# Global scheduler instance
scheduler = None


def cleanup_guest_postbacks():
    """Clean up guest postbacks older than 24 hours."""
    try:
        postbacks_file = "/tmp/postbacks.json"
        if os.path.exists(postbacks_file):
            with open(postbacks_file, "r") as f:
                postbacks = json.load(f)

            # Filter out postbacks older than 24 hours
            cutoff_time = datetime.now() - timedelta(days=1)
            filtered_postbacks = []

            for postback in postbacks:
                try:
                    # Parse the timestamp from the postback
                    timestamp_str = postback.get("timestamp", "")
                    if timestamp_str:
                        postback_time = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        if postback_time.replace(tzinfo=None) >= cutoff_time:
                            filtered_postbacks.append(postback)
                    else:
                        # If no timestamp, keep it (shouldn't happen but safe fallback)
                        filtered_postbacks.append(postback)
                except (ValueError, TypeError):
                    # If timestamp parsing fails, keep the postback
                    filtered_postbacks.append(postback)

            # Write back the filtered postbacks
            with open(postbacks_file, "w") as f:
                json.dump(filtered_postbacks, f, indent=2)

            print(
                f"Guest postbacks cleanup completed. Removed {len(postbacks) - len(filtered_postbacks)} old postbacks."
            )
    except Exception as e:
        print(f"Error during guest postbacks cleanup: {e}")


def create_app(test_config=None, *args, **kwargs):
    global scheduler

    app = Flask(__name__, instance_relative_config=True)
    
    # Configure logging to show INFO level messages in console
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),  # Console output
            ]
        )
        # Set app logger level
        app.logger.setLevel(logging.INFO)

    # JWT Configuration
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "jwt-secret-change-in-production"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=24),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
        JWT_ALGORITHM="HS256",
        # Database Configuration
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///app.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # App Configuration
        DEFAULT_CONFIG=DEFAULT_CONFIG,
        POSTBACKS_FILE="/tmp/postbacks.json",
        # Email Configuration (if using email for invites)
        MAIL_SERVER=os.getenv("MAIL_SERVER"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() in ["true", "1", "yes"],
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER"),
    )

    app.config["PREFERRED_URL_SCHEME"] = "https"

    # Use ProxyFix to respect X-Forwarded-Proto and X-Forwarded-Host
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    jwt = JWTManager(app)

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {"message": "Token has expired", "error": "token_expired"}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {"message": "Invalid token", "error": "invalid_token"}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {
            "message": "Authorization token is required",
            "error": "authorization_required",
        }, 401

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return {"message": "Fresh token required", "error": "fresh_token_required"}, 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return {"message": "Token has been revoked", "error": "token_revoked"}, 401

    # Note: Database initialization and admin user creation moved to init_db.py
    # to avoid circular dependency issues with Flask-Migrate

    # Initialize scheduler for guest postbacks cleanup (only in production/non-testing)
    if not app.config.get("TESTING", False) and scheduler is None:
        scheduler = BackgroundScheduler()
        # Run cleanup daily at 2 AM
        scheduler.add_job(
            func=cleanup_guest_postbacks,
            trigger=CronTrigger(hour=2, minute=0),
            id="cleanup_guest_postbacks",
            name="Daily cleanup of guest postbacks",
            replace_existing=True,
        )
        scheduler.start()
        print("Scheduler started for daily guest postbacks cleanup")

    # Register blueprints
    from .routes import init_app as init_routes
    from app.routes.user import create_user_blueprint

    user_browser_bp = create_user_blueprint(name="user")
    app.register_blueprint(
        user_browser_bp, url_prefix="/user"
    )  # Only browser-facing pages

    init_routes(app)

    @app.route("/")
    def root():
        return "It works!"

    @app.route("/health")
    def health_check():
        """Health check endpoint for Docker and monitoring."""
        try:
            # Test database connection using modern SQLAlchemy syntax
            from sqlalchemy import text

            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return (
                jsonify(
                    {
                        "status": "healthy",
                        "database": "connected",
                        "application": "running",
                    }
                ),
                200,
            )
        except Exception as e:
            return (
                jsonify({"status": "unhealthy", "database": "error", "error": str(e)}),
                503,
            )

    return app
