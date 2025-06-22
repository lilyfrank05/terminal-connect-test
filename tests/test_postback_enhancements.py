import pytest
import json
from app.models import User, UserPostback
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


def create_test_user(client, email="user@test.com", password="userpass"):
    """Creates a test user for testing."""
    with client.application.app_context():
        if User.query.filter_by(email=email).first():
            return
        user = User(email=email, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def create_test_postback_data():
    """Creates sample postback data for testing."""
    return {
        "intentId": "test-intent-123",
        "transactionId": "test-txn-456", 
        "transactionType": "sale",
        "terminalId": "test-terminal-789",
        "merchantReference": "ref-123",
        "status": "success",
        "amount": "10.00"
    }


# --- Test Classes ---

class TestPostbackEnhancements:
    """Tests for enhanced postback functionality including search and column preferences"""

    def test_authenticated_user_postback_storage(self, client):
        """Test that authenticated users get postbacks stored in database"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        postback_data = create_test_postback_data()
        response = client.post("/postback", json=postback_data)
        assert response.status_code == 200
        
        # Check database storage
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").first()
            postback = UserPostback.query.filter_by(user_id=user.id).first()
            assert postback is not None
            assert postback.intent_id == "test-intent-123"
            assert postback.transaction_id == "test-txn-456"
            assert postback.transaction_type == "sale"

    def test_guest_user_postback_storage(self, client):
        """Test that guest users get postbacks stored in files"""
        guest_login(client)
        
        postback_data = create_test_postback_data()
        response = client.post("/postback", json=postback_data)
        assert response.status_code == 200
        
        # Check postbacks page shows the data
        response = client.get("/postbacks")
        assert b"test-intent-123" in response.data
        assert b"test-terminal-789" in response.data

    def test_intent_id_required_for_authenticated_users(self, client):
        """Test that intent_id is required and has a default fallback"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        # Send postback without intentId
        postback_data = {
            "transactionType": "sale",
            "terminalId": "test-terminal",
            "status": "success"
        }
        response = client.post("/postback", json=postback_data)
        assert response.status_code == 200
        
        # Check fallback value was used
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").first()
            postback = UserPostback.query.filter_by(user_id=user.id).first()
            assert postback is not None
            assert postback.intent_id == "unknown_intent"

    def test_transaction_id_nullable(self, client):
        """Test that transaction_id can be null"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        # Send postback without transactionId
        postback_data = {
            "intentId": "test-intent-123",
            "transactionType": "sale",
            "status": "success"
        }
        response = client.post("/postback", json=postback_data)
        assert response.status_code == 200
        
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").first()
            postback = UserPostback.query.filter_by(user_id=user.id).first()
            assert postback is not None
            assert postback.transaction_id is None

    def test_time_formatting_without_microseconds(self, client):
        """Test that time display doesn't include microseconds"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        postback_data = create_test_postback_data()
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        response_data = response.data.decode()
        
        # Check that time format doesn't include decimal points (microseconds)
        assert "T" in response_data  # ISO format
        # Should not contain decimal point for microseconds
        import re
        time_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+'
        assert not re.search(time_pattern, response_data)


class TestPostbackSearch:
    """Tests for postback search functionality"""

    def setup_search_test_data(self, client):
        """Helper to set up test data for search tests"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        # Create multiple postbacks with different data
        test_postbacks = [
            {
                "intentId": "intent-alpha-123",
                "transactionId": "txn-alpha-456",
                "terminalId": "terminal-alpha-789",
                "merchantReference": "ref-alpha",
                "transactionType": "sale",
                "status": "success"
            },
            {
                "intentId": "intent-beta-456", 
                "transactionId": "txn-beta-789",
                "terminalId": "terminal-beta-012",
                "merchantReference": "ref-beta",
                "transactionType": "refund",
                "status": "success"
            },
            {
                "intentId": "intent-gamma-789",
                "transactionId": None,  # Test nullable transaction_id
                "terminalId": "terminal-gamma-345",
                "merchantReference": "ref-gamma",
                "transactionType": "reversal",
                "status": "failed"
            }
        ]
        
        for postback_data in test_postbacks:
            client.post("/postback", json=postback_data)

    def test_search_by_intent_id(self, client):
        """Test searching by intent ID"""
        self.setup_search_test_data(client)
        
        # Search for alpha intent
        response = client.get("/postbacks?search=intent-alpha")
        assert response.status_code == 200
        assert b"intent-alpha-123" in response.data
        assert b"intent-beta-456" not in response.data
        assert b"intent-gamma-789" not in response.data

    def test_search_by_transaction_id(self, client):
        """Test searching by transaction ID"""
        self.setup_search_test_data(client)
        
        # Search for beta transaction
        response = client.get("/postbacks?search=txn-beta")
        assert response.status_code == 200
        assert b"txn-beta-789" in response.data
        assert b"txn-alpha-456" not in response.data

    def test_search_by_terminal_id(self, client):
        """Test searching by terminal ID"""
        self.setup_search_test_data(client)
        
        # Search for gamma terminal
        response = client.get("/postbacks?search=terminal-gamma")
        assert response.status_code == 200
        assert b"terminal-gamma-345" in response.data
        assert b"terminal-alpha-789" not in response.data
        assert b"terminal-beta-012" not in response.data

    def test_search_case_insensitive(self, client):
        """Test that search is case insensitive"""
        self.setup_search_test_data(client)
        
        # Search with different cases
        response1 = client.get("/postbacks?search=INTENT-ALPHA")
        response2 = client.get("/postbacks?search=intent-alpha")
        response3 = client.get("/postbacks?search=Intent-Alpha")
        
        assert response1.status_code == 200
        assert response2.status_code == 200 
        assert response3.status_code == 200
        assert b"intent-alpha-123" in response1.data
        assert b"intent-alpha-123" in response2.data
        assert b"intent-alpha-123" in response3.data

    def test_search_partial_match(self, client):
        """Test that search works with partial matches"""
        self.setup_search_test_data(client)
        
        # Search for partial string
        response = client.get("/postbacks?search=alpha")
        assert response.status_code == 200
        assert b"intent-alpha-123" in response.data
        assert b"txn-alpha-456" in response.data
        assert b"terminal-alpha-789" in response.data

    def test_search_with_pagination(self, client):
        """Test that search works with pagination parameters"""
        self.setup_search_test_data(client)
        
        # Search with pagination
        response = client.get("/postbacks?search=alpha&page=1&per_page=20")
        assert response.status_code == 200
        assert b"intent-alpha-123" in response.data
        
        # Check that search parameter is preserved (don't check for specific pagination links since they may not exist with limited data)
        response_data = response.data.decode()
        assert "alpha" in response_data

    def test_guest_search_functionality(self, client):
        """Test search functionality for guest users"""
        guest_login(client)
        
        # Create guest postbacks
        guest_postbacks = [
            {
                "intentId": "guest-intent-123",
                "transactionId": "guest-txn-456", 
                "terminalId": "guest-terminal-789",
                "status": "success"
            },
            {
                "intentId": "other-intent-999",
                "terminalId": "other-terminal-888",
                "status": "failed"
            }
        ]
        
        for postback_data in guest_postbacks:
            client.post("/postback", json=postback_data)
        
        # Test search
        response = client.get("/postbacks?search=guest")
        assert response.status_code == 200
        assert b"guest-intent-123" in response.data
        assert b"other-intent-999" not in response.data

    def test_search_no_results(self, client):
        """Test search with no matching results"""
        self.setup_search_test_data(client)
        
        response = client.get("/postbacks?search=nonexistent")
        assert response.status_code == 200
        assert b"No postback messages received yet" in response.data

    def test_empty_search_shows_all(self, client):
        """Test that empty search shows all postbacks"""
        self.setup_search_test_data(client)
        
        response = client.get("/postbacks?search=")
        assert response.status_code == 200
        assert b"intent-alpha-123" in response.data
        assert b"intent-beta-456" in response.data
        assert b"intent-gamma-789" in response.data


class TestColumnPreferences:
    """Tests for column visibility preferences"""

    def test_save_column_preferences_authenticated_user(self, client):
        """Test saving column preferences for authenticated users"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        preferences = {
            "time": True,
            "intent_id": True,
            "transaction_id": False,
            "status": True,
            "terminal_id": False,
            "transaction_type": True,
            "reference": True
        }
        
        response = client.post(
            "/postbacks/column-preferences",
            json=preferences,
            content_type="application/json"
        )
        assert response.status_code == 200
        
        # Check preferences were saved
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").first()
            assert user.postback_column_preferences is not None
            saved_prefs = json.loads(user.postback_column_preferences)
            assert saved_prefs["intent_id"] is True
            assert saved_prefs["transaction_id"] is False

    def test_load_column_preferences_authenticated_user(self, client):
        """Test loading column preferences for authenticated users"""
        create_test_user(client)
        
        # Set preferences directly in database
        with client.application.app_context():
            user = User.query.filter_by(email="user@test.com").first()
            preferences = {
                "time": False,
                "intent_id": True,
                "transaction_id": True,
                "status": False,
                "terminal_id": True,
                "transaction_type": False,
                "reference": True
            }
            user.postback_column_preferences = json.dumps(preferences)
            db.session.commit()
        
        login(client, "user@test.com", "userpass")
        response = client.get("/postbacks")
        assert response.status_code == 200
        
        # Check that preferences are applied in the template
        assert b'data-column="time"' in response.data
        assert b'data-column="intent_id" checked' in response.data
        assert b'data-column="transaction_id" checked' in response.data

    def test_default_column_preferences(self, client):
        """Test default column preferences for new users"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        response = client.get("/postbacks")
        assert response.status_code == 200
        
        # Check default preferences (intent_id and transaction_id hidden by default)
        assert b'data-column="time" checked' in response.data
        assert b'data-column="status" checked' in response.data
        assert b'data-column="intent_id"' in response.data
        assert b'data-column="intent_id" checked' not in response.data  # Should be unchecked
        assert b'data-column="transaction_id"' in response.data
        assert b'data-column="transaction_id" checked' not in response.data  # Should be unchecked

    def test_guest_users_no_column_preferences(self, client):
        """Test that guest users don't have column preference controls"""
        guest_login(client)
        
        response = client.get("/postbacks")
        assert response.status_code == 200
        
        # Should not have column toggle controls
        assert b'Show columns:' not in response.data
        assert b'column-toggle' not in response.data

    def test_column_preferences_unauthorized_request(self, client):
        """Test that unauthenticated users cannot save column preferences"""
        preferences = {"time": True, "status": False}
        
        response = client.post(
            "/postbacks/column-preferences",
            json=preferences,
            content_type="application/json"
        )
        assert response.status_code == 401
        
        response_data = json.loads(response.data)
        assert response_data["error"] == "Authentication required"

    def test_column_preferences_invalid_json(self, client):
        """Test error handling for invalid JSON in column preferences"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        response = client.post(
            "/postbacks/column-preferences",
            data="invalid json",
            content_type="application/json"
        )
        assert response.status_code == 500

    def test_details_column_always_visible(self, client):
        """Test that Details column is always visible and not in preferences"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        # Create a postback to ensure the table is rendered
        postback_data = create_test_postback_data()
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        assert response.status_code == 200
        
        # Details column should always be visible (no hidden attribute)
        assert b'column-details' in response.data
        assert b'column-details" hidden' not in response.data
        
        # Details should not have a toggle control
        assert b'data-column="details"' not in response.data


