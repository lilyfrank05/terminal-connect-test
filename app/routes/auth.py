from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from marshmallow import Schema, fields, ValidationError, validate
from ..models import db, User, Invite
from ..utils.auth import jwt_required_with_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# Marshmallow Schemas for validation
class LoginSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=120))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=255))


class RegisterSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=120))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=255))
    token = fields.Str(required=True, validate=validate.Length(min=1))


class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=120))


class PasswordResetSchema(Schema):
    token = fields.Str(required=True, validate=validate.Length(min=1))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=255))


class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True, validate=validate.Length(min=1))
    new_password = fields.Str(required=True, validate=validate.Length(min=6, max=255))


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user and return JWT tokens."""
    try:
        schema = LoginSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    email = data["email"].lower().strip()
    password = data["password"]

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return (
            jsonify(
                {"message": "Invalid email or password", "error": "invalid_credentials"}
            ),
            401,
        )

    if not user.is_active:
        return (
            jsonify(
                {"message": "Account is deactivated", "error": "account_deactivated"}
            ),
            401,
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    # Create JWT tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return (
        jsonify(
            {
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_dict(),
            }
        ),
        200,
    )


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user using an invite token."""
    try:
        schema = RegisterSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    email = data["email"].lower().strip()
    password = data["password"]
    token = data["token"]

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"message": "User already exists", "error": "user_exists"}), 409

    # Find and validate invite
    invite = Invite.query.filter_by(token=token).first()
    if not invite:
        return (
            jsonify({"message": "Invalid invite token", "error": "invalid_invite"}),
            400,
        )

    if not invite.is_valid():
        return (
            jsonify(
                {
                    "message": "Invite has expired or is no longer valid",
                    "error": "invalid_invite",
                }
            ),
            400,
        )

    if invite.email.lower() != email:
        return (
            jsonify(
                {"message": "Email doesn't match invite", "error": "email_mismatch"}
            ),
            400,
        )

    try:
        # Create new user
        user = User(email=email, role=invite.role, is_active=True)
        user.set_password(password)

        # Accept the invite
        invite.accept()

        db.session.add(user)
        db.session.commit()

        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return (
            jsonify(
                {
                    "message": "Registration successful",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": user.to_dict(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {e}")
        return (
            jsonify({"message": "Registration failed", "error": "registration_failed"}),
            500,
        )


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token."""
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user or not user.is_active:
        return (
            jsonify({"message": "User not found or inactive", "error": "user_invalid"}),
            401,
        )

    # Create new access token
    access_token = create_access_token(identity=user.id)

    return (
        jsonify(
            {
                "message": "Token refreshed",
                "access_token": access_token,
                "user": user.to_dict(),
            }
        ),
        200,
    )


@auth_bp.route("/me", methods=["GET"])
@jwt_required_with_user
def get_current_user(user):
    """Get current user information."""
    return jsonify({"user": user.to_dict()}), 200


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required_with_user
def change_password(user):
    """Change user password."""
    try:
        schema = ChangePasswordSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    current_password = data["current_password"]
    new_password = data["new_password"]

    # Verify current password
    if not user.check_password(current_password):
        return (
            jsonify(
                {
                    "message": "Current password is incorrect",
                    "error": "invalid_password",
                }
            ),
            400,
        )

    # Update password
    user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Password changed successfully"}), 200


@auth_bp.route("/request-password-reset", methods=["POST"])
def request_password_reset():
    """Request password reset token."""
    try:
        schema = PasswordResetRequestSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    email = data["email"].lower().strip()
    user = User.query.filter_by(email=email).first()

    if not user:
        # Don't reveal if email exists
        return (
            jsonify({"message": "If the email exists, a reset token will be sent"}),
            200,
        )

    if not user.is_active:
        return (
            jsonify(
                {"message": "Account is deactivated", "error": "account_deactivated"}
            ),
            400,
        )

    # Generate reset token
    reset_token = user.generate_reset_token()
    db.session.commit()

    # TODO: Send email with reset token
    # For now, just log it (in production, integrate with email service)
    current_app.logger.info(f"Password reset token for {email}: {reset_token}")

    return jsonify({"message": "If the email exists, a reset token will be sent"}), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Reset password using token."""
    try:
        schema = PasswordResetSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    token = data["token"]
    new_password = data["password"]

    # Find user with valid reset token
    user = User.query.filter(User.reset_token == token).first()

    if not user or not user.is_reset_token_valid(token):
        return (
            jsonify(
                {"message": "Invalid or expired reset token", "error": "invalid_token"}
            ),
            400,
        )

    # Update password and clear reset token
    user.set_password(new_password)
    user.clear_reset_token()
    db.session.commit()

    return jsonify({"message": "Password reset successful"}), 200


@auth_bp.route("/validate-invite", methods=["POST"])
def validate_invite():
    """Validate an invite token."""
    token = request.json.get("token") if request.json else None

    if not token:
        return jsonify({"message": "Token is required", "error": "token_required"}), 400

    invite = Invite.query.filter_by(token=token).first()

    if not invite:
        return (
            jsonify({"message": "Invalid invite token", "error": "invalid_invite"}),
            400,
        )

    if not invite.is_valid():
        return (
            jsonify(
                {
                    "message": "Invite has expired or is no longer valid",
                    "error": "invalid_invite",
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "message": "Invite is valid",
                "invite": {
                    "email": invite.email,
                    "role": invite.role,
                    "expires_at": invite.expires_at.isoformat(),
                },
            }
        ),
        200,
    )
