import json
import datetime
import os
from flask import Blueprint, request, jsonify, render_template

bp = Blueprint("postbacks", __name__)

POSTBACKS_FILE = "/tmp/postbacks.json"


# Helper to clear the file if it's a new day
def clear_postbacks_if_new_day():
    today = datetime.date.today().isoformat()
    meta_file = POSTBACKS_FILE + ".meta"
    last_day = None
    if os.path.exists(meta_file):
        with open(meta_file, "r") as f:
            last_day = f.read().strip()
    if last_day != today:
        with open(POSTBACKS_FILE, "w") as f:
            json.dump([], f)
        with open(meta_file, "w") as f:
            f.write(today)


def load_postbacks():
    clear_postbacks_if_new_day()
    try:
        with open(POSTBACKS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_postbacks(postbacks):
    with open(POSTBACKS_FILE, "w") as f:
        json.dump(postbacks, f)


@bp.route("/postback", methods=["POST"])
def postback():
    """Handle incoming postback messages from Terminal Connect"""
    # Get the postback data
    postback_data = request.get_json()
    # Record timestamp and headers
    record = {
        "payload": postback_data,
        "received_at": datetime.datetime.utcnow().isoformat() + "Z",
        "headers": dict(request.headers),
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
