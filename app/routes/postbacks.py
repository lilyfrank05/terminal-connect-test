from flask import Blueprint, request, session, jsonify, render_template
import datetime

bp = Blueprint("postbacks", __name__)


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
    # Initialize postbacks list in session if it doesn't exist
    if "postbacks" not in session:
        session["postbacks"] = []
    # Add to session (keep last 50 postbacks)
    postbacks = session["postbacks"]
    postbacks.append(record)
    if len(postbacks) > 50:
        postbacks.pop(0)
    session["postbacks"] = postbacks
    # Return 200 OK
    return jsonify({"status": "success"}), 200


@bp.route("/postbacks", methods=["GET"])
def list_postbacks():
    """Display the list of received postbacks"""
    postbacks = session.get("postbacks", [])
    return render_template("postbacks.html", postbacks=postbacks)
