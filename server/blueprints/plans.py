"""Travel plans management blueprint"""
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from google.cloud import firestore

from utils.auth import claims_or_dev
from utils.data_processing import normalize_places_list, normalize_route_info, sanitize_title, sanitize_text

logger = logging.getLogger(__name__)

plans_bp = Blueprint('plans', __name__)


@plans_bp.route('/api/active-plan', methods=['GET', 'POST'])
def active_plan():
    """Manage the currently active travel plan"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    claims = claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    
    user_id = claims['sub']
    user_ref = db.collection('users').document(user_id)
    
    if request.method == 'GET':
        # Get the currently active plan
        try:
            snap = user_ref.get(timeout=5)
            if snap and snap.exists:
                data = snap.to_dict() or {}
                active_plan_id = data.get('active_plan_id')
                if active_plan_id:
                    # Fetch the full plan details
                    plan_ref = user_ref.collection('plans').document(active_plan_id)
                    plan_snap = plan_ref.get(timeout=5)
                    if plan_snap and plan_snap.exists:
                        plan_data = plan_snap.to_dict() or {}
                        plan_data['id'] = active_plan_id
                        return jsonify({'active_plan': plan_data})
            return jsonify({'active_plan': None})
        except Exception as e:
            logger.exception("/api/active-plan GET error")
            return jsonify({'active_plan': None})
    
    # POST: Set active plan
    payload = request.get_json() or {}
    plan_id = payload.get('plan_id')
    
    if not plan_id:
        # Deactivate current plan
        try:
            user_ref.update({
                'active_plan_id': None,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, timeout=5)
        except Exception:
            try:
                user_ref.set({
                    'active_plan_id': None,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True, timeout=5)
            except Exception as e:
                logger.exception("/api/active-plan POST (deactivate) error")
                return jsonify({"error": "database_unavailable"}), 503
        return jsonify({'status': 'deactivated'})
    
    # Validate plan exists and belongs to user
    try:
        plan_ref = user_ref.collection('plans').document(plan_id)
        plan_snap = plan_ref.get(timeout=5)
        if not plan_snap or not plan_snap.exists:
            return jsonify({"error": "plan_not_found"}), 404
        
        # Set as active plan
        user_ref.update({
            'active_plan_id': plan_id,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, timeout=5)
        
        # Return the activated plan
        plan_data = plan_snap.to_dict() or {}
        plan_data['id'] = plan_id
        return jsonify({'active_plan': plan_data, 'status': 'activated'})
    except Exception as e:
        logger.exception("/api/active-plan POST (activate) error")
        return jsonify({"error": "database_unavailable"}), 503


@plans_bp.route('/api/plans', methods=['GET', 'POST'])
def plans_collection():
    """Travel plans collection management"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    claims = claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    
    user_id = claims['sub']
    plans_ref = db.collection('users').document(user_id).collection('plans')

    if request.method == 'GET':
        # List plans (basic fields)
        try:
            # Firestore: require order by created_at if exists; DevDB returns unsorted
            items = []
            try:
                # Try Firestore query first
                q = plans_ref
                # Firestore needs an index to order by created_at; fallback to manual
                try:
                    docs = q.stream()
                except Exception:
                    # DevDB path
                    docs = []
                for d in docs:
                    try:
                        data = d.to_dict() or {}
                        if data.get('deleted'):
                            continue
                        first_brief = None
                        try:
                            sugg = data.get('suggestions')
                            if isinstance(sugg, list) and sugg:
                                fb = sugg[0].get('brief') if isinstance(sugg[0], dict) else None
                                if isinstance(fb, str):
                                    first_brief = fb
                        except Exception:
                            pass
                        item = {
                            'id': getattr(d, 'id', None),
                            'title': data.get('title'),
                            'summary': data.get('summary'),
                            'brief': first_brief,
                            'created_at': data.get('created_at'),
                            'updated_at': data.get('updated_at'),
                            'status': data.get('status') or ('confirmed' if data.get('source') == 'chat' else data.get('status')),  # fallback
                            'source': data.get('source')
                        }
                        items.append(item)
                    except Exception:
                        continue
            except Exception:
                items = []
            return jsonify({'items': items})
        except Exception as e:
            logger.exception("/api/plans GET error")
            return jsonify({'items': []})

    # POST: create a new plan (wizard/chat 共通)
    payload = request.get_json() or {}
    title = sanitize_title(payload.get('title') or '')
    text = sanitize_text(payload.get('text') or '')
    # Normalize optional structures
    places = normalize_places_list(payload.get('places'))
    route_info = normalize_route_info(payload.get('route_info') or {})
    summary = sanitize_text(payload.get('summary')) if isinstance(payload.get('summary'), str) else None
    suggestions = payload.get('suggestions') if isinstance(payload.get('suggestions'), list) else None
    itinerary = payload.get('itinerary') if isinstance(payload.get('itinerary'), list) else None
    status = payload.get('status') if isinstance(payload.get('status'), str) else 'confirmed'
    status = status.lower()
    if status not in ('confirmed', 'draft'):
        status = 'confirmed'
    # Optional image payload (base64)
    image_base64 = payload.get('image_base64') if isinstance(payload.get('image_base64'), str) else None
    image_mime_type = payload.get('image_mime_type') if isinstance(payload.get('image_mime_type'), str) else None

    if not title:
        # Fallback sensible title
        title = datetime.utcnow().strftime('旅行プラン %Y-%m-%d %H:%M')
    if not text and not (places or route_info):
        return jsonify({"error": "empty_plan"}), 400

    doc = {
        'title': title,
        'text': text,
        'places': places or [],
        'route_info': route_info or None,
        'summary': summary,
        'suggestions': suggestions or [],
        'itinerary': itinerary or [],
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
        'source': 'chat',
        'status': status,
    }
    if image_base64:
        doc['image_base64'] = image_base64
        if image_mime_type:
            doc['image_mime_type'] = image_mime_type
    try:
        doc_ref = plans_ref.document()
        doc_ref.set(doc, timeout=5)
        # Read back for created_at resolution in DevDB
        try:
            saved = doc_ref.get(timeout=5).to_dict() or {}
        except Exception:
            saved = doc
        out = {
            'id': getattr(doc_ref, 'id', None),
            'title': saved.get('title'),
            'text': saved.get('text'),
            'places': saved.get('places') or [],
            'route_info': saved.get('route_info'),
            'summary': saved.get('summary'),
            'suggestions': saved.get('suggestions') or [],
            'itinerary': saved.get('itinerary') or [],
            'created_at': saved.get('created_at'),
            'updated_at': saved.get('updated_at'),
            'status': saved.get('status') or status,
            'source': saved.get('source'),
            'image_base64': saved.get('image_base64'),
            'image_mime_type': saved.get('image_mime_type'),
        }
        return jsonify(out), 201
    except Exception as e:
        logger.exception("/api/plans POST error")
        return jsonify({"error": "database_unavailable"}), 503


