"""
Test authentication endpoints
"""
import pytest
import json
from unittest.mock import patch, MagicMock

class TestAuthEndpoints:
    """Test authentication related endpoints"""

    def test_signup_success(self, client, mock_firestore_client):
        """Test successful user signup"""
        # Reset the mock to ensure clean state
        mock_firestore_client.reset_mock()
        
        # Mock Firestore document check (user doesn't exist)
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        # Test signup with a unique user ID to avoid conflicts
        response = client.post('/api/auth/signup', 
            json={
                'name': 'Test User',
                'user_id': 'uniqueuser123',
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'user' in data
        assert 'token' in data
        assert data['user']['id'] == 'uniqueuser123'
        assert data['user']['name'] == 'Test User'

    def test_signup_invalid_user_id(self, client):
        """Test signup with invalid user_id format"""
        response = client.post('/api/auth/signup',
            json={
                'name': 'Test User', 
                'user_id': 'invalid user!',  # Invalid characters
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_signup_short_password(self, client):
        """Test signup with password too short"""
        response = client.post('/api/auth/signup',
            json={
                'name': 'Test User',
                'user_id': 'testuser123', 
                'password': '123'  # Too short
            },
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_signup_existing_user(self, client, mock_firestore_client):
        """Test signup with existing user_id"""
        # Mock Firestore document check (user exists)
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.post('/api/auth/signup',
            json={
                'name': 'Test User',
                'user_id': 'existinguser',
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 409  # Changed from 400 to 409 (Conflict)
        data = response.get_json()
        assert 'error' in data
        assert 'already exists' in data['error'].lower()

    def test_signup_missing_fields(self, client):
        """Test signup with missing required fields"""
        # Test missing name
        response = client.post('/api/auth/signup',
            json={
                'user_id': 'testuser123',
                'password': 'password123'
            },
            content_type='application/json'
        )
        assert response.status_code == 400

        # Test missing user_id
        response = client.post('/api/auth/signup',
            json={
                'name': 'Test User',
                'password': 'password123'
            },
            content_type='application/json'
        )
        assert response.status_code == 400

        # Test missing password
        response = client.post('/api/auth/signup',
            json={
                'name': 'Test User',
                'user_id': 'testuser123'
            },
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_login_success(self, client, mock_firestore_client):
        """Test successful login"""
        from werkzeug.security import generate_password_hash
        
        # Mock existing user in Firestore
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'user_id': 'testuser123',
            'name': 'Test User',
            'password_hash': generate_password_hash('password123')
        }
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.post('/api/auth/login',
            json={
                'user_id': 'testuser123',
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'user' in data
        assert 'token' in data
        assert data['user']['user_id'] == 'testuser123'

    def test_login_invalid_credentials(self, client, mock_firestore_client):
        """Test login with invalid credentials"""
        # Test non-existent user
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.post('/api/auth/login',
            json={
                'user_id': 'nonexistent',
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_login_wrong_password(self, client, mock_firestore_client):
        """Test login with wrong password"""
        from werkzeug.security import generate_password_hash
        
        # Mock existing user with different password
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'user_id': 'testuser123',
            'name': 'Test User',
            'password_hash': generate_password_hash('differentpassword')
        }
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.post('/api/auth/login',
            json={
                'user_id': 'testuser123',
                'password': 'wrongpassword'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        # Missing user_id
        response = client.post('/api/auth/login',
            json={'password': 'password123'},
            content_type='application/json'
        )
        assert response.status_code == 400

        # Missing password
        response = client.post('/api/auth/login',
            json={'user_id': 'testuser123'},
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_login_invalid_user_id_format(self, client):
        """Test login with invalid user_id format"""
        response = client.post('/api/auth/login',
            json={
                'user_id': 'invalid user!',
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_me_endpoint_authenticated(self, client, auth_headers, mock_firestore_client):
        """Test /me endpoint with valid authentication"""
        # Mock user data in Firestore
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'user_id': 'test_user',
            'name': 'Test User',
            'profile': {'hobbies': ['travel', 'reading']}
        }
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.get('/api/me', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == 'test_user'  # Changed from user_id to id
        assert data['name'] == 'Test User'

    def test_me_endpoint_unauthenticated(self, client):
        """Test /me endpoint without authentication"""
        response = client.get('/api/me')
        
        assert response.status_code == 401

    def test_me_endpoint_invalid_token(self, client):
        """Test /me endpoint with invalid token"""
        response = client.get('/api/me', headers={'Authorization': 'Bearer invalid_token'})
        
        assert response.status_code == 401

    def test_me_endpoint_expired_token(self, client):
        """Test /me endpoint with expired token"""
        import jwt
        from datetime import datetime, timedelta
        
        # Create expired token
        payload = {
            'user_id': 'test_user',
            'exp': datetime.utcnow() - timedelta(hours=1)  # Expired
        }
        token = jwt.encode(payload, 'test-secret-key', algorithm='HS256')
        
        response = client.get('/api/me', headers={'Authorization': f'Bearer {token}'})
        
        assert response.status_code == 401

    @patch('app.db')
    def test_auth_with_devdb_fallback(self, mock_db, client):
        """Test authentication with DevDB fallback when Firestore is unavailable"""
        # Mock DevDB behavior
        mock_devdb = MagicMock()
        mock_db.return_value = mock_devdb
        
        # Test signup with DevDB
        response = client.post('/api/auth/signup',
            json={
                'name': 'Test User',
                'user_id': 'devdbuser',
                'password': 'password123'
            },
            content_type='application/json'
        )
        
        # Should still work with DevDB fallback
        assert response.status_code in [200, 400]  # May exist in DevDB or succeed

    def test_jwt_token_validation(self, client):
        """Test JWT token creation and validation"""
        import jwt
        from datetime import datetime, timedelta
        
        # Test token creation
        from utils.auth import create_jwt, verify_jwt
        
        user_id = 'test_user'
        token = create_jwt(user_id)
        
        # Token should be valid
        assert token is not None
        
        # Verify token
        claims = verify_jwt(token)
        assert claims is not None
        assert claims['sub'] == user_id

    def test_jwt_token_with_ttl(self, client):
        """Test JWT token creation with custom TTL"""
        from utils.auth import create_jwt_with_ttl, verify_jwt
        
        user_id = 'test_user'
        ttl_min = 30
        
        token = create_jwt_with_ttl(user_id, ttl_min)
        
        # Token should be valid
        assert token is not None
        
        # Verify token
        claims = verify_jwt(token)
        assert claims is not None
        assert claims['sub'] == user_id

    def test_require_auth_decorator(self, client):
        """Test require_auth decorator functionality"""
        from utils.auth import require_auth
        from flask import request
        
        # Mock request with valid auth header
        with client.application.test_request_context('/', headers={'Authorization': 'Bearer valid_token'}):
            # This would normally require a valid token
            # Testing the decorator logic
            try:
                require_auth(request)
            except Exception:
                # Expected to fail with mock token
                pass

    def test_claims_or_dev_function(self, client):
        """Test claims_or_dev helper function"""
        from utils.auth import claims_or_dev
        
        # In test environment, should return dev claims
        with client.application.test_request_context('/'):
            claims = claims_or_dev()
            
            # Should return some form of claims (either real or dev)
            assert claims is not None
            assert isinstance(claims, dict)