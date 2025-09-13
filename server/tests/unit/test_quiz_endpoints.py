"""
Test quiz and analysis related endpoints
"""
import pytest
import json
from unittest.mock import patch, MagicMock

class TestQuizEndpoints:
    """Test quiz and personality analysis endpoints"""

    def test_get_questions_endpoint(self, client):
        """Test GET /api/questions endpoint"""
        response = client.get('/api/questions')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should return a list of questions
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Each question should have required fields
        for question in data:
            assert 'id' in question
            assert 'question' in question
            assert 'trait' in question
            assert 'options' in question
            assert isinstance(question['options'], list)

    def test_get_questions_structure(self, client):
        """Test questions have proper structure"""
        response = client.get('/api/questions')
        data = response.get_json()
        
        question = data[0]
        
        # Check question structure
        assert isinstance(question['id'], int)
        assert isinstance(question['question'], str)
        assert isinstance(question['trait'], str)
        assert isinstance(question['options'], list)
        
        # Check options structure
        for option in question['options']:
            assert 'text' in option
            assert 'score' in option
            assert isinstance(option['text'], str)
            assert isinstance(option['score'], int)

    def test_get_hobbies_master(self, client):
        """Test GET /api/hobbies endpoint"""
        response = client.get('/api/hobbies')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should return items list
        assert 'items' in data
        assert isinstance(data['items'], list)
        assert len(data['items']) > 0
        
        # Each hobby should have required fields
        hobby = data['items'][0]
        assert 'id' in hobby
        assert 'label' in hobby
        assert 'emoji' in hobby
        assert 'weights' in hobby

    def test_analyze_text_endpoint(self, client, mock_gemini):
        """Test POST /api/analyze endpoint"""
        mock_gemini.return_value = {
            'analyzed_score': 3.5,
            'explanation': 'This shows moderate preference'
        }
        
        response = client.post('/api/analyze',
            json={
                'text': 'I enjoy traveling to new places and meeting people',
                'trait': 'novelty',
                'question': 'Do you prefer familiar or new experiences?',
                'base_score': 3,
                'question_id': 'q1'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'analyzed_score' in data
        assert 'explanation' in data
        assert isinstance(data['analyzed_score'], (int, float))
        assert isinstance(data['explanation'], str)

    def test_analyze_text_missing_fields(self, client):
        """Test analyze endpoint with missing fields - should handle gracefully"""
        # Missing text should work with base_score
        response = client.post('/api/analyze',
            json={
                'trait': 'novelty',
                'question': 'Test question?',
                'base_score': 2,
                'question_id': 1
            },
            content_type='application/json'
        )
        assert response.status_code == 200

        # Missing trait should also work
        response = client.post('/api/analyze',
            json={
                'text': 'Some text',
                'question': 'Test question?'
            },
            content_type='application/json'
        )
        assert response.status_code == 200

    def test_analyze_text_empty_values(self, client, mock_gemini):
        """Test analyze endpoint with empty values"""
        mock_gemini.return_value = {
            'analyzed_score': 2.0,
            'explanation': 'Minimal input provided'
        }
        
        response = client.post('/api/analyze',
            json={
                'text': '',  # Empty text
                'trait': 'novelty',
                'question': 'Test question?',
                'base_score': 3
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        # Should handle empty text gracefully
        assert 'analyzed_score' in data

    def test_analyze_text_long_input(self, client, mock_gemini):
        """Test analyze endpoint with very long text input"""
        mock_gemini.return_value = {
            'analyzed_score': 4.0,
            'explanation': 'Long detailed response indicates strong preference'
        }
        
        long_text = 'I really love traveling ' * 100  # Very long text
        
        response = client.post('/api/analyze',
            json={
                'text': long_text,
                'trait': 'novelty', 
                'question': 'Test question?',
                'base_score': 3
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'analyzed_score' in data

    @patch('utils.ai_processing.call_gemini_api')
    def test_analyze_text_gemini_error(self, mock_gemini, client):
        """Test analyze endpoint when Gemini API fails"""
        mock_gemini.side_effect = Exception('Gemini API error')
        
        response = client.post('/api/analyze',
            json={
                'text': 'Some text',
                'trait': 'novelty',
                'question': 'Test question?',
                'base_score': 3
            },
            content_type='application/json'
        )
        
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    def test_analyze_text_score_range(self, client, mock_gemini):
        """Test analyze endpoint returns scores in valid range"""
        mock_gemini.return_value = {
            'analyzed_score': 5.5,  # Out of range (should be 1-5)
            'explanation': 'Test explanation'
        }
        
        response = client.post('/api/analyze',
            json={
                'text': 'Some text',
                'trait': 'novelty',
                'question': 'Test question?',
                'base_score': 3
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should clamp score to valid range (1-5)
        assert 1 <= data['analyzed_score'] <= 5

    def test_analyze_text_different_traits(self, client, mock_gemini):
        """Test analyze endpoint with different personality traits"""
        traits = ['novelty', 'pace', 'budget', 'social', 'culture', 'nature']
        
        for trait in traits:
            mock_gemini.return_value = {
                'analyzed_score': 3.0,
                'explanation': f'Analysis for {trait} trait'
            }
            
            response = client.post('/api/analyze',
                json={
                    'text': f'Text related to {trait}',
                    'trait': trait,
                    'question': f'Question about {trait}?',
                    'base_score': 3
                },
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert 'analyzed_score' in data
            assert 'explanation' in data

    def test_analyze_text_with_japanese_text(self, client, mock_gemini):
        """Test analyze endpoint with Japanese text input"""
        mock_gemini.return_value = {
            'analyzed_score': 4.0,
            'explanation': '日本語での説明'
        }
        
        response = client.post('/api/analyze',
            json={
                'text': '新しい場所を探索するのが好きです',
                'trait': 'novelty',
                'question': '新しい体験は好きですか？',
                'base_score': 3
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'analyzed_score' in data
        assert 'explanation' in data

    def test_analyze_text_concurrent_requests(self, client, mock_gemini):
        """Test analyze endpoint with concurrent requests"""
        mock_gemini.return_value = {
            'analyzed_score': 3.5,
            'explanation': 'Concurrent analysis'
        }
        
        # Simulate concurrent requests
        import threading
        results = []
        
        def make_request():
            response = client.post('/api/analyze',
                json={
                    'text': 'Concurrent test',
                    'trait': 'novelty',
                    'question': 'Test?',
                    'base_score': 3
                },
                content_type='application/json'
            )
            results.append(response.status_code)
        
        threads = [threading.Thread(target=make_request) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)

    def test_questions_endpoint_caching(self, client):
        """Test questions endpoint consistency (implicitly tests caching)"""
        response1 = client.get('/api/questions')
        response2 = client.get('/api/questions')
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        # Should return identical data
        assert data1 == data2

    def test_hobbies_endpoint_structure(self, client):
        """Test hobbies endpoint returns proper structure"""
        response = client.get('/api/hobbies')
        data = response.get_json()
        
        for hobby in data['items'][:5]:  # Check first 5 hobbies
            # Required fields
            assert isinstance(hobby['id'], str)
            assert isinstance(hobby['label'], str)
            assert isinstance(hobby['emoji'], str)
            assert isinstance(hobby['weights'], dict)
            
            # Weights should be valid
            for weight_key, weight_value in hobby['weights'].items():
                assert isinstance(weight_key, str)
                assert isinstance(weight_value, (int, float))
                assert -1.0 <= weight_value <= 1.0  # Reasonable weight range