class TestPostbackColumns:
    """Tests for the new postback columns display"""

    def test_column_order(self, client):
        """Test that columns are in the correct order"""
        create_test_user(client) 
        login(client, "user@test.com", "userpass")
        
        # Create a postback
        postback_data = create_test_postback_data()
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        response_text = response.data.decode()
        
        # Check column header order
        time_pos = response_text.find('>Time</th>')
        intent_pos = response_text.find('>Intent ID</th>')
        transaction_pos = response_text.find('>Transaction ID</th>')
        status_pos = response_text.find('>Status</th>')
        details_pos = response_text.find('>Details</th>')
        
        # Verify order: Time < Intent ID < Transaction ID < Status < ... < Details
        assert time_pos < intent_pos < transaction_pos < status_pos < details_pos

    def test_intent_id_display(self, client):
        """Test that intent ID is displayed correctly"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        postback_data = create_test_postback_data()
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        assert b"test-intent-123" in response.data

    def test_transaction_id_display_with_value(self, client):
        """Test transaction ID display when value exists"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        postback_data = create_test_postback_data()
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        assert b"test-txn-456" in response.data

    def test_transaction_id_display_na_when_missing(self, client):
        """Test transaction ID shows N/A when missing"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        postback_data = {
            "intentId": "test-intent-123",
            "terminalId": "test-terminal",
            "status": "success"
            # No transactionId
        }
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        # Should show N/A for missing transaction ID
        assert b"N/A" in response.data

    def test_terminal_id_display(self, client):
        """Test that terminal ID is displayed correctly"""
        create_test_user(client)
        login(client, "user@test.com", "userpass")
        
        postback_data = create_test_postback_data()
        client.post("/postback", json=postback_data)
        
        response = client.get("/postbacks")
        assert b"test-terminal-789" in response.data