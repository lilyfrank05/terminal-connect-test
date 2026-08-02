import time
from flask import session, url_for


def generate_merchant_reference():
    """Generate a default merchant reference using Unix timestamp"""
    return str(int(time.time()))


def is_charge_anywhere_tid(tid):
    """Check if TID starts with 'WP' (Charge Anywhere TID)"""
    return tid and tid.startswith("WP")


def get_postback_url():
    """Get postback URL from session or generate appropriate one."""
    postback_url = session.get("POSTBACK_URL")
    if not postback_url:
        if session.get("user_id"):
            postback_url = url_for(
                "postbacks.postback", user_id=session["user_id"], _external=True
            )
        else:
            postback_url = url_for("postbacks.postback", _external=True)
    return postback_url
