import pytest
import requests_mock
from unittest.mock import patch
from app.models import User, Invite, UserConfig, UserPostback
from app import db


# --- Helper Functions ---


def login(client, email, password):
    """Logs in a user and returns the response."""
    return client.post(
        "/user/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def guest_login(client):
    """Logs in a guest and returns the response."""
    return client.get("/user/guest-login", follow_redirects=True)


def create_admin_user(client):
    """Creates a default admin user for testing."""
    with client.application.app_context():
        if User.query.filter_by(email="admin@test.com").first():
            return
        user = User(email="admin@test.com", role="admin")
        user.set_password("adminpass")
        db.session.add(user)
        db.session.commit()


def create_regular_user(client):
    """Creates a default regular user for testing."""
    with client.application.app_context():
        if User.query.filter_by(email="user@test.com").first():
            return
        user = User(email="user@test.com", role="user")
        user.set_password("userpass")
        db.session.add(user)
        db.session.commit()


# --- Test Cases ---


class TestAuth:
    """Tests for Authentication and User Management"""

    def test_login_page_loads(self, client):
        response = client.get("/user/login")
        assert response.status_code == 200
        assert b"Login" in response.data

    def test_version_in_footer(self, client):
        """Test that version number appears in the footer of pages"""
        import os
        
        # Read the actual version from the VERSION file
        try:
            version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
            with open(version_file, "r") as f:
                expected_version = f.read().strip()
        except (FileNotFoundError, IOError):
            expected_version = "unknown"
        
        response = client.get("/user/login")
        assert response.status_code == 200
        assert b"Terminal Connect Test v" in response.data
        # Check that the actual version from file appears in the response
        expected_footer = f"Terminal Connect Test v{expected_version}".encode()
        assert expected_footer in response.data

    def test_guest_login(self, client):
        response = guest_login(client)
        assert response.status_code == 200
        assert b"Configuration" in response.data  # Redirects to config
        with client.session_transaction() as sess:
            assert sess["is_guest"] is True

    @patch("app.routes.user.send_email")
    def test_admin_can_invite(self, mock_send_email, client):
        create_admin_user(client)
        login(client, "admin@test.com", "adminpass")
        response = client.post(
            "/user/admin/invites/send",
            data={"email": "newuser@test.com", "role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Invitation sent to newuser@test.com" in response.data
        mock_send_email.assert_called_once()
        with client.application.app_context():
            assert Invite.query.filter_by(email="newuser@test.com").count() == 1

    def test_user_cannot_invite(self, client):
        create_regular_user(client)
        login(client, "user@test.com", "userpass")
        response = client.get("/user/admin/invites", follow_redirects=True)
        assert response.status_code == 200  # Redirects to login
        assert b"Admin access required" in response.data

    def test_register_page_invalid_token(self, client):
        response = client.get("/user/register?token=invalid", follow_redirects=True)
        assert b"Invalid or expired invite token" in response.data

    @patch("app.routes.user.send_email")
    def test_full_registration_flow(self, mock_send_email, client):
        # 1. Admin sends invite
        create_admin_user(client)
        login(client, "admin@test.com", "adminpass")
        client.post(
            "/user/admin/invites/send",
            data={"email": "registerme@test.com", "role": "user"},
        )
        client.get("/user/logout")  # Admin logs out

        # 2. New user registers with token
        with client.application.app_context():
            invite = Invite.query.filter_by(email="registerme@test.com").first()
            assert invite is not None
            assert invite.status == "pending"
        response = client.post(
            "/user/register",
            data={
                "email": "registerme@test.com",
                "password": "password123",
                "token": invite.token,
            },
            follow_redirects=True,
        )
        assert b"Registration successful" in response.data

        # 3. New user logs in
        response = login(client, "registerme@test.com", "password123")
        assert b"Configuration" in response.data  # Redirected to config page

    def test_login_logout(self, client):
        create_regular_user(client)
        login_res = login(client, "user@test.com", "userpass")
        assert b"Configuration" in login_res.data
        logout_res = client.get("/user/logout", follow_redirects=True)
        assert b"You have been logged out" in logout_res.data

    def test_login_invalid_credentials(self, client):
        create_regular_user(client)
        response = login(client, "user@test.com", "wrongpassword")
        assert b"Invalid credentials" in response.data

    def test_login_redirects_to_config_page(self, client):
        """Test that successful login redirects user to configuration page"""
        create_regular_user(client)
        response = login(client, "user@test.com", "userpass")
        assert response.status_code == 200
        assert b"Configuration" in response.data
        # Verify we're actually on the config page, not profile
        assert b"Environment" in response.data  # Config form element
        assert b"Merchant ID" in response.data  # Config form element

    @patch("app.routes.user.send_email")
    def test_removed_user_can_be_invited_again(self, mock_send_email, client):
        """Test that a removed user can be invited again"""
        # Create admin user and login
        create_admin_user(client)
        login(client, "admin@test.com", "adminpass")

        # Send initial invite
        response = client.post(
            "/user/admin/invites/send", data={"email": "test@test.com", "role": "user"}
        )
        assert response.status_code == 302

        # Get the invite token
        with client.application.app_context():
            invite = Invite.query.filter_by(email="test@test.com").first()
            assert invite is not None
            assert invite.status == "pending"

        # Register the user
        client.get("/user/logout")  # Logout admin first
        response = client.post(
            "/user/register",
            data={
                "email": "test@test.com",
                "password": "password",
                "token": invite.token,
            },
            follow_redirects=True,
        )
        assert b"Registration successful" in response.data

        # Verify user was created and invite was marked as accepted
        with client.application.app_context():
            user = User.query.filter_by(email="test@test.com").first()
            assert user is not None
            invite = Invite.query.filter_by(email="test@test.com").first()
            assert invite.status == "accepted"

        # Admin logs back in and removes the user
        login(client, "admin@test.com", "adminpass")
        response = client.post("/user/admin/users", data={"user_id": "test@test.com"})
        assert response.status_code == 302

        # Verify user was deleted
        with client.application.app_context():
            user = User.query.filter_by(email="test@test.com").first()
            assert user is None

        # Invite should still exist but be marked as accepted
        with client.application.app_context():
            invite = Invite.query.filter_by(email="test@test.com").first()
            assert invite is not None
            assert invite.status == "accepted"

        # Reset the mock to track new calls
        mock_send_email.reset_mock()

        # Now try to invite the same email again (should work)
        response = client.post(
            "/user/admin/invites/send", data={"email": "test@test.com", "role": "user"}
        )
        assert response.status_code == 302

        # Verify email was sent
        mock_send_email.assert_called_once()

        # Verify a new invite was created and can be used again
        with client.application.app_context():
            invites = Invite.query.filter_by(email="test@test.com").all()
            assert (
                len(invites) == 2
            )  # Should have 2 invites now (old accepted + new pending)
            # Find the pending invite (should be the new one)
            pending_invites = [inv for inv in invites if inv.status == "pending"]
            accepted_invites = [inv for inv in invites if inv.status == "accepted"]
            assert len(pending_invites) == 1  # Should have exactly 1 pending invite
            assert len(accepted_invites) == 1  # Should have exactly 1 accepted invite
            new_invite = pending_invites[0]
            assert new_invite.token is not None  # Should have a token

        # User should be able to register again with the new invite
        client.get("/user/logout")  # Logout admin
        response = client.post(
            "/user/register",
            data={
                "email": "test@test.com",
                "password": "newpassword",
                "token": new_invite.token,
            },
            follow_redirects=True,
        )
        assert b"Registration successful" in response.data

        # Verify user was created again
        with client.application.app_context():
            user = User.query.filter_by(email="test@test.com").first()
            assert user is not None
            assert user.email == "test@test.com"


class TestConfig:
    """Tests for Configuration Management"""

    def test_config_page_loads_for_guest(self, client):
        guest_login(client)
        response = client.get("/config")
        assert response.status_code == 200
        assert b"Configuration" in response.data

    def test_config_page_loads_for_user(self, client):
        create_regular_user(client)
        login(client, "user@test.com", "userpass")
        response = client.get("/config")
        assert response.status_code == 200
        assert b"Configuration" in response.data

    def test_guest_config_update(self, client, mock_config):
        guest_login(client)
        client.post("/config", data=mock_config)
        with client.session_transaction() as sess:
            assert sess["MID"] == mock_config["mid"]
            assert sess["TID"] == mock_config["tid"]

    def test_user_config_save_and_load(self, client, mock_config):
        create_regular_user(client)
        login(client, "user@test.com", "userpass")

        # Save a new config
        save_data = mock_config.copy()
        save_data["config_name"] = "My Test Config"
        client.post("/config", data=save_data, follow_redirects=True)

        # Check it was saved
        with client.application.app_context():
            config = UserConfig.query.filter_by(name="My Test Config").first()
            assert config is not None
            user = User.query.filter_by(email="user@test.com").first()
            assert config.user_id == user.id

        # Load the config
        client.get(f"/config/load/{config.id}", follow_redirects=True)
        with client.session_transaction() as sess:
            assert sess["MID"] == mock_config["mid"]
            assert sess["active_config_id"] == config.id
            assert sess["TID"] == mock_config["tid"]

    def test_user_can_delete_config(self, client):
        create_regular_user(client)
        login(client, "user@test.com", "userpass")

        # Create a config to delete
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").one()
            config = UserConfig(
                user_id=user.id,
                name="to-delete",
                environment="sandbox",
                base_url="https://test.com",
                mid="123",
                tid="456",
                api_key="test-key",
            )
            db.session.add(config)
            db.session.commit()
            config_id = config.id

        # Delete it
        response = client.post(f"/config/delete/{config_id}")
        assert response.status_code == 302

        # Follow the redirect and check for the message
        redirect_response = client.get(response.location)
        assert b"Configuration &#39;to-delete&#39; deleted." in redirect_response.data
        with client.application.app_context():
            assert db.session.get(UserConfig, config_id) is None

    def test_user_cannot_delete_other_users_config(self, client):
        # Create two users and a config for the first one
        create_regular_user(client)
        with client.application.app_context():
            other_user = User(email="other@test.com", role="user")
            other_user.set_password("pass")
            db.session.add(other_user)
            db.session.commit()
            config = UserConfig(
                user_id=other_user.id,
                name="secret",
                environment="sandbox",
                base_url="https://test.com",
                mid="456",
                tid="789",
                api_key="secret-key",
            )
            db.session.add(config)
            db.session.commit()
            config_id = config.id

        # Log in as user1 and try to delete user2's config
        login(client, "user@test.com", "userpass")
        response = client.post(f"/config/delete/{config_id}", follow_redirects=True)
        assert response.status_code == 403

    def test_config_limit(self, client):
        create_regular_user(client)
        login(client, "user@test.com", "userpass")
        # Create 10 configs (the limit)
        for i in range(10):
            client.post(
                "/config",
                data={
                    "config_name": f"Config {i+1}",
                    "environment": "sandbox",
                    "mid": f"mid{i}",
                    "tid": f"tid{i}",
                    "api_key": f"key{i}",
                },
            )
        # Try to create 11th config
        response = client.post(
            "/config",
            data={
                "config_name": "Config 11",
                "environment": "sandbox",
                "mid": "mid11",
                "tid": "tid11",
                "api_key": "key11",
            },
            follow_redirects=True,
        )
        assert b"maximum of 10 saved configurations" in response.data


class TestPostbacks:
    """Tests for Postback Handling"""

    def test_postbacks_page_loads_for_guest(self, client):
        guest_login(client)
        response = client.get("/postbacks")
        assert response.status_code == 200
        assert b"Postback Messages" in response.data

    def test_guest_receives_postback(self, client, app):
        guest_login(client)
        client.post("/postback", json={"test": "data"})
        response = client.get("/postbacks")
        assert b"data" in response.data

    def test_user_receives_postback(self, client):
        create_regular_user(client)
        login(client, "user@test.com", "userpass")
        client.post("/postback", json={"test": "data"})
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").first()
            assert UserPostback.query.filter_by(user_id=user.id).count() == 1
        response = client.get("/postbacks")
        assert b"data" in response.data


class TestTransactions:
    """Tests for Sale, Refund, Reversal"""

    def test_sale_requires_config(self, client):
        guest_login(client)
        # No config set yet
        response = client.post("/sale", data={"amount": "10.00"}, follow_redirects=True)
        assert b"Please configure your settings first" in response.data

    def test_sale_success(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        guest_login(client)
        client.post("/config", data=mock_config)  # Set config
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/payment",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/sale",
                data={"amount": "10.00", "merchant_reference": "test-ref"},
                follow_redirects=True,
            )
            assert b"Successfully processed Intent ID:" in response.data

    def test_unlinked_refund_success(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        guest_login(client)
        client.post("/config", data=mock_config)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/unlinked-refund",
                data={"amount": "10.00", "merchant_reference": "test-ref"},
                follow_redirects=True,
            )
            assert b"Successfully processed Intent ID:" in response.data


class TestRefunds:
    """Tests for Unlinked and Linked Refunds"""

    def test_unlinked_refund_page_loads(self, client):
        guest_login(client)
        response = client.get("/unlinked-refund")
        assert response.status_code == 200
        assert b"Unlinked Refund" in response.data

    def test_unlinked_refund_validation_errors(self, client, mock_config):
        guest_login(client)
        client.post("/config", data=mock_config)

        # Missing amount
        response = client.post(
            "/unlinked-refund", data={"merchant_reference": "test-ref"}
        )
        assert response.status_code == 302
        redirect_response = client.get(response.location)
        assert b"Amount must be greater than zero" in redirect_response.data

        # Invalid amount
        response = client.post(
            "/unlinked-refund", data={"amount": "abc", "merchant_reference": "test-ref"}
        )
        assert response.status_code == 302
        redirect_response = client.get(response.location)
        assert b"Invalid amount format" in redirect_response.data

        # Missing merchant reference
        response = client.post("/unlinked-refund", data={"amount": "10.00"})
        assert response.status_code == 302
        redirect_response = client.get(response.location)
        assert b"Merchant reference is required" in redirect_response.data

    def test_unlinked_refund_api_error(self, client, mock_config):
        guest_login(client)
        client.post("/config", data=mock_config)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json={"error": "API is down"},
                status_code=500,
            )
            response = client.post(
                "/unlinked-refund",
                data={"amount": "10.00", "merchant_reference": "test-ref"},
                follow_redirects=True,
            )
            assert b"Error creating refund intent" in response.data

    def test_linked_refund_page_loads(self, client):
        guest_login(client)
        response = client.get("/linked-refund")
        assert response.status_code == 200
        assert b"Linked Refund" in response.data

    def test_linked_refund_pinpad_success(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        guest_login(client)
        client.post("/config", data=mock_config)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/linked-refund",
                data={
                    "amount": "10.00",
                    "merchant_reference": "test-ref-linked",
                    "parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef",
                    "via_pinpad": "on",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_linked_refund_non_pinpad_success(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        """Test that non-WP TID linked refunds always process (no longer supports non-pinpad for non-WP TIDs)"""
        guest_login(client)
        client.post("/config", data=mock_config)
        parent_intent_id = "a1b2c3d4-e5f6-4890-a234-567890abcdef"

        with requests_mock.Mocker() as m:
            # Mock creating refund intent
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json=mock_intent_response,
            )
            # Mock processing the intent (now always called for non-WP TIDs)
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )

            response = client.post(
                "/linked-refund",
                data={
                    "amount": "10.00",
                    "merchant_reference": "test-ref-non-pinpad",
                    "parent_intent_id": parent_intent_id,
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_linked_refund_validation_errors(self, client, mock_config):
        guest_login(client)
        client.post("/config", data=mock_config)

        # Missing parent intent ID
        response = client.post(
            "/linked-refund",
            data={"amount": "10.00", "merchant_reference": "test-ref"},
            follow_redirects=True,
        )
        assert b"Original Sale Reference is required" in response.data

        # Invalid parent intent ID (not a UUID)
        response = client.post(
            "/linked-refund",
            data={
                "amount": "10.00",
                "merchant_reference": "test-ref",
                "parent_intent_id": "not-a-uuid",
            },
            follow_redirects=True,
        )
        assert b"Original Sale Reference must be a valid UUID v4" in response.data


class TestReversals:
    """Tests for Reversals"""

    def test_reversal_page_loads(self, client):
        guest_login(client)
        response = client.get("/reversal")
        assert response.status_code == 200
        assert b"Reversal" in response.data

    def test_reversal_pinpad_success(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        guest_login(client)
        client.post("/config", data=mock_config)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/reversal",
                data={
                    "merchant_reference": "test-ref-reversal",
                    "parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef",
                    "via_pinpad": "on",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_reversal_non_pinpad_success(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        """Test that non-WP TID reversals always process (no longer supports non-pinpad for non-WP TIDs)"""
        guest_login(client)
        client.post("/config", data=mock_config)
        parent_intent_id = "a1b2c3d4-e5f6-4890-a234-567890abcdef"

        with requests_mock.Mocker() as m:
            # Mock creating reversal intent
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
                json=mock_intent_response,
            )
            # Mock processing the intent (now always called for non-WP TIDs)
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )

            response = client.post(
                "/reversal",
                data={
                    "merchant_reference": "test-ref-non-pinpad",
                    "parent_intent_id": parent_intent_id,
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_reversal_validation_errors(self, client, mock_config):
        guest_login(client)
        client.post("/config", data=mock_config)

        # Missing merchant reference
        response = client.post(
            "/reversal",
            data={"parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef"},
            follow_redirects=True,
        )
        assert b"Merchant reference is required" in response.data

        # Missing parent intent ID
        response = client.post(
            "/reversal",
            data={"merchant_reference": "test-ref"},
            follow_redirects=True,
        )
        assert b"Original Sale Reference is required" in response.data


class TestChargeAnywhereTID:
    """Tests for Charge Anywhere TID functionality (TIDs starting with WP)"""
    
    def test_wp_tid_shows_pinpad_options_linked_refund(self, client, mock_config_wp):
        """Test that WP TIDs show pinpad options in linked refund form"""
        guest_login(client)
        client.post("/config", data=mock_config_wp)
        response = client.get("/linked-refund")
        assert response.status_code == 200
        assert b"Process via PINpad" in response.data
        assert b"via_pinpad" in response.data

    def test_wp_tid_shows_pinpad_options_reversal(self, client, mock_config_wp):
        """Test that WP TIDs show pinpad options in reversal form"""
        guest_login(client)
        client.post("/config", data=mock_config_wp)
        response = client.get("/reversal")
        assert response.status_code == 200
        assert b"Process via PINpad" in response.data
        assert b"via_pinpad" in response.data

    def test_non_wp_tid_hides_pinpad_options_linked_refund(self, client, mock_config):
        """Test that non-WP TIDs hide pinpad options in linked refund form"""
        guest_login(client)
        client.post("/config", data=mock_config)
        response = client.get("/linked-refund")
        assert response.status_code == 200
        assert b"Process via PINpad" not in response.data

    def test_non_wp_tid_hides_pinpad_options_reversal(self, client, mock_config):
        """Test that non-WP TIDs hide pinpad options in reversal form"""
        guest_login(client)
        client.post("/config", data=mock_config)
        response = client.get("/reversal")
        assert response.status_code == 200
        assert b"Process via PINpad" not in response.data
        assert b'type="checkbox"' not in response.data

    def test_wp_tid_linked_refund_via_pinpad_yes(
        self, client, mock_config_wp, mock_intent_response, mock_process_response
    ):
        """Test WP TID linked refund with via_pinpad=yes processes correctly"""
        guest_login(client)
        client.post("/config", data=mock_config_wp)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/linked-refund",
                data={
                    "amount": "10.00",
                    "merchant_reference": "test-ref-wp-pinpad",
                    "parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef",
                    "via_pinpad": "yes",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_wp_tid_linked_refund_via_pinpad_no(
        self, client, mock_config_wp, mock_intent_response
    ):
        """Test WP TID linked refund with via_pinpad=no creates intent without processing"""
        guest_login(client)
        client.post("/config", data=mock_config_wp)
        parent_intent_id = "a1b2c3d4-e5f6-4890-a234-567890abcdef"

        with requests_mock.Mocker() as m:
            # Mock getting transaction details
            m.get(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{parent_intent_id}",
                json={
                    "transactionDetails": {
                        "externalData": '{"gatewayReferenceNumber": "123", "originalAmount": 1000, "originalApprovalCode": "ABC", "originalTransactionType": "SALE", "hostMerchantId": "ext-mid", "hostTerminalId": "ext-tid"}'
                    }
                },
            )
            # Mock creating refund intent
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json=mock_intent_response,
            )

            response = client.post(
                "/linked-refund",
                data={
                    "amount": "10.00",
                    "merchant_reference": "test-ref-wp-no-pinpad",
                    "parent_intent_id": parent_intent_id,
                    "via_pinpad": "no",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully created refund Intent ID:" in redirect_response.data

    def test_wp_tid_reversal_via_pinpad_checked(
        self, client, mock_config_wp, mock_intent_response, mock_process_response
    ):
        """Test WP TID reversal with via_pinpad checked processes correctly"""
        guest_login(client)
        client.post("/config", data=mock_config_wp)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/reversal",
                data={
                    "merchant_reference": "test-ref-wp-reversal",
                    "parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef",
                    "via_pinpad": "yes",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_wp_tid_reversal_via_pinpad_unchecked(
        self, client, mock_config_wp, mock_intent_response
    ):
        """Test WP TID reversal with via_pinpad unchecked creates intent without processing"""
        guest_login(client)
        client.post("/config", data=mock_config_wp)
        parent_intent_id = "a1b2c3d4-e5f6-4890-a234-567890abcdef"

        with requests_mock.Mocker() as m:
            # Mock getting transaction details
            m.get(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{parent_intent_id}",
                json={
                    "transactionDetails": {
                        "externalData": '{"gatewayReferenceNumber": "123", "originalAmount": 1000, "originalApprovalCode": "ABC", "originalTransactionType": "SALE", "hostMerchantId": "ext-mid", "hostTerminalId": "ext-tid"}'
                    }
                },
            )
            # Mock creating reversal intent
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
                json=mock_intent_response,
            )

            response = client.post(
                "/reversal",
                data={
                    "merchant_reference": "test-ref-wp-no-pinpad",
                    "parent_intent_id": parent_intent_id,
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully created reversal Intent ID:" in redirect_response.data

    def test_non_wp_tid_linked_refund_always_processes(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        """Test that non-WP TID linked refunds always process regardless of form data"""
        guest_login(client)
        client.post("/config", data=mock_config)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/refund",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/linked-refund",
                data={
                    "amount": "10.00",
                    "merchant_reference": "test-ref-non-wp",
                    "parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data

    def test_non_wp_tid_reversal_always_processes(
        self, client, mock_config, mock_intent_response, mock_process_response
    ):
        """Test that non-WP TID reversals always process regardless of form data"""
        guest_login(client)
        client.post("/config", data=mock_config)
        with requests_mock.Mocker() as m:
            m.post(
                "https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/reversal",
                json=mock_intent_response,
            )
            m.post(
                f"https://api-terminal-gateway.tillvision.show/devices/merchant/test-mid/intent/{mock_intent_response['intentId']}/process",
                json=mock_process_response,
            )
            response = client.post(
                "/reversal",
                data={
                    "merchant_reference": "test-ref-non-wp",
                    "parent_intent_id": "a1b2c3d4-e5f6-4890-a234-567890abcdef",
                },
            )
            assert response.status_code == 302
            redirect_response = client.get(response.location)
            assert b"Successfully processed Intent ID:" in redirect_response.data
