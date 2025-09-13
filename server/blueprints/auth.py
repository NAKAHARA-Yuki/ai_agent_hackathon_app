"""Authentication blueprint"""
import re
import logging
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from google.cloud import firestore

from utils.auth import create_jwt, require_auth, claims_or_dev

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

USER_ID_REGEX = r'[a-z0-9_-]{3,30}'


@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration endpoint"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    if db is None:
        return jsonify({"error": "Database not configured"}), 500
    
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    user_id = (data.get('user_id') or '').strip().lower()
    password = data.get('password') or ''
    
    # Validate
    if not name or not user_id or not password:
        return jsonify({"error": "missing fields"}), 400
    
    # user_id: 3-30 chars, lowercase letters, numbers, _-
    if not re.fullmatch(USER_ID_REGEX, user_id):
        return jsonify({"error": "invalid user_id"}), 400
    
    if len(password) < 8:
        return jsonify({"error": "weak password"}), 400
    
    users_ref = db.collection('users')
    # Use user_id as document id to enforce uniqueness
    doc_ref = users_ref.document(user_id)
    
    try:
        if doc_ref.get(timeout=5).exists:
            return jsonify({"error": "user_id already exists"}), 409
        
        user_doc = {
            'name': name,
            'user_id': user_id,
            'password_hash': generate_password_hash(password),
            'diagnosis_completed': False,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(user_doc, timeout=5)
    except Exception as e:
        logger.exception("Signup DB error")
        return jsonify({"error": "database unavailable"}), 503
    
    token = create_jwt(user_id)
    return jsonify({
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "diagnosis_completed": False
        }
    })


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    if db is None:
        return jsonify({"error": "Database not configured"}), 500
    
    data = request.get_json() or {}
    user_id = (data.get('user_id') or '').strip().lower()
    password = data.get('password') or ''
    
    if not user_id or not password:
        return jsonify({"error": "missing fields"}), 400
    
    if not re.fullmatch(USER_ID_REGEX, user_id):
        return jsonify({"error": "invalid user_id"}), 400
    
    users_ref = db.collection('users')
    try:
        doc = users_ref.document(user_id).get(timeout=5)
    except Exception as e:
        logger.exception("Login DB error")
        return jsonify({"error": "database unavailable"}), 503
    
    if not doc.exists:
        return jsonify({"error": "invalid credentials"}), 401
    
    user = doc.to_dict()
    if not check_password_hash(user.get('password_hash', ''), password):
        return jsonify({"error": "invalid credentials"}), 401
    
    token = create_jwt(user_id)
    return jsonify({
        "token": token,
        "user": {
            "id": user_id,
            "name": user.get('name'),
            "diagnosis_completed": bool(user.get('diagnosis_completed'))
        }
    })


@auth_bp.route('/api/me', methods=['GET'])
def me():
    """Get current user information"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    claims = claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    
    try:
        snap = db.collection('users').document(claims['sub']).get(timeout=5)
        if not snap.exists:
            return jsonify({"id": claims['sub'], "diagnosis_completed": False})
        
        u = snap.to_dict() or {}
        return jsonify({
            "id": claims['sub'],
            "name": u.get('name'),
            "diagnosis_completed": bool(u.get('diagnosis_completed')),
            "last_persona_id": u.get('last_persona_id')
        })
    except Exception as e:
        logger.exception("/api/me error")
        # Provide fallback if claims exist but there's a DB error
        if claims and 'sub' in claims:
            return jsonify({"id": claims['sub']}), 200
        else:
            return jsonify({"error": "internal server error"}), 500