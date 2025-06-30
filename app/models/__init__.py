from datetime import datetime, timedelta, timezone
import bcrypt
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, DateTime, Boolean, ForeignKey, func
from typing import List, Optional


# Helper function to get timezone-naive UTC datetime (avoids deprecation warning)
def utc_now() -> datetime:
    """Get current UTC time as timezone-naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )  # 'admin' or 'user'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Password reset functionality
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    
    # Postback column preferences (JSON string)
    postback_column_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    configs: Mapped[List["UserConfig"]] = relationship(
        "UserConfig", back_populates="user", cascade="all, delete-orphan"
    )
    postbacks: Mapped[List["UserPostback"]] = relationship(
        "UserPostback", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Set password hash using bcrypt."""
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Check password against stored hash."""
        password_bytes = password.encode("utf-8")
        hash_bytes = self.password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)

    def generate_reset_token(self) -> str:
        """Generate a password reset token."""
        self.reset_token = str(uuid.uuid4())
        self.reset_token_expires = utc_now() + timedelta(hours=24)
        return self.reset_token

    def is_reset_token_valid(self, token: str) -> bool:
        """Check if reset token is valid and not expired."""
        if not self.reset_token or not self.reset_token_expires:
            return False
        return self.reset_token == token and utc_now() < self.reset_token_expires

    def clear_reset_token(self) -> None:
        """Clear the reset token after use."""
        self.reset_token = None
        self.reset_token_expires = None

    def get_config_count(self) -> int:
        """Get the number of configs for this user."""
        return len(self.configs)

    def get_postback_count(self) -> int:
        """Get the number of postbacks for this user."""
        return len(self.postbacks)

    def can_add_config(self) -> bool:
        """Check if user can add more configs (max 10)."""
        return self.get_config_count() < 10

    def can_add_postback(self) -> bool:
        """Check if user can add more postbacks (max 10,000)."""
        return self.get_postback_count() < 10000

    def to_dict(self) -> dict:
        """Convert user to dictionary for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "config_count": self.get_config_count(),
            "postback_count": self.get_postback_count(),
        }


class Invite(db.Model):
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # 'pending', 'accepted', 'expired', 'cancelled'
    invited_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __init__(
        self, email: str, role: str, invited_by: int, expires_in_hours: int = 72
    ):
        self.email = email
        self.role = role
        self.invited_by = invited_by
        self.token = str(uuid.uuid4())
        self.expires_at = utc_now() + timedelta(hours=expires_in_hours)

    def is_expired(self) -> bool:
        """Check if invite is expired."""
        return utc_now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if invite is valid (pending and not expired)."""
        return self.status == "pending" and not self.is_expired()

    def accept(self) -> None:
        """Mark invite as accepted."""
        self.status = "accepted"
        self.accepted_at = utc_now()

    def cancel(self) -> None:
        """Mark invite as cancelled."""
        self.status = "cancelled"

    def extend_expiry(self, hours: int = 72) -> None:
        """Extend invite expiry time and reactivate if expired or cancelled."""
        self.expires_at = utc_now() + timedelta(hours=hours)
        if self.status in ["expired", "cancelled"]:
            self.status = "pending"

    def to_dict(self) -> dict:
        """Convert invite to dictionary for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "invited_by": self.invited_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "is_expired": self.is_expired(),
        }


class UserConfig(db.Model):
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    mid: Mapped[str] = mapped_column(String(100), nullable=False)
    tid: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    postback_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    postback_delay: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="configs")

    def to_dict(self) -> dict:
        """Convert user config to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "environment": self.environment,
            "base_url": self.base_url,
            "mid": self.mid,
            "tid": self.tid,
            "api_key": self.api_key,
            "postback_url": self.postback_url,
            "postback_delay": self.postback_delay,
            "is_default": self.is_default,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserPostback(db.Model):
    __tablename__ = "user_postbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'sale', 'refund', 'reversal'
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    intent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    postback_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="postbacks")

    def to_dict(self) -> dict:
        """Convert user postback to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "transaction_type": self.transaction_type,
            "transaction_id": self.transaction_id,
            "intent_id": self.intent_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "postback_data": self.postback_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
