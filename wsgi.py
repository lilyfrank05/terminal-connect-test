#!/usr/bin/env python3
"""
Flask Application Entry Point

This file serves as the WSGI entry point for Gunicorn.
The main application is defined in the app package.
"""

from app import create_app

# Create the Flask application instance
app = create_app()
