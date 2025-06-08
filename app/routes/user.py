from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    render_template,
    redirect,
    url_for,
    session,
    flash,
)
from ..models import db, User, Invite, UserConfig, UserPostback
from app.utils.email import send_email
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, UTC
import uuid
import os
from functools import wraps


def login_required(view):
    """
    Decorator to ensure a user is either logged in or a guest.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session and not session.get("is_guest"):
            flash("Please log in or continue as a guest to view this page.", "warning")
            return redirect(url_for("user.login_page"))
        return view(*args, **kwargs)

    return wrapped


def user_only_required(view):
    """
    Decorator to ensure a user is logged in (not a guest).
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("You must be logged in to view this page.", "danger")
            return redirect(url_for("user.login_page"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @user_only_required  # Admin must be a logged-in user
    def wrapped(*args, **kwargs):
        user = db.session.get(User, session["user_id"])
        if not user or user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("user.login_page"))
        return view(*args, **kwargs)

    return wrapped


def create_user_blueprint(name="user"):
    user_bp = Blueprint(name, __name__)

    # --- Auth & User Management ---
    # NOTE: All API-only routes have been removed for clarity as per user request.
    # Browser-facing routes are below.

    # --- Browser-facing routes ---
    @user_bp.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                return render_template("login.html", error="Invalid credentials")
            if not user.is_active:
                return render_template(
                    "login.html",
                    error="Account suspended. Use password reset to unlock.",
                )
            session["user_id"] = user.id
            session["user_role"] = user.role
            return redirect(url_for("user.profile_page"))
        return render_template("login.html")

    @user_bp.route("/guest-login")
    def guest_login():
        session["is_guest"] = True
        flash("You are browsing as a guest.", "info")
        return redirect(url_for("config.config"))

    @user_bp.route("/logout")
    def logout_page():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("user.login_page"))

    @user_bp.route("/register", methods=["GET", "POST"])
    def register_page():
        # If user is logged in, log them out first
        if "user_id" in session:
            session.clear()
            flash("You have been logged out to complete your registration.", "info")

        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            token = request.form["token"]
            invite = Invite.query.filter_by(token=token).first()
            if not invite or not invite.is_valid() or invite.email != email:
                return render_template(
                    "register.html", error="Invalid or expired invite"
                )
            if User.query.filter_by(email=email).first():
                return render_template("register.html", error="User already exists")
            user_role = getattr(invite, "role", "user")
            user = User(email=email, role=user_role)
            user.set_password(password)
            db.session.add(user)
            invite.accept()
            db.session.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("user.login_page"))

        token = request.args.get("token")
        if not token:
            flash("No invite token provided.", "danger")
            return redirect(url_for("user.login_page"))

        invite = Invite.query.filter_by(token=token).first()

        if not invite or not invite.is_valid():
            flash("Invalid or expired invite token.", "danger")
            return redirect(url_for("user.login_page"))

        return render_template("register.html", token=invite.token, email=invite.email)

    @user_bp.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password_page():
        if request.method == "POST":
            email = request.form["email"]
            user = User.query.filter_by(email=email).first()
            if user:
                # Generate a random token
                token = str(uuid.uuid4())
                user.reset_token = token
                user.reset_token_expires = datetime.now(UTC) + timedelta(hours=1)
                db.session.commit()

                # Send password reset email
                reset_link = url_for(
                    "user.reset_password_page", token=token, _external=True
                )
                send_email(
                    user.email,
                    "Password Reset Request",
                    f"Click here to reset your password: {reset_link}",
                )

            # Show a generic message to prevent user enumeration
            flash(
                "If an account with that email exists, a password reset link has been sent.",
                "info",
            )
            return redirect(url_for("user.login_page"))
        return render_template("forgot_password.html")

    @user_bp.route("/reset-password", methods=["GET", "POST"])
    def reset_password_page():
        token = request.args.get("token") or request.form.get("token")
        if not token:
            flash("Password reset token is missing.", "danger")
            return redirect(url_for("user.login_page"))

        user = User.query.filter_by(reset_token=token).first()

        if not user or user.reset_token_expires.replace(tzinfo=UTC) < datetime.now(UTC):
            flash("Password reset token is invalid or has expired.", "danger")
            return redirect(url_for("user.login_page"))

        if request.method == "POST":
            password = request.form["password"]
            user.set_password(password)
            user.reset_token = None
            user.reset_token_expires = None
            user.is_active = True
            db.session.commit()
            flash(
                "Your password has been reset successfully. Please log in.", "success"
            )
            return redirect(url_for("user.login_page"))

        return render_template("reset_password.html", token=token)

    @user_bp.route("/profile", methods=["GET"])
    @user_only_required
    def profile_page():
        user = db.session.get(User, session["user_id"])
        return render_template("profile.html", user=user)

    @user_bp.route("/change-password", methods=["POST"])
    @user_only_required
    def change_password():
        user_id = session["user_id"]
        user = db.session.get(User, user_id)
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        if not user.check_password(current_password):
            flash("Current password is not correct.", "danger")
            return redirect(url_for("user.profile_page"))
        user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for("user.profile_page"))

    # --- Admin pages ---
    @user_bp.route("/admin/invites", methods=["GET"])
    @admin_required
    def manage_invites():
        invites = Invite.query.order_by(Invite.created_at.desc()).all()
        return render_template("admin/manage_invites.html", invites=invites)

    @user_bp.route("/admin/invites/send", methods=["POST"])
    @admin_required
    def send_invite():
        email = request.form.get("email")
        role = request.form.get("role", "user")
        admin = db.session.get(User, session["user_id"])

        if not email:
            flash("Email is required.", "danger")
            return redirect(url_for("user.manage_invites"))

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash("User with this email already exists.", "warning")
            return redirect(url_for("user.manage_invites"))

        # Check for existing invites
        existing_invite = Invite.query.filter_by(email=email).first()

        if existing_invite:
            if existing_invite.status == "accepted":
                # Check if the user still exists - if they were removed, allow re-inviting
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    flash("This email has already been used to register.", "warning")
                    return redirect(url_for("user.manage_invites"))
                else:
                    # User was removed, create a new invite
                    new_invite = Invite(email=email, invited_by=admin.id, role=role)
                    db.session.add(new_invite)
                    db.session.commit()

                    # Send new invite email
                    invite_link = url_for(
                        "user.register_page",
                        token=new_invite.token,
                        _external=True,
                    )
                    send_email(
                        email,
                        "You are invited to join Terminal Connect Test",
                        f"Click here to register: {invite_link}",
                    )
                    flash(
                        f"New invitation sent to {email} (previous user was removed)",
                        "success",
                    )
                    return redirect(url_for("user.manage_invites"))
            elif existing_invite.status == "pending":
                flash("This email already has a pending invite.", "warning")
                return redirect(url_for("user.manage_invites"))
            elif existing_invite.status in ["cancelled", "expired"]:
                # Extend the existing invite
                existing_invite.extend_expiry()
                existing_invite.role = role  # Update role if changed
                existing_invite.invited_by = admin.id  # Update inviter
                db.session.commit()

                # Send reactivated invite email
                invite_link = url_for(
                    "user.register_page", token=existing_invite.token, _external=True
                )
                send_email(
                    email,
                    "You are invited to join Terminal Connect Test",
                    f"Click here to register: {invite_link}",
                )
                flash(f"Invitation reactivated and sent to {email}", "success")
                return redirect(url_for("user.manage_invites"))

        # Create new invite if none exists
        invite = Invite(email=email, invited_by=admin.id, role=role)
        db.session.add(invite)
        db.session.commit()

        # Send invite email
        invite_link = url_for("user.register_page", token=invite.token, _external=True)
        send_email(
            email,
            "You are invited to join Terminal Connect Test",
            f"Click here to register: {invite_link}",
        )
        flash(f"Invitation sent to {email}", "success")
        return redirect(url_for("user.manage_invites"))

    @user_bp.route("/admin/invites/cancel/<int:invite_id>", methods=["POST"])
    @admin_required
    def cancel_invite(invite_id):
        invite = db.get_or_404(Invite, invite_id)
        if invite.status in ["accepted", "cancelled"]:
            flash("This invite cannot be canceled.", "warning")
        else:
            invite.cancel()
            db.session.commit()
            flash(f"Invite for {invite.email} has been canceled.", "success")
        return redirect(url_for("user.manage_invites"))

    @user_bp.route("/admin/users", methods=["GET", "POST"])
    @admin_required
    def user_list():
        if request.method == "POST":
            user_id_or_email = request.form["user_id"]
            user = None
            if user_id_or_email.isdigit():
                user = db.session.get(User, int(user_id_or_email))
            else:
                user = User.query.filter_by(email=user_id_or_email).first()
            if not user or user.role == "admin":
                flash("User not found or cannot remove admin", "danger")
                return redirect(url_for("user.user_list"))
            db.session.delete(user)
            db.session.commit()
            flash("User removed successfully.", "success")
            return redirect(url_for("user.user_list"))
        users = User.query.all()
        return render_template("admin/user_list.html", users=users)

    return user_bp
