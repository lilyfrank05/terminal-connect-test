import json
import datetime
import os
from flask import Blueprint, request, jsonify, render_template, current_app, session
from .user import login_required
from app import db
from app.models.user import Postback, User

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
def postback():
    """Handle incoming postback messages from Terminal Connect"""
    postback_data = request.get_json()

    # If a logged-in user is making this request (e.g., via a saved config),
    # associate postback with them. Otherwise, handle as guest.
    user_id = session.get("user_id")

    if user_id:
        # Logged-in user: save to database
        count = Postback.query.filter_by(user_id=user_id).count()
        if count >= 10000:
            # Overwrite the oldest postback
            oldest = (
                Postback.query.filter_by(user_id=user_id)
                .order_by(Postback.created_at.asc())
                .first()
            )
            if oldest:
                db.session.delete(oldest)

        new_postback = Postback(
            user_id=user_id,
            data={
                "payload": postback_data,
                "headers": mask_headers(dict(request.headers)),
            },
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
@login_required
def list_postbacks():
    """Display the list of received postbacks"""
    postbacks = []
    if "user_id" in session:
        # Logged-in user: get from DB
        user_postbacks = (
            Postback.query.filter_by(user_id=session["user_id"])
            .order_by(Postback.created_at.desc())
            .all()
        )
        # Format for template
        for pb in user_postbacks:
            postbacks.append(
                {
                    "payload": pb.data.get("payload"),
                    "headers": pb.data.get("headers"),
                    "received_at": pb.created_at.isoformat().replace("+00:00", "Z"),
                }
            )
    else:
        # Guest user: get from file
        postbacks = load_guest_postbacks()

    return render_template("postbacks.html", postbacks=postbacks)
