"""Memories (albums) blueprint: link a plan and up to 3 images.

Additionally, optionally launch Vertex AI Veo video generation jobs for each image
upon creation. Controlled via env ENABLE_VEO_VIDEO=true in environments with GCP auth.
"""
from flask import Blueprint, request, jsonify, current_app
import logging
import os
import json
import requests
from typing import List, Dict, Any
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
                        'video_jobs': data.get('video_jobs') or [],
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
        # Optionally kick off Veo video generation per image
        video_jobs = []
        try:
            if os.getenv('ENABLE_VEO_VIDEO', 'false').lower() == 'true':
                video_jobs = _launch_veo_jobs(
                    images=norm_images,
                    user_id=user_id,
                    memory_id=getattr(doc_ref, 'id', None) or 'unknown',
                    prompt=str(payload.get('prompt') or 'my memory'),
                    storage_uri_override=payload.get('storage_uri') if isinstance(payload.get('storage_uri'), str) else None
                )
                # persist job metadata
                try:
                    doc_ref.update({'video_jobs': video_jobs, 'updated_at': firestore.SERVER_TIMESTAMP}, timeout=5)
                    saved['video_jobs'] = video_jobs
                except Exception:
                    pass
        except Exception:
            logger.exception('Failed to launch Veo jobs')

        out = {
            'id': getattr(doc_ref, 'id', None),
            'plan_id': saved.get('plan_id'),
            'images': saved.get('images') or [],
            'video_jobs': saved.get('video_jobs') or video_jobs or [],
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
            'video_jobs': data.get('video_jobs') or [],
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at'),
        }
        return jsonify(out)
    except Exception:
        logger.exception('/api/memories/{id} GET error')
        return jsonify({"error": "database_unavailable"}), 503


def _get_gcp_access_token() -> str:
    """Fetch an OAuth2 access token for Cloud Platform scope using default creds."""
    # Local import to avoid hard dependency when video feature is disabled
    import google.auth  # type: ignore
    from google.auth.transport.requests import Request as GoogleAuthRequest  # type: ignore
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    return creds.token


def _launch_veo_jobs(images: List[Dict[str, Any]], user_id: str, memory_id: str, prompt: str, storage_uri_override: str | None = None) -> List[Dict[str, Any]]:
    """Launch Vertex Veo predictLongRunning jobs for each image. Returns list of job metadata."""
    project_id = os.getenv('VEO_PROJECT_ID') or os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT') or 'ai-agent-hackason'
    location = os.getenv('VEO_LOCATION', 'us-central1')
    model_id = os.getenv('VEO_MODEL_ID', 'veo-3.0-fast-generate-preview')
    api_endpoint = os.getenv('VEO_API_ENDPOINT', f'{location}-aiplatform.googleapis.com')

    # storage uri
    if storage_uri_override and isinstance(storage_uri_override, str):
        base_uri = storage_uri_override.rstrip('/') + '/'
    else:
        scheme = os.getenv('GCS_URI_SCHEME', 'gcs')  # 'gs' or 'gcs'
        bucket = os.getenv('GCS_VIDEO_BUCKET', 'izatabi')
        base_uri = f"{scheme}://{bucket}/users/{user_id}/memories/{memory_id}/"

    token = _get_gcp_access_token()
    url = f"https://{api_endpoint}/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:predictLongRunning"

    jobs = []
    for idx, img in enumerate(images):
        try:
            b64 = img.get('image_base64')
            mime = img.get('image_mime_type') or 'image/jpeg'
            storage_uri = f"{base_uri}video_{idx+1}/"
            payload = {
                'instances': [
                    {
                        'prompt': prompt,
                        'image': {
                            'bytesBase64Encoded': b64,
                            'mimeType': mime,
                        },
                    }
                ],
                'parameters': {
                    'aspectRatio': '16:9',
                    'sampleCount': 1,
                    'durationSeconds': 8,
                    'personGeneration': 'allow_all',
                    'addWatermark': True,
                    'includeRaiReason': True,
                    'generateAudio': False,
                    'resolution': '720p',
                    'storageUri': storage_uri,
                },
            }
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            op_name = None
            try:
                data = resp.json()
                op_name = data.get('name') or data.get('operation') or None
            except Exception:
                data = {'status_code': resp.status_code, 'text': resp.text[:200]}
            job = {
                'index': idx,
                'storage_uri': storage_uri,
                'operation_name': op_name,
                'http_status': resp.status_code,
            }
            jobs.append(job)
        except Exception as e:
            logger.warning(f'Veo job launch failed for idx={idx}: {e}')
            jobs.append({'index': idx, 'error': str(e)})
    return jobs


@memories_bp.route('/api/memories/<mem_id>/video-status', methods=['GET'])
def memories_video_status(mem_id: str):
    """Check Veo long-running operations for a memory and return per-job status.

    Returns: { video_jobs: [{ index, operation_name, done, error, storage_uri }], all_done: bool }
    """
    from flask import current_app
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
        jobs = list(data.get('video_jobs') or [])

        # If feature disabled or no jobs, return stored state
        enable = os.getenv('ENABLE_VEO_VIDEO', 'false').lower() == 'true'
        if not enable or not jobs:
            all_done = bool(jobs) and all(bool(j.get('done')) for j in jobs)
            return jsonify({ 'video_jobs': jobs, 'all_done': all_done })

        # Resolve endpoint and token
        location = os.getenv('VEO_LOCATION', 'us-central1')
        api_endpoint = os.getenv('VEO_API_ENDPOINT', f'{location}-aiplatform.googleapis.com')
        token = _get_gcp_access_token()

        updated_jobs = []
        headers = { 'Authorization': f'Bearer {token}' }
        for j in jobs:
            idx = j.get('index')
            op = j.get('operation_name')
            entry = dict(j)
            try:
                if op and isinstance(op, str):
                    url = f"https://{api_endpoint}/v1/{op.lstrip('/')}"
                    resp = requests.get(url, headers=headers, timeout=20)
                    data = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
                    entry['done'] = bool(data.get('done')) if resp.ok else False
                    if not resp.ok:
                        entry['error'] = f"HTTP {resp.status_code}"
                    elif 'error' in data:
                        entry['error'] = data.get('error')
            except Exception as e:
                entry['error'] = str(e)
            updated_jobs.append(entry)

        all_done = all(bool(j.get('done')) for j in updated_jobs) if updated_jobs else False

        # persist back
        try:
            doc_ref.update({ 'video_jobs': updated_jobs, 'updated_at': firestore.SERVER_TIMESTAMP }, timeout=5)
        except Exception:
            pass

        return jsonify({ 'video_jobs': updated_jobs, 'all_done': all_done })
    except Exception:
        logger.exception('/api/memories/{id}/video-status GET error')
        return jsonify({"error": "database_unavailable"}), 503
