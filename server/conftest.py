"""
Pytest configuration and fixtures for testing Flask app
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Prevent google.cloud.firestore from importing and raising tp_new metaclass error in python 3.14
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.firestore'] = MagicMock()

# Add app module to path
sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    # Mock external services before importing app
    with patch.dict(os.environ, {
        'JWT_SECRET': 'test-secret-key',
        'FLASK_ENV': 'testing',
        'GEMINI_API_KEY': 'test-gemini-key',
        'GOOGLE_MAPS_API_KEY': 'test-maps-key'
    }):
        # Mock Firestore before importing
        with patch('google.cloud.firestore.Client') as mock_firestore:
            mock_firestore.return_value = MagicMock()
            
            # Import app after mocking
            import app as flask_app
            
            # Configure app for testing
            flask_app.app.config['TESTING'] = True
            flask_app.app.config['JWT_SECRET'] = 'test-secret-key'
            
            yield flask_app.app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def auth_headers():
    """Generate authentication headers for testing."""
    import jwt
    from datetime import datetime, timedelta
    
    payload = {
        'sub': 'test_user',
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, 'test-secret-key', algorithm='HS256')
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture
def mock_gemini():
    """Mock Gemini AI API calls across all imports."""
    mock = MagicMock()
    mock.return_value = {'text': 'Mock AI response'}
    
    targets = [
        'utils.ai_processing.call_gemini_api',
        'blueprints.quiz.call_gemini_api',
        'blueprints.personas.call_gemini_api',
        'blueprints.ai.call_gemini_api'
    ]
    
    patched_mocks = []
    for target in targets:
        try:
            p = patch(target, mock)
            p.start()
            patched_mocks.append(p)
        except Exception:
            pass
            
    yield mock
    
    for p in patched_mocks:
        p.stop()

@pytest.fixture
def mock_firestore_client(app):
    """Mock Firestore client."""
    # Setup mock Firestore structure
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_document = MagicMock()
    
    mock_client.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document
    mock_document.get.return_value.exists = True
    mock_document.get.return_value.to_dict.return_value = {}
    
    original_db = getattr(app, 'db', None)
    app.db = mock_client
    yield mock_client
    app.db = original_db

@pytest.fixture
def mock_maps_api():
    """Mock Google Maps API calls."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [{
                'geometry': {'location': {'lat': 35.6762, 'lng': 139.6503}},
                'formatted_address': 'Tokyo, Japan'
            }],
            'status': 'OK'
        }
        mock_get.return_value = mock_response
        yield mock_get

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables and cleanup after tests."""
    import tempfile
    
    # Create temporary database file for isolation
    fd, temp_db_path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    
    # Setup
    original_env = dict(os.environ)
    
    # Set test environment variables
    os.environ.update({
        'JWT_SECRET': 'test-secret-key',
        'FLASK_ENV': 'testing',
        'GEMINI_API_KEY': 'test-gemini-key',
        'GOOGLE_MAPS_API_KEY': 'test-maps-key',
        'LOCAL_DB_PATH': temp_db_path
    })
    
    yield
    
    # Cleanup - restore original environment and delete temp file
    os.environ.clear()
    os.environ.update(original_env)
    try:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)
    except Exception:
        pass

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'name': 'Test User',
        'user_id': 'test_user_123',
        'password': 'test_password_123'
    }

@pytest.fixture
def sample_question_data():
    """Sample question data for testing."""
    return {
        'id': 'q1',
        'question': 'Sample question?',
        'trait': 'novelty',
        'scale': [
            {'value': 1, 'label': 'Strongly disagree'},
            {'value': 2, 'label': 'Disagree'},
            {'value': 3, 'label': 'Neutral'},
            {'value': 4, 'label': 'Agree'},
            {'value': 5, 'label': 'Strongly agree'}
        ]
    }

@pytest.fixture
def sample_plan_data():
    """Sample travel plan data for testing."""
    return {
        'title': 'Test Travel Plan',
        'text': 'This is a test travel plan description',
        'places': [
            {'name': 'Tokyo Tower', 'lat': 35.6586, 'lng': 139.7454},
            {'name': 'Senso-ji Temple', 'lat': 35.7148, 'lng': 139.7967}
        ],
        'route_info': None,
        'summary': 'A great trip to Tokyo',
        'suggestions': ['Visit in spring', 'Try local food'],
        'itinerary': []
    }