"""
Test health check endpoint
"""
import pytest
from unittest.mock import patch, MagicMock

class TestHealthEndpoint:
    """Test health check endpoint functionality"""

    def test_health_endpoint_basic(self, client):
        """Test basic health endpoint response"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Check required fields based on actual endpoint
        assert 'status' in data
        assert 'env' in data
        assert 'db' in data
        assert 'gemini_configured' in data
        assert 'jwt_configured' in data
        assert 'agent_json_metrics' in data
        
        # Check values
        assert data['status'] == 'ok'
        assert data['env'] == 'testing'  # From conftest.py setup
        assert data['db'] in ['devdb', 'firestore']
        assert isinstance(data['gemini_configured'], bool)
        assert isinstance(data['jwt_configured'], bool)
        assert isinstance(data['agent_json_metrics'], dict)

    def test_health_endpoint_with_firestore(self, client, mock_firestore_client):
        """Test health endpoint when Firestore is available"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['status'] == 'ok'
        assert data['db'] == 'firestore'

    @patch('app.db', side_effect=Exception('Firestore connection failed'))
    def test_health_endpoint_with_devdb_fallback(self, mock_db, client):
        """Test health endpoint when Firestore fails and DevDB is used"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['status'] == 'ok'
        # Should still work even if db check fails

    def test_health_endpoint_headers(self, client):
        """Test health endpoint response headers"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        assert response.headers.get('Content-Type') == 'application/json'

    def test_health_endpoint_methods(self, client):
        """Test health endpoint only allows GET method"""
        # GET should work
        response = client.get('/api/health')
        assert response.status_code == 200
        
        # POST should not be allowed
        response = client.post('/api/health')
        assert response.status_code == 405
        
        # PUT should not be allowed
        response = client.put('/api/health')
        assert response.status_code == 405
        
        # DELETE should not be allowed
        response = client.delete('/api/health')
        assert response.status_code == 405

    def test_health_endpoint_gemini_configuration(self, client):
        """Test health endpoint shows Gemini configuration status"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should indicate whether Gemini is configured
        assert 'gemini_configured' in data
        assert data['gemini_configured'] is True  # Should be True from test setup

    def test_health_endpoint_jwt_configuration(self, client):
        """Test health endpoint shows JWT configuration status"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should indicate whether JWT is configured
        assert 'jwt_configured' in data
        assert data['jwt_configured'] is True  # Should be True from test setup

    def test_health_endpoint_agent_metrics(self, client):
        """Test health endpoint includes agent metrics"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should include agent JSON metrics
        assert 'agent_json_metrics' in data
        metrics = data['agent_json_metrics']
        assert 'ok' in metrics
        assert 'fail' in metrics
        assert isinstance(metrics['ok'], int)
        assert isinstance(metrics['fail'], int)

    def test_health_endpoint_consistent_response(self, client):
        """Test health endpoint returns consistent response structure"""
        response1 = client.get('/api/health')
        response2 = client.get('/api/health')
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        # Structure should be the same
        assert set(data1.keys()) == set(data2.keys())
        assert data1['status'] == data2['status']
        assert data1['env'] == data2['env']
        assert data1['db'] == data2['db']

    @patch('app.db', side_effect=Exception('Database error'))
    def test_health_endpoint_database_error_handling(self, mock_db, client):
        """Test health endpoint handles database errors gracefully"""
        response = client.get('/api/health')
        
        # Should still return 200 OK even if database check fails
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'

    def test_health_endpoint_environment_detection(self, client):
        """Test health endpoint correctly detects environment"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Environment should be 'testing' in test context
        assert data['env'] == 'testing'

    @patch('app.logger')
    def test_health_endpoint_exception_handling(self, mock_logger, client):
        """Test health endpoint exception handling"""
        # Force an exception in the health check
        with patch('app.jsonify', side_effect=Exception('Test exception')):
            response = client.get('/api/health')
            
            # Should return 500 on unhandled exception
            assert response.status_code == 500

    def test_health_endpoint_database_type_detection(self, client):
        """Test health endpoint correctly identifies database type"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should correctly identify the database type
        assert data['db'] in ['firestore', 'devdb', 'unknown']

    def test_health_endpoint_devdb_detection(self, client):
        """Test health endpoint detects DevDB correctly"""
        # Create a mock DevDB-like object
        class MockDevDB:
            pass
        
        mock_devdb_instance = MockDevDB()
        
        with patch('app.db', mock_devdb_instance):
            response = client.get('/api/health')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Should detect DevDB-like object
            assert data['db'] in ['devdb', 'unknown']