import os
import requests
from flask import current_app

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _get_timeout_seconds():
    try:
        # Prefer app config, fallback to env, then default
        if current_app:
            val = int(current_app.config.get("API_REQUEST_TIMEOUT", 60))
        else:
            val = int(os.getenv("API_REQUEST_TIMEOUT", "60"))
        if val < 1:
            return 60
        if val > 300:
            return 300
        return val
    except Exception:
        return 60


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = {
        "sender": {
            "name": "App",
            "email": os.getenv("ADMIN_EMAIL", "admin@example.com"),
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    try:
        response = requests.post(
            BREVO_API_URL,
            json=data,
            headers=headers,
            timeout=_get_timeout_seconds(),
        )
        if response.status_code != 201:
            print(
                f"Failed to send email. Status: {response.status_code}, Response: {response.text}"
            )
        return response.status_code == 201
    except requests.exceptions.Timeout:
        print("Failed to send email: request timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Failed to send email: {e}")
        return False
