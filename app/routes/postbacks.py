import json
import datetime
import os
from flask import Blueprint, request, jsonify, render_template, current_app, session
from ..utils.auth import optional_jwt_user
from ..models import db
from ..models import UserPostback, User

bp = Blueprint("postbacks", __name__)

# --- Guest User Postback Helpers (File-based) ---


def clear_guest_postbacks_if_new_day():
    today = datetime.date.today().isoformat()
    postbacks_file = current_app.config["POSTBACKS_FILE"]
    meta_file = postbacks_file + ".meta"
    os.makedirs(os.path.dirname(postbacks_file), exist_ok=True)
    last_day = None
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r") as f:
                last_day = f.read().strip()
        except Exception:
            last_day = None
    if last_day != today:
        try:
            with open(postbacks_file, "w") as f:
                json.dump([], f)
            with open(meta_file, "w") as f:
                f.write(today)
        except Exception:
            pass


def load_guest_postbacks():
    clear_guest_postbacks_if_new_day()
    postbacks_file = current_app.config["POSTBACKS_FILE"]
    try:
        if not os.path.exists(postbacks_file):
            return []
        with open(postbacks_file, "r") as f:
            data = f.read().strip()
            return json.loads(data) if data else []
    except Exception:
        return []


def save_guest_postbacks(postbacks):
    postbacks_file = current_app.config["POSTBACKS_FILE"]
    with open(postbacks_file, "w") as f:
        json.dump(postbacks, f)


# --- General Helpers ---


def mask_headers(headers):
    masked = dict(headers)
    if "Authorization" in masked:
        masked["Authorization"] = "***MASKED***"
    if "authorization" in masked:
        masked["authorization"] = "***MASKED***"
    return masked


# --- Routes ---


@bp.route("/postback", methods=["POST"])
@bp.route("/postback/<int:user_id>", methods=["POST"])
@optional_jwt_user
def postback(user=None, user_id=None):
    """Handle incoming postback messages from Terminal Connect"""
    postback_data = request.get_json()

    # Determine user_id from multiple sources (priority order):
    # 1. URL parameter (for user-specific postback URLs)
    # 2. JWT authenticated user
    # 3. Session authenticated user
    if user_id:
        # URL parameter takes precedence (user-specific postback URL)
        pass
    elif user:  # JWT authenticated user
        user_id = user.id
    elif "user_id" in session:  # Session authenticated user
        user_id = session.get("user_id")
    else:
        user_id = None

    if user_id:
        # Logged-in user: save to database
        count = UserPostback.query.filter_by(user_id=user_id).count()
        if count >= 10000:
            # Overwrite the oldest postback
            oldest = (
                UserPostback.query.filter_by(user_id=user_id)
                .order_by(UserPostback.created_at.asc())
                .first()
            )
            if oldest:
                db.session.delete(oldest)

        new_postback = UserPostback(
            user_id=user_id,
            transaction_type="postback",
            transaction_id=str(postback_data.get("id", "")),
            status="received",
            postback_data=json.dumps(
                {
                    "payload": postback_data,
                    "headers": mask_headers(dict(request.headers)),
                }
            ),
        )
        db.session.add(new_postback)
        db.session.commit()
    else:
        # Guest user: save to file
        record = {
            "payload": postback_data,
            "received_at": datetime.datetime.now(datetime.UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "headers": mask_headers(dict(request.headers)),
        }
        postbacks = load_guest_postbacks()
        postbacks.append(record)
        if len(postbacks) > 50:
            postbacks = postbacks[-50:]
        save_guest_postbacks(postbacks)

    return jsonify({"status": "success"}), 200


@bp.route("/postbacks", methods=["GET"])
@optional_jwt_user
def list_postbacks(user):
    """Display the list of received postbacks with pagination"""
    # Get pagination parameters
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # Validate per_page options
    if per_page not in [20, 50, 100]:
        per_page = 20

    # Check if user is authenticated (either via session or JWT)
    user_id = None
    if user:  # JWT authenticated user
        user_id = user.id
    elif "user_id" in session:  # Session authenticated user
        user_id = session["user_id"]

    if user_id:
        # Logged-in user: get postbacks from database with pagination
        pagination = (
            UserPostback.query.filter_by(user_id=user_id)
            .order_by(UserPostback.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        # Format for template
        postbacks = []
        for pb in pagination.items:
            pb_data = json.loads(pb.postback_data)
            postbacks.append(
                {
                    "payload": pb_data.get("payload"),
                    "headers": pb_data.get("headers"),
                    "received_at": pb.created_at.isoformat().replace("+00:00", "Z"),
                }
            )
    else:
        # Guest user: get postbacks from file with manual pagination
        all_postbacks = load_guest_postbacks()
        # Sort guest postbacks by received_at in descending order (newest first)
        all_postbacks.sort(key=lambda x: x.get("received_at", ""), reverse=True)

        # Manual pagination for file-based postbacks
        total = len(all_postbacks)
        start = (page - 1) * per_page
        end = start + per_page
        postbacks = all_postbacks[start:end]

        # Create a simple pagination object for template consistency
        class SimplePagination:
            def __init__(self, page, per_page, total):
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
                self.items = postbacks

        pagination = SimplePagination(page, per_page, total)

    return render_template("postbacks.html", postbacks=postbacks, pagination=pagination)
