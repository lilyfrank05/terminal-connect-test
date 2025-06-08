#!/usr/bin/env python3
"""
Flask Application Entry Point

This file serves as a compatibility layer and entry point for the Flask application.
The main application is defined in the app package.
"""

from app import create_app

# Create the Flask application instance
app = create_app()

if __name__ == "__main__":
    # This allows the app to be run directly with `python app.py`
    # though in production it should be run with Gunicorn
    app.run(host="0.0.0.0", port=5000, debug=False)
