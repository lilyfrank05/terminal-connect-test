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
            transaction_type=postback_data.get("transactionType", "N/A"),
            transaction_id=postback_data.get("transactionId") if postback_data.get("transactionId") else None,
            intent_id=postback_data.get("intentId", "unknown_intent"),
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
            .replace(microsecond=0)
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
    # Get pagination and search parameters
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search_query = request.args.get("search", "").strip()

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
        # Get user preferences for logged-in users
        current_user = db.session.get(User, user_id) if user_id else None
        column_preferences = {}
        if current_user and current_user.postback_column_preferences:
            try:
                column_preferences = json.loads(current_user.postback_column_preferences)
            except:
                column_preferences = {}
        
        # Default column visibility (intent_id and transaction_id hidden by default)
        default_preferences = {
            "time": True,
            "intent_id": False,
            "transaction_id": False,
            "status": True,
            "terminal_id": True,
            "transaction_type": True,
            "reference": True
        }
        column_preferences = {**default_preferences, **column_preferences}
        
        # Logged-in user: get postbacks from database with pagination
        query = UserPostback.query.filter_by(user_id=user_id)
        
        # Add search functionality
        if search_query:
            # Search in intent_id, transaction_id, and postback_data (for terminal_id)
            # Database-agnostic approach that works with both SQLite and PostgreSQL
            search_filter = db.or_(
                UserPostback.intent_id.ilike(f'%{search_query}%'),
                UserPostback.transaction_id.ilike(f'%{search_query}%'),
                # Simple string search in JSON data - works with both databases
                UserPostback.postback_data.ilike(f'%{search_query}%')
            )
            query = query.filter(search_filter)
        
        pagination = (
            query.order_by(UserPostback.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        # Format for template
        postbacks = []
        for pb in pagination.items:
            pb_data = json.loads(pb.postback_data)
            # Format time without microseconds
            formatted_time = pb.created_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            postbacks.append(
                {
                    "payload": pb_data.get("payload"),
                    "headers": pb_data.get("headers"),
                    "received_at": formatted_time,
                    "transaction_type": pb.transaction_type,
                    "transaction_id": pb.transaction_id,
                    "intent_id": pb.intent_id,
                }
            )
    else:
        # Guest user: default column preferences (intent_id and transaction_id hidden)
        column_preferences = {
            "time": True,
            "intent_id": False,
            "transaction_id": False,
            "status": True,
            "terminal_id": True,
            "transaction_type": True,
            "reference": True
        }
        
        # Guest user: get postbacks from file with manual pagination
        all_postbacks = load_guest_postbacks()
        
        # Apply search filter for guest users
        if search_query:
            filtered_postbacks = []
            for postback in all_postbacks:
                payload = postback.get("payload", {})
                # Search in intentId, transactionId (from payload.id), and terminalId
                intent_id = payload.get("intentId", "")
                transaction_id = payload.get("transactionId", "")
                terminal_id = payload.get("terminalId", "")
                
                if (search_query.lower() in intent_id.lower() or 
                    search_query.lower() in (transaction_id or "").lower() or 
                    search_query.lower() in (terminal_id or "").lower()):
                    filtered_postbacks.append(postback)
            all_postbacks = filtered_postbacks
        
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

    return render_template("postbacks.html", postbacks=postbacks, pagination=pagination, column_preferences=column_preferences, user_id=user_id)


@bp.route("/postbacks/column-preferences", methods=["POST"])
@optional_jwt_user
def save_column_preferences(user):
    """Save user's column visibility preferences"""
    # Get user_id from multiple sources
    user_id = None
    if user:  # JWT authenticated user
        user_id = user.id
    elif "user_id" in session:  # Session authenticated user
        user_id = session["user_id"]
    
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        preferences = request.get_json()
        current_user = db.session.get(User, user_id)
        if current_user:
            current_user.postback_column_preferences = json.dumps(preferences)
            db.session.commit()
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
