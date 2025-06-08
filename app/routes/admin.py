from flask import Blueprint, request, jsonify, current_app
from marshmallow import Schema, fields, ValidationError, validate
from sqlalchemy.exc import IntegrityError
from ..models import db, User, Invite, UserConfig, UserPostback
from ..utils.auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# Marshmallow Schemas for validation
class InviteUserSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=120))
    role = fields.Str(required=True, validate=validate.OneOf(["admin", "user"]))


class UpdateUserSchema(Schema):
    email = fields.Email(validate=validate.Length(max=120))
    role = fields.Str(validate=validate.OneOf(["admin", "user"]))
    is_active = fields.Bool()


class UpdateInviteSchema(Schema):
    role = fields.Str(validate=validate.OneOf(["admin", "user"]))
    expires_in_hours = fields.Int(
        validate=validate.Range(min=1, max=720)
    )  # 1 hour to 30 days


# User Management Routes
@admin_bp.route("/users", methods=["GET"])
@admin_required
def get_users(admin_user):
    """Get all users with pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)  # Max 100 per page
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()
    active_filter = request.args.get("active", "").strip()

    query = User.query

    # Apply filters
    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))

    if role_filter in ["admin", "user"]:
        query = query.filter(User.role == role_filter)

    if active_filter.lower() in ["true", "false"]:
        is_active = active_filter.lower() == "true"
        query = query.filter(User.is_active == is_active)

    # Order by creation date
    query = query.order_by(User.created_at.desc())

    # Paginate
    users = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "users": [user.to_dict() for user in users.items],
                "pagination": {
                    "page": users.page,
                    "pages": users.pages,
                    "per_page": users.per_page,
                    "total": users.total,
                },
            }
        ),
        200,
    )


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@admin_required
def get_user(admin_user, user_id):
    """Get specific user details."""
    user = User.query.get_or_404(user_id)

    user_data = user.to_dict()
    user_data["configs"] = [config.to_dict() for config in user.configs]
    user_data["postback_count"] = user.get_postback_count()

    return jsonify({"user": user_data}), 200


@admin_bp.route("/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(admin_user, user_id):
    """Update user details."""
    try:
        schema = UpdateUserSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    user = User.query.get_or_404(user_id)

    # Prevent admin from deactivating themselves
    if user.id == admin_user.id and "is_active" in data and not data["is_active"]:
        return (
            jsonify(
                {
                    "message": "Cannot deactivate your own account",
                    "error": "self_deactivation",
                }
            ),
            400,
        )

    # Prevent changing the last admin's role
    if user.role == "admin" and "role" in data and data["role"] != "admin":
        admin_count = User.query.filter_by(role="admin", is_active=True).count()
        if admin_count <= 1:
            return (
                jsonify(
                    {
                        "message": "Cannot change role of the last admin",
                        "error": "last_admin",
                    }
                ),
                400,
            )

    try:
        # Update fields
        if "email" in data:
            data["email"] = data["email"].lower().strip()
            user.email = data["email"]

        if "role" in data:
            user.role = data["role"]

        if "is_active" in data:
            user.is_active = data["is_active"]

        db.session.commit()

        return (
            jsonify({"message": "User updated successfully", "user": user.to_dict()}),
            200,
        )

    except IntegrityError as e:
        db.session.rollback()
        if "UNIQUE constraint failed: users.email" in str(e):
            return (
                jsonify({"message": "Email already exists", "error": "email_exists"}),
                409,
            )
        return jsonify({"message": "Database error", "error": "db_error"}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"User update error: {e}")
        return jsonify({"message": "Update failed", "error": "update_failed"}), 500


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(admin_user, user_id):
    """Delete a user and all their data."""
    user = User.query.get_or_404(user_id)

    # Prevent admin from deleting themselves
    if user.id == admin_user.id:
        return (
            jsonify(
                {"message": "Cannot delete your own account", "error": "self_deletion"}
            ),
            400,
        )

    # Prevent deleting the last admin
    if user.role == "admin":
        admin_count = User.query.filter_by(role="admin", is_active=True).count()
        if admin_count <= 1:
            return (
                jsonify(
                    {"message": "Cannot delete the last admin", "error": "last_admin"}
                ),
                400,
            )

    try:
        # Delete user (cascading will handle configs and postbacks)
        db.session.delete(user)
        db.session.commit()

        return jsonify({"message": "User deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"User deletion error: {e}")
        return jsonify({"message": "Deletion failed", "error": "deletion_failed"}), 500


# Invite Management Routes
@admin_bp.route("/invites", methods=["GET"])
@admin_required
def get_invites(admin_user):
    """Get all invites with pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Invite.query

    # Apply filters
    if search:
        query = query.filter(Invite.email.ilike(f"%{search}%"))

    if status_filter in ["pending", "accepted", "expired", "cancelled"]:
        query = query.filter(Invite.status == status_filter)

    # Order by creation date
    query = query.order_by(Invite.created_at.desc())

    # Paginate
    invites = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "invites": [invite.to_dict() for invite in invites.items],
                "pagination": {
                    "page": invites.page,
                    "pages": invites.pages,
                    "per_page": invites.per_page,
                    "total": invites.total,
                },
            }
        ),
        200,
    )


