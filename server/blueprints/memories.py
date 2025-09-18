"""Memories (albums) blueprint: link a plan and up to 3 images."""
from flask import Blueprint, request, jsonify, current_app
import logging
from datetime import datetime
from google.cloud import firestore

from utils.auth import claims_or_dev

logger = logging.getLogger(__name__)

memories_bp = Blueprint('memories', __name__)


@memories_bp.route('/api/memories', methods=['GET', 'POST'])
def memories_collection():
    db = getattr(current_app, 'db', None)

    claims = claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401

    user_id = claims['sub']
    user_ref = db.collection('users').document(user_id)
    col_ref = user_ref.collection('memories')

    if request.method == 'GET':
        items = []
        try:
            docs = []
            try:
                docs = col_ref.stream()
            except Exception:
                docs = []
            for d in docs:
                try:
                    data = d.to_dict() or {}
                    if data.get('deleted'):
                        continue
                    out = {
                        'id': getattr(d, 'id', None),
                        'plan_id': data.get('plan_id'),
                        'images': data.get('images') or [],
                        'created_at': data.get('created_at'),
                        'updated_at': data.get('updated_at'),
                    }
                    # derive hero from first image
                    hero = None
                    if out['images']:
                        img0 = out['images'][0]
                        if isinstance(img0, dict):
                            hero = {
                                'image_base64': img0.get('image_base64'),
                                'image_mime_type': img0.get('image_mime_type') or 'image/png'
                            }
                    out['hero'] = hero
                    items.append(out)
                except Exception:
                    continue
            return jsonify({'items': items})
        except Exception:
            logger.exception('/api/memories GET error')
            return jsonify({'items': []}), 200

    # POST
    payload = request.get_json() or {}
    plan_id = payload.get('plan_id') if isinstance(payload.get('plan_id'), str) else None
    images = payload.get('images') if isinstance(payload.get('images'), list) else []
    if not plan_id:
        return jsonify({"error": "plan_id_required"}), 400

    # Normalize images: take up to 3 base64 images
    norm_images = []
    for img in images[:3]:
        if isinstance(img, dict) and isinstance(img.get('image_base64'), str):
            norm_images.append({
                'image_base64': img.get('image_base64'),
                'image_mime_type': img.get('image_mime_type') if isinstance(img.get('image_mime_type'), str) else 'image/png'
            })

    doc = {
        'plan_id': plan_id,
        'images': norm_images,
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    }
    try:
        doc_ref = col_ref.document()
        doc_ref.set(doc, timeout=5)
        try:
            saved = doc_ref.get(timeout=5).to_dict() or {}
        except Exception:
            saved = doc
        out = {
            'id': getattr(doc_ref, 'id', None),
            'plan_id': saved.get('plan_id'),
            'images': saved.get('images') or [],
            'created_at': saved.get('created_at'),
            'updated_at': saved.get('updated_at'),
        }
        return jsonify(out), 201
    except Exception:
        logger.exception('/api/memories POST error')
        return jsonify({"error": "database_unavailable"}), 503


@memories_bp.route('/api/memories/<mem_id>', methods=['GET'])
def memories_item(mem_id: str):
    """Return a single memory by id"""
    db = getattr(current_app, 'db', None)

    claims = claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401

    user_id = claims['sub']
    user_ref = db.collection('users').document(user_id)
    doc_ref = user_ref.collection('memories').document(mem_id)
    try:
        snap = doc_ref.get(timeout=5)
        if not getattr(snap, 'exists', False):
            return jsonify({"error": "not_found"}), 404
        data = snap.to_dict() or {}
        if data.get('deleted'):
            return jsonify({"error": "not_found"}), 404
        out = {
            'id': mem_id,
            'plan_id': data.get('plan_id'),
            'images': data.get('images') or [],
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at'),
        }
        return jsonify(out)
    except Exception:
        logger.exception('/api/memories/{id} GET error')
        return jsonify({"error": "database_unavailable"}), 503
