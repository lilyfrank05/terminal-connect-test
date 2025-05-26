import json
import datetime
import os
from flask import Blueprint, request, jsonify, render_template, current_app

bp = Blueprint("postbacks", __name__)


# Helper to clear the file if it's a new day
def clear_postbacks_if_new_day():
    today = datetime.date.today().isoformat()
    postbacks_file = current_app.config["POSTBACKS_FILE"]
    meta_file = postbacks_file + ".meta"

    # Ensure the directory exists
    os.makedirs(os.path.dirname(postbacks_file), exist_ok=True)

    # Read the last day from meta file
    last_day = None
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r") as f:
                last_day = f.read().strip()
        except Exception:
            last_day = None

    # If it's a new day or meta file is invalid, clear postbacks
    if last_day != today:
        try:
            # Clear postbacks file
            with open(postbacks_file, "w") as f:
                json.dump([], f)
            # Update meta file with today's date
            with open(meta_file, "w") as f:
                f.write(today)
            return True
        except Exception:
            return False
    return False


def load_postbacks():
    """Load postbacks from file, clearing if it's a new day."""
    clear_postbacks_if_new_day()
    postbacks_file = current_app.config["POSTBACKS_FILE"]
    try:
        if not os.path.exists(postbacks_file):
            return []
        with open(postbacks_file, "r") as f:
            data = f.read().strip()
            if not data:
                return []
            return json.loads(data)
    except Exception:
        return []


def save_postbacks(postbacks):
    postbacks_file = current_app.config["POSTBACKS_FILE"]
    with open(postbacks_file, "w") as f:
        json.dump(postbacks, f)


def mask_headers(headers):
    masked = dict(headers)
    if "Authorization" in masked:
        masked["Authorization"] = "***MASKED***"
    if "authorization" in masked:
        masked["authorization"] = "***MASKED***"
    return masked


@bp.route("/postback", methods=["POST"])
def postback():
    """Handle incoming postback messages from Terminal Connect"""
    # Get the postback data
    postback_data = request.get_json()
    # Record timestamp and headers
    record = {
        "payload": postback_data,
        "received_at": datetime.datetime.now(datetime.UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "headers": mask_headers(dict(request.headers)),
    }
    postbacks = load_postbacks()
    postbacks.append(record)
    if len(postbacks) > 50:
        postbacks = postbacks[-50:]
    save_postbacks(postbacks)
    # Return 200 OK
    return jsonify({"status": "success"}), 200


@bp.route("/postbacks", methods=["GET"])
def list_postbacks():
    """Display the list of received postbacks"""
    postbacks = load_postbacks()
    return render_template("postbacks.html", postbacks=postbacks)
