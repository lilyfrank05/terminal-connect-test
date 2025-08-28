import pytest
import json
from app.models import User, UserConfig, db


class TestConfigSharing:
    
    def test_share_config_success(self, client, test_users):
        """Test successful config sharing between users."""
        # Log in as first user and create a config
        login_response = client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        assert login_response.status_code == 302
        
        # Create a config for user1
        client.post('/config', data={
            'config_name': 'Test Config',
            'environment': 'sandbox',
            'mid': 'TEST_MID_123',
            'tid': 'TEST_TID_456',
            'api_key': 'test_api_key_123',
            'postback_url': 'https://example.com/webhook',
            'postback_delay': '5'
        })
        
        # Get the created config and share it
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='Test Config').first()
            assert config is not None
            config_id = config.id
        
        # Share the config with user2
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'user2@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'shared successfully' in data['message']
        
        # Verify the config was copied to user2
        with client.application.app_context():
            user2 = User.query.filter_by(email='user2@example.com').first()
            shared_config = UserConfig.query.filter_by(
                user_id=user2.id, 
                name='Test Config',
                mid='TEST_MID_123',
                tid='TEST_TID_456'
            ).first()
            
            assert shared_config is not None
            assert shared_config.api_key == 'test_api_key_123'
            assert shared_config.postback_url == 'https://example.com/webhook?delay=5'
            assert shared_config.postback_delay == 5
    
    def test_share_config_with_name_conflict(self, client, test_users):
        """Test config sharing when target user already has config with same name."""
        # Log in as user1 and create a config
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'My Config',
            'environment': 'production',
            'mid': 'MID_001',
            'tid': 'TID_001',
            'api_key': 'api_key_001'
        })
        
        # Log in as user2 and create a config with same name
        client.post('/user/logout')
        client.post('/user/login', data={
            'email': 'user2@example.com',
            'password': 'password2'
        })
        
        client.post('/config', data={
            'config_name': 'My Config',
            'environment': 'sandbox',
            'mid': 'MID_002',
            'tid': 'TID_002',
            'api_key': 'api_key_002'
        })
        
        # Switch back to user1 and share the config
        client.post('/user/logout')
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='My Config', mid='MID_001').first()
            config_id = config.id
        
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'user2@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify the shared config has "copy" appended to name
        with client.application.app_context():
            user2 = User.query.filter_by(email='user2@example.com').first()
            shared_config = UserConfig.query.filter_by(
                user_id=user2.id, 
                name='My Config copy'
            ).first()
            
            assert shared_config is not None
            assert shared_config.mid == 'MID_001'
    
    def test_share_config_user_not_exist(self, client, test_users):
        """Test sharing config with non-existent user email."""
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'Test Config',
            'environment': 'sandbox',
            'mid': 'TEST_MID',
            'tid': 'TEST_TID',
            'api_key': 'test_api_key'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='Test Config').first()
            config_id = config.id
        
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'nonexistent@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'does not exist' in data['error']
    
    def test_share_config_user_not_active(self, client, test_users):
        """Test sharing config with inactive user."""
        # Make user2 inactive
        with client.application.app_context():
            user2 = User.query.filter_by(email='user2@example.com').first()
            user2.is_active = False
            db.session.commit()
        
        # Login as user1 and create config
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'Test Config',
            'environment': 'sandbox',
            'mid': 'TEST_MID',
            'tid': 'TEST_TID',
            'api_key': 'test_api_key'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='Test Config').first()
            config_id = config.id
        
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'user2@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not activated' in data['error']
    
    def test_share_config_duplicate_config(self, client, test_users):
        """Test sharing config when target user already has same config."""
        # Create same config for both users
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'Shared Config',
            'environment': 'production',
            'mid': 'SAME_MID',
            'tid': 'SAME_TID',
            'api_key': 'api_key_1'
        })
        
        # Switch to user2 and create identical config
        client.post('/user/logout')
        client.post('/user/login', data={
            'email': 'user2@example.com',
            'password': 'password2'
        })
        
        client.post('/config', data={
            'config_name': 'Different Name',
            'environment': 'production',
            'mid': 'SAME_MID',  # Same MID and TID
            'tid': 'SAME_TID',
            'api_key': 'api_key_2'
        })
        
        # Try to share from user1 to user2
        client.post('/user/logout')
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='Shared Config').first()
            config_id = config.id
        
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'user2@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'already has this configuration' in data['error']
    
    def test_share_config_unauthorized_access(self, client, test_users):
        """Test trying to share another user's config."""
        # Create config as user1
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'User1 Config',
            'environment': 'sandbox',
            'mid': 'USER1_MID',
            'tid': 'USER1_TID',
            'api_key': 'user1_api_key'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='User1 Config').first()
            config_id = config.id
        
        # Switch to user2 and try to share user1's config
        client.post('/user/logout')
        client.post('/user/login', data={
            'email': 'user2@example.com',
            'password': 'password2'
        })
        
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'user1@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Unauthorized' in data['error']
    
    def test_share_config_to_self(self, client, test_users):
        """Test preventing sharing config to self."""
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'My Config',
            'environment': 'sandbox',
            'mid': 'MY_MID',
            'tid': 'MY_TID',
            'api_key': 'my_api_key'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='My Config').first()
            config_id = config.id
        
        response = client.post(f'/config/share/{config_id}', 
                             json={'email': 'user1@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Cannot share config with yourself' in data['error']
    
    def test_share_config_missing_email(self, client, test_users):
        """Test sharing config without providing email."""
        client.post('/user/login', data={
            'email': 'user1@example.com',
            'password': 'password1'
        })
        
        client.post('/config', data={
            'config_name': 'Test Config',
            'environment': 'sandbox',
            'mid': 'TEST_MID',
            'tid': 'TEST_TID',
            'api_key': 'test_api_key'
        })
        
        with client.application.app_context():
            config = UserConfig.query.filter_by(name='Test Config').first()
            config_id = config.id
        
        response = client.post(f'/config/share/{config_id}', 
                             json={},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Email is required' in data['error']
    
    def test_share_config_unauthenticated(self, client, test_users):
        """Test sharing config without authentication."""
        response = client.post('/config/share/1', 
                             json={'email': 'user2@example.com'},
                             content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Authentication required' in data['error']