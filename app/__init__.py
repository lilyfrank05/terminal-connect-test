import os

from dotenv import load_dotenv
from flask import Flask

# Load environment variables at module level
load_dotenv()

# Default configuration from environment
DEFAULT_CONFIG = {
    "ENVIRONMENT": "sandbox",
    "BASE_URL": "https://api-terminal-gateway.tillvision.show/devices",
    "MID": os.getenv("MID", ""),
    "TID": os.getenv("TID", ""),
    "API_KEY": os.getenv("API_KEY", ""),
    "POSTBACK_URL": os.getenv("POSTBACK_URL", ""),
}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DEFAULT_CONFIG=DEFAULT_CONFIG,
    )

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
