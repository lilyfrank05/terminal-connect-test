#!/usr/bin/env python3
"""
Local development runner for Terminal Connect Test.
This script handles database initialization and starts the Flask development server.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_database_init():
    """Run database initialization."""
    print("Running database initialization...")
    try:
        result = subprocess.run([sys.executable, "init_db.py"], check=True)
        print("✓ Database initialization completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Database initialization failed: {e}")
        return False


def start_development_server():
    """Start Flask development server."""
    print("Starting Flask development server...")

    # Set development environment variables
    os.environ.setdefault("FLASK_APP", "app:create_app")
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_DEBUG", "1")

    # Run Flask development server
    try:
        subprocess.run(
            ["flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"], check=True
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"✗ Server failed to start: {e}")
        return False

    return True


def main():
    """Main function."""
    print("=== Terminal Connect Test Development Server ===")

    # Check if we're in the right directory
    if not Path("app").exists():
        print("✗ Error: app directory not found. Please run from project root.")
        sys.exit(1)

    # Initialize database
    if not run_database_init():
        print("✗ Cannot start server without database initialization")
        sys.exit(1)

    # Start development server
    print("\n" + "=" * 50)
    print("Database ready! Starting development server...")
    print("=" * 50 + "\n")

    start_development_server()


if __name__ == "__main__":
    main()
