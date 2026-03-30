import json
import os
import requests
from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
    session,
)

from ..utils.auth import optional_jwt_user
from ..utils.api import VERIFY_PATH, _get_timeout_seconds

bp = Blueprint("wu_check", __name__)


def _load_wu_keys():
    """Load WU API keys from config/wu_keys.json. Returns dict or None on error."""
    keys_path = os.path.normpath(
        os.path.join(current_app.root_path, "..", "config", "wu_keys.json")
    )
    try:
        with open(keys_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, IOError) as e:
        current_app.logger.error(f"Failed to load wu_keys.json: {e}")
        return None


@bp.route("/wu-check", methods=["GET", "POST"])
@optional_jwt_user
def wu_check(user):
    if not current_app.config.get("ENABLE_WU_CHECK", False):
        abort(404)

    # Guest-only: reject authenticated users
    if user is not None or "user_id" in session:
        abort(404)

    keys = _load_wu_keys()
    key_names = list(keys.keys()) if keys else []

    result = None
    error = None
    selected_key = None
    mid_value = ""

    if request.method == "POST":
        mid_value = request.form.get("mid", "").strip()
        selected_key = request.form.get("key_name", "").strip()

        # Validate MID: numeric digits only, 1–8 digits
        if not mid_value.isdigit() or not (1 <= len(mid_value) <= 8):
            error = "MID must be 1–8 numeric digits."
        elif keys is None:
            error = "WU keys configuration file not found."
        elif selected_key not in keys:
            error = "Invalid key selection."
        else:
            api_key = keys[selected_key]
            base = current_app.config["WU_API_BASE_URL"].rstrip("/")
            url = f"{base}/merchant/{mid_value}/terminals"
            try:
                timeout = _get_timeout_seconds()
                resp = requests.get(
                    url,
                    headers={"x-api-key": api_key},
                    timeout=timeout,
                    verify=VERIFY_PATH,
                )
                try:
                    body_str = json.dumps(resp.json(), indent=2)
                except ValueError:
                    body_str = resp.text
                result = {"status_code": resp.status_code, "body": body_str}
            except requests.exceptions.Timeout:
                error = "Request timed out."
            except requests.exceptions.RequestException:
                current_app.logger.error(
                    "WU check request to %s failed", url, exc_info=True
                )
                error = "Request failed. Please try again."

    return render_template(
        "wu_check.html",
        key_names=key_names,
        result=result,
        error=error,
        selected_key=selected_key,
        mid_value=mid_value,
        keys_available=keys is not None,
    )
