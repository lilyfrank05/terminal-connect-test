#!/usr/bin/env python3
"""
Database initialization script for Terminal Connect Test application.
This script handles database setup, migrations, and admin user creation.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description="", ignore_errors=False):
    """Run a shell command and handle errors."""
    print(f"Running: {description or command}")
    try:
        # Use current directory instead of hardcoded /app for local development
        cwd = "/app" if os.path.exists("/app") else os.getcwd()
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, cwd=cwd
        )

        if result.stdout:
            print(f"Output: {result.stdout.strip()}")

        if result.stderr and not ignore_errors:
            print(f"Error: {result.stderr.strip()}")

        if result.returncode != 0 and not ignore_errors:
            print(f"Command failed with return code {result.returncode}")
            return False

        return True
    except Exception as e:
        print(f"Exception running command: {e}")
        return False


def check_database_connection():
    """Check if database is accessible."""
    print("=== Checking Database Connection ===")

    try:
        from app import create_app, db
        from sqlalchemy import text

        app = create_app()
        with app.app_context():
            # Test database connection using modern SQLAlchemy syntax
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("✓ Database connection successful")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def check_migrations_dir():
    """Check if migrations directory exists."""
    # Use current directory instead of hardcoded /app for local development
    base_dir = Path("/app") if Path("/app").exists() else Path.cwd()
    migrations_dir = base_dir / "migrations"
    versions_dir = migrations_dir / "versions"

    if not migrations_dir.exists():
        print("Migrations directory does not exist")
        return False, False

    if not versions_dir.exists() or not any(versions_dir.iterdir()):
        print("No migration files found")
        return True, False

    print("Migration files exist")
    return True, True


def initialize_flask_migrate():
    """Initialize Flask-Migrate if needed."""
    print("=== Initializing Flask-Migrate ===")

    migrations_exist, files_exist = check_migrations_dir()

    if not migrations_exist:
        print("Creating migrations directory...")
        if run_command("flask db init", "Initialize Flask-Migrate"):
            print("✓ Migrations directory created")
        else:
            print("✗ Failed to create migrations directory")
            return False

    if not files_exist:
        print("Creating initial migration...")
        if run_command(
            "flask db migrate -m 'Initial migration'", "Create initial migration"
        ):
            print("✓ Initial migration created")
        else:
            print("✗ Failed to create initial migration")
            return False

    return True


def apply_migrations():
    """Apply database migrations."""
    print("=== Applying Database Migrations ===")

    # Check current migration status
    print("Checking current migration status...")
    run_command("flask db current", "Check current migration", ignore_errors=True)

    # Try to apply migrations
    print("Applying migrations...")
    if run_command("flask db upgrade", "Apply migrations"):
        print("✓ Migrations applied successfully")
        return True
    else:
        print("Migration failed, attempting fallback...")

        # Fallback: Create tables directly
        try:
            from app import create_app, db

            app = create_app()
            with app.app_context():
                print("Creating database tables directly...")
                db.create_all()
                print("✓ Database tables created")

                # Mark current state as migrated
                print("Marking current state as up to date...")
                if run_command("flask db stamp head", "Mark as up to date"):
                    print("✓ Database marked as up to date")
                    return True
                else:
                    print("✗ Failed to mark database as up to date")
                    return False
        except Exception as e:
            print(f"✗ Fallback table creation failed: {e}")
            return False


def create_admin_user():
    """Create admin user if credentials are provided."""
    print("=== Creating Admin User ===")

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("No admin credentials provided in environment variables")
        return True

    try:
        from app import create_app, db
        from app.models import User

        app = create_app()
        with app.app_context():
            # Check if admin user already exists
            existing_admin = User.query.filter_by(email=admin_email).first()
            if existing_admin:
                print(f"✓ Admin user already exists: {admin_email}")
                return True

            # Create new admin user
            print(f"Creating admin user: {admin_email}")
            admin = User(email=admin_email, role="admin")
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()

            print(f"✓ Admin user created successfully: {admin_email}")
            return True

    except Exception as e:
        print(f"✗ Failed to create admin user: {e}")
        return False


def main():
    """Main initialization function."""
    print("=== Starting Database Initialization ===")

    # Step 1: Check database connection
    if not check_database_connection():
        print("✗ Database connection failed - cannot continue")
        sys.exit(1)

    # Step 2: Initialize Flask-Migrate
    if not initialize_flask_migrate():
        print("✗ Flask-Migrate initialization failed")
        sys.exit(1)

    # Step 3: Apply migrations
    if not apply_migrations():
        print("✗ Migration application failed")
        sys.exit(1)

    # Step 4: Create admin user
    if not create_admin_user():
        print("✗ Admin user creation failed")
        sys.exit(1)

    print("=== Database Initialization Completed Successfully ===")


if __name__ == "__main__":
    main()
