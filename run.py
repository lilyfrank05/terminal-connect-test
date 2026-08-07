#!/usr/bin/env python3
"""
Local development runner for Terminal Connect Test.
Performs database initialization in-process (no subprocess chaining)
and starts the Flask development server.
"""

import sys
import subprocess
from pathlib import Path


def run_database_init():
    """Run database initialization in-process — no subprocess chaining."""
    print("Running database initialization...")
    from app import create_app

    app = create_app()
    with app.app_context():
        from app.cli import (
            _check_database_connection,
            _init_migrations,
            _apply_migrations,
            _create_admin_user,
        )

        if not _check_database_connection():
            print("Database initialization failed")
            return False

        if not _init_migrations():
            print("Migrations initialization failed")
            return False

        if not _apply_migrations():
            print("Migration application failed")
            return False

        _create_admin_user()

    print("Database initialization completed")
    return True


def start_development_server():
    """Start Flask development server."""
    print("Starting Flask development server...")

    try:
        subprocess.run(
            [
                "flask",
                "run",
                "--host=0.0.0.0",
                "--port=5000",
                "--debug",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"Server failed to start: {e}")
        return False

    return True


def main():
    """Main function."""
    print("=== Terminal Connect Test Development Server ===")

    # Check if we're in the right directory
    if not Path("app").exists():
        print("Error: app directory not found. Please run from project root.")
        sys.exit(1)

    # Initialize database
    if not run_database_init():
        print("Cannot start server without database initialization")
        sys.exit(1)

    # Start development server
    print("\n" + "=" * 50)
    print("Database ready! Starting development server...")
    print("=" * 50 + "\n")

    start_development_server()


if __name__ == "__main__":
    main()