import os

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

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


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DEFAULT_CONFIG=DEFAULT_CONFIG,
        POSTBACKS_FILE="/tmp/postbacks.json",
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

    # Register blueprints
    from .routes import init_app as init_routes

    init_routes(app)

    return app
