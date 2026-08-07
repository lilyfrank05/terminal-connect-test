#!/usr/bin/env python3
"""
Database initialization script for Terminal Connect Test application.
Replaced the old subprocess-chained pattern with direct API calls via Flask CLI.

Docker entrypoints SHOULD use `flask init-db` instead of this script.
This file exists as a fallback direct entry point.  No subprocess calls are made.
"""

import sys

from app import create_app


def main():
    """Initialize the database using direct API calls (no subprocess chaining)."""
    app = create_app()

    with app.app_context():
        from app.cli import (
            _check_database_connection,
            _init_migrations,
            _apply_migrations,
            _create_admin_user,
        )

        print("=== Starting Database Initialization ===")

        if not _check_database_connection():
            print("Database connection failed - cannot continue")
            sys.exit(1)

        if not _init_migrations():
            print("Flask-Migrate initialization failed")
            sys.exit(1)

        if not _apply_migrations():
            print("Migration application failed")
            sys.exit(1)

        _create_admin_user()

        print("=== Database Initialization Completed Successfully ===")


if __name__ == "__main__":
    main()