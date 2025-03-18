from flask import Flask
from dotenv import load_dotenv
import os

# Load environment variables at module level
load_dotenv()

# Default configuration from environment
DEFAULT_CONFIG = {
    'ENVIRONMENT': 'sandbox',
    'BASE_URL': 'https://api-terminal-gateway.tillvision.show/devices',
    'MID': os.getenv('MID', ''),
    'TID': os.getenv('TID', ''),
    'API_KEY': os.getenv('API_KEY', ''),
    'POSTBACK_URL': os.getenv('POSTBACK_URL', '')
}

def create_app():
    app = Flask(__name__)
    
    # Set secret key for session management
    app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-this-in-production')
    
    # Store default config in app for access in routes
    app.config['DEFAULT_CONFIG'] = DEFAULT_CONFIG
    
    # Import routes
    from app import routes
    app.register_blueprint(routes.bp)
    
    return app
