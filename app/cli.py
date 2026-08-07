"""
CLI commands for Terminal Connect Test application.

Provides a one-shot `flask init-db` command that replaces the old
subprocess-chained init_db.py with direct Alembic/Flask-Migrate API calls.
"""

import os
import sys
from pathlib import Path

import click
from alembic import command as alembic_command
from flask import current_app
from flask.cli import with_appcontext


@click.group()
def cli():
    """Terminal Connect Test management commands."""
    pass


@cli.command("init-db")
@with_appcontext
def init_db():
    """Initialize the database: create/upgrade schema and seed admin user.

    Replaces the old subprocess-chained init_db.py pattern.
    """
    print("=== Starting Database Initialization ===")

    # Step 1: Check database connection
    if not _check_database_connection():
        click.echo("Database connection failed - cannot continue", err=True)
        sys.exit(1)

    # Step 2: Initialize Flask-Migrate if needed
    if not _init_migrations():
        click.echo("Flask-Migrate initialization failed", err=True)
        sys.exit(1)

    # Step 3: Apply pending migrations
    if not _apply_migrations():
        click.echo("Migration application failed", err=True)
        sys.exit(1)

    # Step 4: Create admin user if credentials configured
    _create_admin_user()

    print("=== Database Initialization Completed Successfully ===")


def _check_database_connection() -> bool:
    """Verify the database is reachable."""
    print("=== Checking Database Connection ===")
    try:
        from sqlalchemy import text
        from app import db

        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database connection successful")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def _init_migrations() -> bool:
    """Initialize the migrations directory and create an initial migration if needed."""
    print("=== Initializing Flask-Migrate ===")

    base_dir = Path(current_app.root_path).parent
    versions_dir = base_dir / "migrations" / "versions"

    migrations_exist = versions_dir.parent.exists()
    files_exist = versions_dir.exists() and any(versions_dir.iterdir())

    migrate = current_app.extensions["migrate"]
    cfg = migrate.cfg

    if not migrations_exist:
        print("Creating migrations directory...")
        try:
            alembic_command.init(cfg, str(base_dir / "migrations"))
            print("Migrations directory created")
        except Exception as e:
            print(f"Failed to create migrations directory: {e}")
            return False

    if not files_exist:
        print("Creating initial migration...")
        try:
            alembic_command.revision(cfg, message="Initial migration", autogenerate=True)
            print("Initial migration created")
        except Exception as e:
            print(f"Failed to create initial migration: {e}")
            return False

    return True


def _apply_migrations() -> bool:
    """Apply pending database migrations."""
    print("=== Applying Database Migrations ===")

    migrate = current_app.extensions["migrate"]
    cfg = migrate.cfg

    # Show current migration status
    print("Checking current migration status...")
    try:
        alembic_command.current(cfg)
    except Exception:
        pass  # non-fatal; current may fail on fresh DB

    # Attempt upgrade
    try:
        alembic_command.upgrade(cfg, "head")
        print("Migrations applied successfully")
        return True
    except Exception as e:
        print(f"Migration failed: {e}")
        # Fall back to creating all tables and stamping head
        print("Attempting to create tables directly and stamp as head...")
        try:
            from app import db

            db.create_all()
            alembic_command.stamp(cfg, "head")
            print("Tables created and stamped as head")
            return True
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            return False


def _create_admin_user() -> None:
    """Create the admin user from environment credentials, if configured."""
    print("=== Creating Admin User ===")

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("No admin credentials provided in environment variables")
        return

    try:
        from app import db
        from app.models import User

        existing_admin = User.query.filter_by(email=admin_email).first()
        if existing_admin:
            print(f"Admin user already exists: {admin_email}")
            return

        print(f"Creating admin user: {admin_email}")
        admin = User(email=admin_email, role="admin")
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user created successfully: {admin_email}")
    except Exception as e:
        print(f"Failed to create admin user: {e}")