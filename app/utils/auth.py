from functools import wraps
from flask import jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from ..models import User, db


def jwt_required_with_user(f):
    """Decorator that requires a valid JWT token and loads the user."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()

            if not user_id:
                return (
                    jsonify({"message": "Invalid token", "error": "invalid_token"}),
                    401,
                )

            user = db.session.get(User, user_id)
            if not user:
                return (
                    jsonify({"message": "User not found", "error": "user_not_found"}),
                    401,
                )

            if not user.is_active:
                return (
                    jsonify(
                        {
                            "message": "User account is deactivated",
                            "error": "account_deactivated",
                        }
                    ),
                    401,
                )

            # Pass user to the decorated function
            return f(user, *args, **kwargs)

        except Exception as e:
            current_app.logger.error(f"JWT authentication error: {e}")
            return (
                jsonify({"message": "Authentication failed", "error": "auth_failed"}),
                401,
            )

    return decorated_function


def admin_required(f):
    """Decorator that requires admin role."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()

            if not user_id:
                return (
                    jsonify({"message": "Invalid token", "error": "invalid_token"}),
                    401,
                )

            user = db.session.get(User, user_id)
            if not user:
                return (
                    jsonify({"message": "User not found", "error": "user_not_found"}),
                    401,
                )

            if not user.is_active:
                return (
                    jsonify(
                        {
                            "message": "User account is deactivated",
                            "error": "account_deactivated",
                        }
                    ),
                    401,
                )

            if user.role != "admin":
                return (
                    jsonify(
                        {"message": "Admin access required", "error": "admin_required"}
                    ),
                    403,
                )

            # Pass user to the decorated function
            return f(user, *args, **kwargs)

        except Exception as e:
            current_app.logger.error(f"Admin authentication error: {e}")
            return (
                jsonify({"message": "Authentication failed", "error": "auth_failed"}),
                401,
            )

    return decorated_function


def optional_jwt_user(f):
    """Decorator that optionally loads user if JWT token is present."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()

            if user_id:
                user = db.session.get(User, user_id)
                if user and not user.is_active:
                    user = None

        except Exception as e:
            # If JWT is invalid, just continue without user
            current_app.logger.debug(f"Optional JWT check failed: {e}")
            user = None

        # Pass user (or None) to the decorated function
        return f(user, *args, **kwargs)

    return decorated_function


def get_current_user():
    """Get the current authenticated user from JWT token."""
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()

        if not user_id:
            return None

        user = db.session.get(User, user_id)
        if user and user.is_active:
            return user

        return None

    except Exception:
        return None


def is_admin_user():
    """Check if the current user is an admin."""
    user = get_current_user()
    return user and user.role == "admin"


def can_access_user_data(target_user_id):
    """Check if the current user can access data for the target user."""
    current_user = get_current_user()

    if not current_user:
        return False

    # Admins can access all user data
    if current_user.role == "admin":
        return True

    # Users can only access their own data
    return current_user.id == target_user_id


def validate_user_limits(user, config_count=0, postback_count=0):
    """Validate if user can add more configs or postbacks."""
    errors = []

    if config_count > 0 and user.get_config_count() + config_count > 10:
        errors.append(f"Config limit exceeded. Maximum 10 configs allowed per user.")

    if postback_count > 0 and user.get_postback_count() + postback_count > 10000:
        errors.append(
            f"Postback limit exceeded. Maximum 10,000 postbacks allowed per user."
        )

    return errors
