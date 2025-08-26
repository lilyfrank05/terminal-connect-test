from flask import Blueprint, request, jsonify, current_app
from marshmallow import Schema, fields, ValidationError, validate
from sqlalchemy.exc import IntegrityError
from ..models import db, UserConfig
from ..utils.auth import jwt_required_with_user, optional_jwt_user
from ..utils.api import ENVIRONMENT_URLS
from ..utils.validation import validate_url

user_config_bp = Blueprint("user_config", __name__, url_prefix="/api/user/configs")


# Marshmallow Schemas for validation
class CreateConfigSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    environment = fields.Str(
        required=True, validate=validate.OneOf(["sandbox", "production"])
    )
    mid = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    tid = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    api_key = fields.Str(required=True, validate=validate.Length(min=1))
    postback_url = fields.Str(validate=validate.Length(max=255))
    is_default = fields.Bool(load_default=False)


class UpdateConfigSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=100))
    environment = fields.Str(validate=validate.OneOf(["sandbox", "production"]))
    mid = fields.Str(validate=validate.Length(min=1, max=100))
    tid = fields.Str(validate=validate.Length(min=1, max=100))
    api_key = fields.Str(validate=validate.Length(min=1))
    postback_url = fields.Str(validate=validate.Length(max=255))
    is_default = fields.Bool()


@user_config_bp.route("", methods=["GET"])
@jwt_required_with_user
def get_user_configs(user):
    """Get all configurations for the authenticated user."""
    page = request.args.get("page", 1, type=int)
    per_page = min(
        request.args.get("per_page", 10, type=int), 10
    )  # Max 10 (user limit)

    configs = (
        UserConfig.query.filter_by(user_id=user.id)
        .order_by(UserConfig.is_default.desc(), UserConfig.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return (
        jsonify(
            {
                "configs": [config.to_dict() for config in configs.items],
                "pagination": {
                    "page": configs.page,
                    "pages": configs.pages,
                    "per_page": configs.per_page,
                    "total": configs.total,
                },
                "can_add_more": user.can_add_config(),
            }
        ),
        200,
    )


@user_config_bp.route("/<int:config_id>", methods=["GET"])
@jwt_required_with_user
def get_user_config(user, config_id):
    """Get a specific configuration for the authenticated user."""
    config = UserConfig.query.filter_by(id=config_id, user_id=user.id).first()

    if not config:
        return (
            jsonify(
                {"message": "Configuration not found", "error": "config_not_found"}
            ),
            404,
        )

    return jsonify({"config": config.to_dict()}), 200


@user_config_bp.route("", methods=["POST"])
@jwt_required_with_user
def create_user_config(user):
    """Create a new configuration for the authenticated user."""
    try:
        schema = CreateConfigSchema()
        data = schema.load(request.json or {})
    except ValidationError as e:
        return jsonify({"message": "Validation error", "errors": e.messages}), 400

    # Check user limits
    if not user.can_add_config():
        return (
            jsonify(
                {
                    "message": f"Configuration limit exceeded. Maximum {50 if user.role == 'admin' else 10} configurations allowed.",
                    "error": "config_limit_exceeded",
                }
            ),
            400,
        )

    # Validate postback URL if provided
    postback_url = data.get("postback_url", "").strip()
    if postback_url:
        is_valid, error = validate_url(postback_url)
        if not is_valid:
            return (
                jsonify(
                    {
                        "message": f"Invalid postback URL: {error}",
                        "error": "invalid_url",
                    }
                ),
                400,
            )

    # If no postback URL provided, use default
    if not postback_url:
        postback_url = current_app.config.get("DEFAULT_POSTBACK_URL", "/api/postbacks")

    # Set base URL based on environment
    base_url = ENVIRONMENT_URLS.get(data["environment"])
    if not base_url:
        return (
            jsonify({"message": "Invalid environment", "error": "invalid_environment"}),
            400,
        )

    try:
        # If this is set as default, unset other defaults
        if data.get("is_default", False):
            UserConfig.query.filter_by(user_id=user.id, is_default=True).update(
                {"is_default": False}
            )

        # Create new configuration
        config = UserConfig(
            user_id=user.id,
            name=data["name"],
            environment=data["environment"],
            base_url=base_url,
            mid=data["mid"],
            tid=data["tid"],
            api_key=data["api_key"],
            is_default=data.get("is_default", False),
        )

        db.session.add(config)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Configuration created successfully",
                    "config": config.to_dict(),
                }
            ),
            201,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": "Database error", "error": "db_error"}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Config creation error: {e}")
        return (
            jsonify(
                {"message": "Configuration creation failed", "error": "creation_failed"}
            ),
            500,
        )
