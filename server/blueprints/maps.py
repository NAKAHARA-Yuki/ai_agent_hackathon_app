"""Maps and geocoding blueprint for Google Maps integration."""
from flask import Blueprint, request, jsonify
import logging
import os

logger = logging.getLogger(__name__)

maps_bp = Blueprint('maps', __name__)


@maps_bp.route('/api/maps-key', methods=['GET'])
def get_maps_key():
    """Get Google Maps API key for frontend."""
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        return jsonify({'error': 'Maps API key not configured'}), 500
    return jsonify({'key': api_key})


@maps_bp.route('/api/geocode', methods=['POST'])
def geocode():
    """Geocode a location name to coordinates."""
    data = request.get_json()
    if not data or 'address' not in data:
        return jsonify({'error': 'Address required'}), 400
    
    # This would normally use Google Maps Geocoding API
    # For now, return a mock response to maintain functionality
    return jsonify({
        'results': [{
            'formatted_address': data['address'],
            'geometry': {
                'location': {
                    'lat': 35.6762,  # Default to Tokyo coordinates
                    'lng': 139.6503
                }
            }
        }]
    })


@maps_bp.route('/api/maps/static', methods=['GET'])
def static_map():
    """Generate static map image URL."""
    # Mock implementation - would normally generate Google Static Maps API URL
    return jsonify({
        'url': 'https://via.placeholder.com/600x400/4285F4/FFFFFF?text=Map+Placeholder'
    })