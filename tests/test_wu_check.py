import pytest
import requests_mock as rm
import requests
from unittest.mock import patch

WU_TERMINALS_URL = (
    "https://api-terminal-gateway.tillpayments.com/devices/merchant/{mid}/terminals"
)

MOCK_KEYS = {"production": "prod-key-123", "sandbox": "sandbox-key-456"}


def _enable_wu_check(app):
    app.config["ENABLE_WU_CHECK"] = True


class TestWuCheck:
    def test_wu_check_disabled_returns_404(self, client, app):
        app.config["ENABLE_WU_CHECK"] = False
        response = client.get("/wu-check")
        assert response.status_code == 404

    def test_wu_check_get_as_guest(self, client, app):
        _enable_wu_check(app)
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            response = client.get("/wu-check")
        assert response.status_code == 200
        assert b"WU Check" in response.data
        assert b"production" in response.data
        assert b"sandbox" in response.data

    def test_wu_check_get_session_logged_in_returns_404(self, client, app):
        _enable_wu_check(app)
        with client.session_transaction() as sess:
            sess["user_id"] = 1
        response = client.get("/wu-check")
        assert response.status_code == 404

    def test_wu_check_no_keys_file(self, client, app):
        _enable_wu_check(app)
        with patch("app.routes.wu_check._load_wu_keys", return_value=None):
            response = client.get("/wu-check")
        assert response.status_code == 200
        assert b"not found" in response.data

    def test_wu_check_post_invalid_mid_alpha(self, client, app):
        _enable_wu_check(app)
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            response = client.post(
                "/wu-check", data={"mid": "abcd1234", "key_name": "production"}
            )
        assert response.status_code == 200
        assert b"MID must be" in response.data

    def test_wu_check_post_invalid_mid_too_long(self, client, app):
        _enable_wu_check(app)
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            response = client.post(
                "/wu-check", data={"mid": "123456789", "key_name": "production"}
            )
        assert response.status_code == 200
        assert b"MID must be" in response.data

    def test_wu_check_post_invalid_key_name(self, client, app):
        _enable_wu_check(app)
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            response = client.post(
                "/wu-check", data={"mid": "12345678", "key_name": "nonexistent"}
            )
        assert response.status_code == 200
        assert b"Invalid key selection" in response.data

    def test_wu_check_post_success(self, client, app):
        _enable_wu_check(app)
        api_response = [{"terminalId": "T001", "status": "active"}]
        mid = "12345678"
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            with rm.Mocker() as m:
                m.get(WU_TERMINALS_URL.format(mid=mid), json=api_response, status_code=200)
                response = client.post(
                    "/wu-check", data={"mid": mid, "key_name": "production"}
                )
        assert response.status_code == 200
        assert b"200" in response.data
        assert b"T001" in response.data

    def test_wu_check_post_api_error_response(self, client, app):
        _enable_wu_check(app)
        mid = "99999999"
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            with rm.Mocker() as m:
                m.get(
                    WU_TERMINALS_URL.format(mid=mid),
                    json={"error": "Merchant not found"},
                    status_code=404,
                )
                response = client.post(
                    "/wu-check", data={"mid": mid, "key_name": "production"}
                )
        assert response.status_code == 200
        assert b"404" in response.data
        assert b"Merchant not found" in response.data

    def test_wu_check_post_timeout(self, client, app):
        _enable_wu_check(app)
        mid = "12345678"
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            with rm.Mocker() as m:
                m.get(
                    WU_TERMINALS_URL.format(mid=mid),
                    exc=requests.exceptions.Timeout,
                )
                response = client.post(
                    "/wu-check", data={"mid": mid, "key_name": "production"}
                )
        assert response.status_code == 200
        assert b"timed out" in response.data

    def test_wu_check_api_key_not_in_response(self, client, app):
        """Ensure the actual API key value is never leaked in the response."""
        _enable_wu_check(app)
        mid = "12345678"
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            with rm.Mocker() as m:
                m.get(
                    WU_TERMINALS_URL.format(mid=mid),
                    json={"status": "ok"},
                    status_code=200,
                )
                response = client.post(
                    "/wu-check", data={"mid": mid, "key_name": "production"}
                )
        assert b"prod-key-123" not in response.data
        assert b"sandbox-key-456" not in response.data

    def test_wu_check_post_as_session_user_returns_404(self, client, app):
        _enable_wu_check(app)
        with client.session_transaction() as sess:
            sess["user_id"] = 1
        with patch("app.routes.wu_check._load_wu_keys", return_value=MOCK_KEYS):
            response = client.post(
                "/wu-check", data={"mid": "12345678", "key_name": "production"}
            )
        assert response.status_code == 404
