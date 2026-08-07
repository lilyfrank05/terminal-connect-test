"""
Shared Marshmallow schemas for request validation.
Consolidated from route files to avoid duplication.
"""

from marshmallow import Schema, fields, validate


# ── Auth schemas ──

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


# ── Admin schemas ──

class InviteUserSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=120))
    role = fields.Str(required=True, validate=validate.OneOf(["admin", "user"]))


class UpdateUserSchema(Schema):
    email = fields.Email(validate=validate.Length(max=120))
    role = fields.Str(validate=validate.OneOf(["admin", "user"]))
    is_active = fields.Bool()


class UpdateInviteSchema(Schema):
    role = fields.Str(validate=validate.OneOf(["admin", "user"]))
    expires_in_hours = fields.Int(validate=validate.Range(min=1, max=720))


# ── Config schemas ──

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