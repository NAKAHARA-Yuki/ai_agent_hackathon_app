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
            'video_urls': saved.get('video_urls') or [],
            'primary_video_url': saved.get('primary_video_url'),
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
            'video_urls': data.get('video_urls') or [],
            'primary_video_url': data.get('primary_video_url'),
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


def _launch_veo_jobs(images: List[Dict[str, Any]], user_id: str, memory_id: str, prompt: str) -> List[Dict[str, Any]]:
    """Launch Vertex Veo predictLongRunning jobs for each image. Returns list of job metadata.

    Note: We do NOT set storageUri. We'll fetch the base64 video upon completion via operations API,
    then upload to GCS ourselves and persist the public URL in Firestore.
    """
    project_id = os.getenv('VEO_PROJECT_ID') or os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT') or 'ai-agent-hackason'
    location = os.getenv('VEO_LOCATION', 'us-central1')
    model_id = os.getenv('VEO_MODEL_ID', 'veo-3.0-fast-generate-preview')
    api_endpoint = os.getenv('VEO_API_ENDPOINT', f'{location}-aiplatform.googleapis.com')

    token = _get_gcp_access_token()
    url = f"https://{api_endpoint}/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:predictLongRunning"

    jobs = []
    for idx, img in enumerate(images):
        try:
            b64 = img.get('image_base64')
            mime = img.get('image_mime_type') or 'image/jpeg'
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

    Returns: { video_jobs: [{ index, operation_name, done, error, video_public_url }], all_done: bool }
    """
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
                    # On completion, try to extract base64 video and persist to GCS, store URL
                    if entry.get('done') and not entry.get('video_public_url'):
                        try:
                            # Veo operations response assumed to include base64 under one of known keys
                            video_b64 = None
                            # Common patterns (adjust if API differs)
                            if isinstance(data.get('response'), dict):
                                video_b64 = data['response'].get('video', {}).get('bytesBase64Encoded') or data['response'].get('videoBase64')
                            if not video_b64 and isinstance(data.get('result'), dict):
                                video_b64 = data['result'].get('video', {}).get('bytesBase64Encoded') or data['result'].get('videoBase64')
                            if not video_b64 and isinstance(data.get('videos'), list) and data['videos']:
                                first = data['videos'][0]
                                if isinstance(first, dict):
                                    video_b64 = first.get('bytesBase64Encoded') or first.get('base64')
                            if video_b64:
                                public_url = _save_video_to_gcs(video_b64, user_id, mem_id, idx)
                                if public_url:
                                    entry['video_public_url'] = public_url
                        except Exception as e:
                            entry['error'] = f"save_video: {e}"
            except Exception as e:
                entry['error'] = str(e)
            updated_jobs.append(entry)

        all_done = all(bool(j.get('done')) for j in updated_jobs) if updated_jobs else False

        # persist back
        try:
            # If any job has video_public_url, also store a top-level field for convenience
            public_urls = [j.get('video_public_url') for j in updated_jobs if j.get('video_public_url')]
            update_doc = { 'video_jobs': updated_jobs, 'updated_at': firestore.SERVER_TIMESTAMP }
            if public_urls:
                update_doc['video_urls'] = public_urls
                update_doc['primary_video_url'] = public_urls[0]
            doc_ref.update(update_doc, timeout=5)
        except Exception:
            pass

        return jsonify({ 'video_jobs': updated_jobs, 'all_done': all_done, 'primary_video_url': (public_urls[0] if 'public_urls' in locals() and public_urls else None), 'video_urls': (public_urls if 'public_urls' in locals() else []) })
    except Exception:
        logger.exception('/api/memories/{id}/video-status GET error')
        return jsonify({"error": "database_unavailable"}), 503


def _save_video_to_gcs(video_b64: str, user_id: str, mem_id: str, idx: int) -> str | None:
    """Decode base64 video and upload to GCS. Return a public or signed URL."""
    try:
        import base64
        from google.cloud import storage  # type: ignore

        bucket_name = os.getenv('GCS_VIDEO_BUCKET', 'izatabi')
        object_name = f"users/{user_id}/memories/{mem_id}/video_{(idx or 0)+1}.mp4"
        content_type = 'video/mp4'

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        raw = base64.b64decode(video_b64)
        blob.upload_from_string(raw, content_type=content_type)

        # Public or signed URL
        if os.getenv('GCS_PUBLIC_READ', 'true').lower() == 'true':
            try:
                blob.make_public()
            except Exception:
                pass
            return blob.public_url
        else:
            # Signed URL for 7 days by default
            from datetime import timedelta
            # 半年 = 60*60*24*30*6 = 15,552,000 秒
            expires = int(os.getenv('GCS_SIGNED_URL_EXPIRES_SECONDS', '15552000'))
            url = blob.generate_signed_url(expiration=timedelta(seconds=expires), method='GET')
            return url
    except Exception as e:
        logger.warning(f'GCS upload failed: {e}')
        return None
