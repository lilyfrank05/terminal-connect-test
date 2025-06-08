import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Load environment variables at module level
load_dotenv()

# Default configuration from environment
DEFAULT_CONFIG = {
    "ENVIRONMENT": "sandbox",
    "BASE_URL": "https://api-terminal-gateway.tillvision.show/devices",
    "MID": os.getenv("MID", ""),
    "TID": os.getenv("TID", ""),
    "API_KEY": os.getenv("API_KEY", ""),
}

db = SQLAlchemy()
migrate = Migrate()


def create_app(test_config=None, *args, **kwargs):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev"),
        DEFAULT_CONFIG=DEFAULT_CONFIG,
        POSTBACKS_FILE="/tmp/postbacks.json",
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///:memory:"),
        ADMIN_EMAIL=os.getenv("ADMIN_EMAIL"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD"),
        BREVO_API_KEY=os.getenv("BREVO_API_KEY"),
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

    db.init_app(app)
    migrate.init_app(app, db)

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
