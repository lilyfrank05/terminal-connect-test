from datetime import datetime, UTC
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(db.Model):
    """User model for authentication and role management."""

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(32), default="user", nullable=False, index=True
    )  # 'admin' or 'user'
    is_active = db.Column(db.Boolean, default=True)
    is_suspended = db.Column(db.Boolean, default=False)
    failed_login_attempts = db.Column(db.Integer, default=0)
    password_reset_token = db.Column(db.String(128), unique=True, nullable=True)
    password_reset_expiration = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    configs = relationship(
        "Configuration", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    postbacks = relationship(
        "Postback", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    invites = relationship("Invite", backref="inviter", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Invite(db.Model):
    """Invite model for invite-only registration and password reset tokens."""

    __tablename__ = "invites"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    role = db.Column(db.String(32), default="user", nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    is_canceled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    used_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id"))


class Configuration(db.Model):
    """Configuration model for user-saved configurations (max 10 per user)."""

    __tablename__ = "configurations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    name = db.Column(db.String(128), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class Postback(db.Model):
    """Postback model for user-saved postbacks (max 10,000 per user, FIFO)."""

    __tablename__ = "postbacks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