@admin_bp.route("/invites", methods=["POST"])
@admin_required
def create_invite(admin_user):
    """Create a new user invite."""
    try:
        schema = InviteUserSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    email = data["email"].lower().strip()
    role = data["role"]

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"message": "User already exists", "error": "user_exists"}), 409

    # Check if there's already a pending invite
    existing_invite = Invite.query.filter_by(email=email, status="pending").first()
    if existing_invite and not existing_invite.is_expired():
        return (
            jsonify(
                {"message": "Pending invite already exists", "error": "invite_exists"}
            ),
            409,
        )

    try:
        # Create new invite
        invite = Invite(email=email, role=role, invited_by=admin_user.id)

        db.session.add(invite)
        db.session.commit()

        # TODO: Send email invitation
        current_app.logger.info(
            f"Invite created for {email} with token: {invite.token}"
        )

        return (
            jsonify(
                {"message": "Invite created successfully", "invite": invite.to_dict()}
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Invite creation error: {e}")
        return (
            jsonify({"message": "Invite creation failed", "error": "creation_failed"}),
            500,
        )


@admin_bp.route("/invites/<int:invite_id>", methods=["PUT"])
@admin_required
def update_invite(admin_user, invite_id):
    """Update an invite (extend expiry, change role)."""
    try:
        schema = UpdateInviteSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    invite = Invite.query.get_or_404(invite_id)

    if invite.status == "accepted":
        return (
            jsonify(
                {"message": "Cannot modify accepted invite", "error": "invite_accepted"}
            ),
            400,
        )

    try:
        # Update fields
        if "role" in data:
            invite.role = data["role"]

        if "expires_in_hours" in data:
            invite.extend_expiry(data["expires_in_hours"])

        db.session.commit()

        return (
            jsonify(
                {"message": "Invite updated successfully", "invite": invite.to_dict()}
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Invite update error: {e}")
        return jsonify({"message": "Update failed", "error": "update_failed"}), 500


@admin_bp.route("/invites/<int:invite_id>/cancel", methods=["POST"])
@admin_required
def cancel_invite(admin_user, invite_id):
    """Cancel an invite."""
    invite = Invite.query.get_or_404(invite_id)

    if invite.status == "accepted":
        return (
            jsonify(
                {"message": "Cannot cancel accepted invite", "error": "invite_accepted"}
            ),
            400,
        )

    if invite.status == "cancelled":
        return (
            jsonify(
                {"message": "Invite is already cancelled", "error": "already_cancelled"}
            ),
            400,
        )

    try:
        invite.cancel()
        db.session.commit()

        return (
            jsonify(
                {"message": "Invite cancelled successfully", "invite": invite.to_dict()}
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Invite cancellation error: {e}")
        return (
            jsonify({"message": "Cancellation failed", "error": "cancellation_failed"}),
            500,
        )


@admin_bp.route("/invites/<int:invite_id>/resend", methods=["POST"])
@admin_required
def resend_invite(admin_user, invite_id):
    """Resend/reactivate an invite with new expiry."""
    invite = Invite.query.get_or_404(invite_id)

    if invite.status == "accepted":
        return (
            jsonify(
                {"message": "Cannot resend accepted invite", "error": "invite_accepted"}
            ),
            400,
        )

    # Check if user was created after invite acceptance
    existing_user = User.query.filter_by(email=invite.email).first()
    if existing_user:
        return (
            jsonify(
                {
                    "message": "User already exists, cannot resend invite",
                    "error": "user_exists",
                }
            ),
            409,
        )

    try:
        # Extend expiry and reactivate
        invite.extend_expiry(72)  # 3 days
        invite.status = "pending"
        db.session.commit()

        # TODO: Send email invitation
        current_app.logger.info(
            f"Invite resent for {invite.email} with token: {invite.token}"
        )

        return (
            jsonify(
                {"message": "Invite resent successfully", "invite": invite.to_dict()}
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Invite resend error: {e}")
        return jsonify({"message": "Resend failed", "error": "resend_failed"}), 500


@admin_bp.route("/reinvite-user", methods=["POST"])
@admin_required
def reinvite_user(admin_user):
    """Create a new invite for a removed user."""
    email = request.json.get("email", "").lower().strip() if request.json else ""

    if not email:
        return jsonify({"message": "Email is required", "error": "email_required"}), 400

    # Check if user currently exists and is active
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.is_active:
        return (
            jsonify({"message": "User is already active", "error": "user_active"}),
            409,
        )

    # Check if there's already a pending invite
    existing_invite = Invite.query.filter_by(email=email, status="pending").first()
    if existing_invite and not existing_invite.is_expired():
        return (
            jsonify(
                {"message": "Pending invite already exists", "error": "invite_exists"}
            ),
            409,
        )

    try:
        # Determine role (use previous role if user existed, otherwise default to 'user')
        role = "user"
        if existing_user:
            role = existing_user.role

        # Create new invite
        invite = Invite(email=email, role=role, invited_by=admin_user.id)

        db.session.add(invite)
        db.session.commit()

        # TODO: Send email invitation
        current_app.logger.info(
            f"Reinvite created for {email} with token: {invite.token}"
        )

        return (
            jsonify(
                {"message": "Reinvite created successfully", "invite": invite.to_dict()}
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reinvite creation error: {e}")
        return (
            jsonify(
                {"message": "Reinvite creation failed", "error": "creation_failed"}
            ),
            500,
        )


# Statistics Routes
@admin_bp.route("/stats", methods=["GET"])
@admin_required
def get_admin_stats(admin_user):
    """Get admin dashboard statistics."""
    try:
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        admin_users = User.query.filter_by(role="admin", is_active=True).count()

        pending_invites = Invite.query.filter_by(status="pending").count()
        expired_invites = Invite.query.filter(
            Invite.status == "pending", Invite.expires_at < db.func.now()
        ).count()

        total_configs = UserConfig.query.count()
        total_postbacks = UserPostback.query.count()

        return (
            jsonify(
                {
                    "users": {
                        "total": total_users,
                        "active": active_users,
                        "inactive": total_users - active_users,
                        "admins": admin_users,
                    },
                    "invites": {"pending": pending_invites, "expired": expired_invites},
                    "data": {"configs": total_configs, "postbacks": total_postbacks},
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Admin stats error: {e}")
        return (
            jsonify({"message": "Failed to fetch statistics", "error": "stats_failed"}),
            500,
        )