@plans_bp.route('/api/plans/<plan_id>', methods=['GET', 'PATCH', 'DELETE'])
def plans_item(plan_id: str):
    """Individual travel plan management"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    claims = claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    
    user_id = claims['sub']
    if not plan_id or len(plan_id) > 200:
        return jsonify({"error": "invalid_id"}), 400
    
    plan_ref = db.collection('users').document(user_id).collection('plans').document(plan_id)
    
    if request.method == 'GET':
        try:
            snap = plan_ref.get(timeout=5)
            if not getattr(snap, 'exists', False):
                return jsonify({}), 404
            data = snap.to_dict() or {}
            out = data.copy()
            out['id'] = plan_id
            return jsonify(out)
        except Exception as e:
            logger.exception("/api/plans/{id} GET error")
            return jsonify({}), 404

    if request.method == 'PATCH':
        try:
            payload = request.get_json() or {}
            updates = {}
            # Only allow specific fields to be updated for safety
            if isinstance(payload.get('image_base64'), str):
                updates['image_base64'] = payload['image_base64']
            if isinstance(payload.get('image_mime_type'), str):
                updates['image_mime_type'] = payload['image_mime_type']
            # Optionally allow title/summary minor updates (future-proof; keep minimal)
            if isinstance(payload.get('title'), str):
                updates['title'] = sanitize_title(payload['title'])
            if isinstance(payload.get('summary'), str):
                updates['summary'] = sanitize_text(payload['summary'])

            if not updates:
                return jsonify({'status': 'no_changes'}), 200

            updates['updated_at'] = firestore.SERVER_TIMESTAMP
            plan_ref.set(updates, merge=True, timeout=5)

            snap = plan_ref.get(timeout=5)
            data = snap.to_dict() or {}
            data['id'] = plan_id
            return jsonify(data)
        except Exception:
            logger.exception("/api/plans/{id} PATCH error")
            return jsonify({"error": "database_unavailable"}), 503
    
    # DELETE
    try:
        plan_ref.update({'deleted': True, 'updated_at': firestore.SERVER_TIMESTAMP}, timeout=5)
    except Exception:
        try:
            plan_ref.set({'deleted': True, 'updated_at': firestore.SERVER_TIMESTAMP}, merge=True, timeout=5)
        except Exception as e2:
            logger.exception("/api/plans/{id} DELETE error")
            return jsonify({"error": "database_unavailable"}), 503
    
    return jsonify({"status": "deleted"})