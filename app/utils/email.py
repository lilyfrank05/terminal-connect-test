import os
import requests

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


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
    response = requests.post(BREVO_API_URL, json=data, headers=headers)
    if response.status_code != 201:
        print(
            f"Failed to send email. Status: {response.status_code}, Response: {response.text}"
        )
    return response.status_code == 201
