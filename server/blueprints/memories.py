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
from utils.data_processing import sanitize_title

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
                    out = {
                        'id': getattr(d, 'id', None),
                        'plan_id': data.get('plan_id'),
                        'title': data.get('title'),
                        'images': data.get('images') or [],
                        'video_jobs': data.get('video_jobs') or [],
                        'trip_start_date': data.get('trip_start_date'),
                        'trip_end_date': data.get('trip_end_date'),
                        'text': data.get('text'),
                        'summary': data.get('summary'),
                        'itinerary': data.get('itinerary') or [],
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
    # Optional trip dates (YYYY-MM-DD)
    trip_start_date = payload.get('trip_start_date') if isinstance(payload.get('trip_start_date'), str) else None
    trip_end_date = payload.get('trip_end_date') if isinstance(payload.get('trip_end_date'), str) else None
    if not plan_id:
        return jsonify({"error": "plan_id_required"}), 400

    # Normalize images: take up to 3 base64 images
    def _resize_image_if_needed(b64: str, mime: str, max_w: int = 1280, max_h: int = 720) -> tuple[str, str] | tuple[None, None]:
        try:
            import base64, io
            from PIL import Image, ImageOps  # type: ignore
            # Strip data URL prefix if present
            header = None
            if b64.startswith('data:'):
                try:
                    header, b64 = b64.split(',', 1)
                except Exception:
                    header = None
            raw = base64.b64decode(b64)
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                w, h = im.size
                # Decide target format (supported only)
                use_jpeg = (mime or '').lower() in ('image/jpeg', 'image/jpg', 'jpeg', 'jpg')
                target_fmt = 'JPEG' if use_jpeg else 'PNG'
                new_mime = 'image/jpeg' if use_jpeg else 'image/png'

                # Prepare image mode for target format
                if target_fmt == 'JPEG':
                    # JPEG doesn't support alpha; composite on white
                    if im.mode in ('RGBA', 'LA'):
                        bg = Image.new('RGB', im.size, (255, 255, 255))
                        tmp = im.convert('RGBA') if im.mode != 'RGBA' else im
                        bg.paste(tmp, mask=tmp.split()[-1])
                        im = bg
                    else:
                        im = im.convert('RGB')
                else:
                    # PNG can keep alpha; normalize palette
                    if im.mode in ('P',):
                        im = im.convert('RGBA')

                # Resize if larger than box, otherwise keep original size
                if w > max_w or h > max_h:
                    im = ImageOps.contain(im, (max_w, max_h), method=Image.LANCZOS)

                out = io.BytesIO()
                if target_fmt == 'JPEG':
                    im.save(out, format='JPEG', quality=85, optimize=True)
                else:
                    im.save(out, format='PNG', optimize=True)
                out_b64 = base64.b64encode(out.getvalue()).decode('utf-8')
                return (out_b64, new_mime)
        except Exception:
            return (b64, mime)

    norm_images = []
    for img in images[:3]:
        if isinstance(img, dict) and isinstance(img.get('image_base64'), str):
            mime = img.get('image_mime_type') if isinstance(img.get('image_mime_type'), str) else 'image/png'
            b64_in = img.get('image_base64')
            b64_out, mime_out = _resize_image_if_needed(b64_in, mime)
            norm_images.append({
                'image_base64': b64_out,
                'image_mime_type': mime_out,
            })

    doc = {
        'plan_id': plan_id,
        'images': norm_images,
    'trip_start_date': trip_start_date,
    'trip_end_date': trip_end_date,
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    }
    # Try to pull title/text/summary/itinerary from the linked plan as snapshot fields
    try:
        plan_snap = user_ref.collection('plans').document(plan_id).get(timeout=5)
        if getattr(plan_snap, 'exists', False):
            p = plan_snap.to_dict() or {}
            if isinstance(p.get('title'), str):
                doc['title'] = sanitize_title(p.get('title'))
            if isinstance(p.get('text'), str):
                doc['text'] = p.get('text')
            if isinstance(p.get('summary'), str):
                doc['summary'] = p.get('summary')
            if isinstance(p.get('itinerary'), list):
                doc['itinerary'] = p.get('itinerary')
    except Exception:
        pass
    # If client provided explicit title, prefer it (after sanitize)
    if isinstance(payload.get('title'), str):
        doc['title'] = sanitize_title(payload.get('title'))
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
            'title': saved.get('title'),
            'images': saved.get('images') or [],
            'video_jobs': saved.get('video_jobs') or video_jobs or [],
            'video_urls': saved.get('video_urls') or [],
            'primary_video_url': saved.get('primary_video_url'),
            'text': saved.get('text'),
            'summary': saved.get('summary'),
            'itinerary': saved.get('itinerary') or [],
            'created_at': saved.get('created_at'),
            'updated_at': saved.get('updated_at'),
            'trip_start_date': saved.get('trip_start_date'),
            'trip_end_date': saved.get('trip_end_date'),
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
            'title': data.get('title'),
            'images': data.get('images') or [],
            'video_jobs': data.get('video_jobs') or [],
            'video_urls': data.get('video_urls') or [],
            'primary_video_url': data.get('primary_video_url'),
            'text': data.get('text'),
            'summary': data.get('summary'),
            'itinerary': data.get('itinerary') or [],
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at'),
            'trip_start_date': data.get('trip_start_date'),
            'trip_end_date': data.get('trip_end_date'),
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

    Direct-save to Cloud Storage: set parameters.storageUri so Veo writes mp4 files
    into the specified GCS bucket/prefix. On completion, we'll read response.videos[].gcsUri
    and convert it to a public/signed URL.
    """
    project_id = os.getenv('VEO_PROJECT_ID') or os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT') or 'ai-agent-hackason'
    location = os.getenv('VEO_LOCATION', 'us-central1')
    model_id = os.getenv('VEO_MODEL_ID', 'veo-3.0-fast-generate-preview')
    api_endpoint = os.getenv('VEO_API_ENDPOINT', f'{location}-aiplatform.googleapis.com')

    token = _get_gcp_access_token()
    url = f"https://{api_endpoint}/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:predictLongRunning"

    # Target GCS bucket/prefix for outputs
    bucket_name = os.getenv('GCS_VIDEO_BUCKET', 'izatabi')
    base_prefix = f"users/{user_id}/memories/{memory_id}/"
    storage_uri = f"gs://{bucket_name}/{base_prefix}"

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
                    # Instruct Veo to store outputs directly to Cloud Storage
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
            return jsonify({
                'video_jobs': jobs,
                'all_done': all_done,
                'video_urls': data.get('video_urls') or [],
                'primary_video_url': data.get('primary_video_url')
            })

        # Resolve endpoint, model, project and token
        location = os.getenv('VEO_LOCATION', 'us-central1')
        project_id = os.getenv('VEO_PROJECT_ID') or os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT') or 'ai-agent-hackason'
        model_id = os.getenv('VEO_MODEL_ID', 'veo-3.0-fast-generate-preview')
        api_endpoint = os.getenv('VEO_API_ENDPOINT', f'{location}-aiplatform.googleapis.com')
        token = _get_gcp_access_token()

        updated_jobs = []
        headers = { 'Authorization': f'Bearer {token}' }
        headers_json = { **headers, 'Content-Type': 'application/json' }
        for j in jobs:
            idx = j.get('index')
            op = j.get('operation_name')
            entry = dict(j)
            try:
                if op and isinstance(op, str):
                    # Veo requires fetchPredictOperation with POST
                    url = f"https://{api_endpoint}/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:fetchPredictOperation"
                    payload = { 'operationName': op }
                    resp = requests.post(url, headers=headers_json, data=json.dumps(payload), timeout=30)
                    data = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
                    entry['done'] = bool(data.get('done')) if resp.ok else False
                    if not resp.ok:
                        entry['error'] = f"HTTP {resp.status_code}"
                    elif 'error' in data:
                        entry['error'] = data.get('error')
                    # On completion, try to read GCS URI and publish/sign it to a URL; fallback to base64 path
                    if entry.get('done') and not entry.get('video_public_url'):
                        try:
                            public_url = None
                            if isinstance(data.get('response'), dict):
                                resp_videos = data['response'].get('videos')
                                if isinstance(resp_videos, list) and resp_videos:
                                    first = resp_videos[0] if isinstance(resp_videos[0], dict) else None
                                    gcs_uri = first.get('gcsUri') if first else None
                                    if gcs_uri:
                                        public_url = _publish_gcs_uri(gcs_uri)
                                    else:
                                        # Back-compat: some responses may include base64
                                        video_b64 = first.get('bytesBase64Encoded') or first.get('base64') if first else None
                                        if video_b64:
                                            public_url = _save_video_to_gcs(video_b64, user_id, mem_id, idx)
                            if not public_url and isinstance(data.get('result'), dict):
                                video_b64 = data['result'].get('video', {}).get('bytesBase64Encoded') or data['result'].get('videoBase64')
                                if video_b64:
                                    public_url = _save_video_to_gcs(video_b64, user_id, mem_id, idx)
                            if public_url:
                                entry['video_public_url'] = public_url
                        except Exception as e:
                            entry['error'] = f"publish_video: {e}"
            except Exception as e:
                entry['error'] = str(e)
            updated_jobs.append(entry)

        all_done = all(bool(j.get('done')) for j in updated_jobs) if updated_jobs else False

        # persist back
        public_urls = [j.get('video_public_url') for j in updated_jobs if j.get('video_public_url')]
        update_doc = { 'video_jobs': updated_jobs, 'updated_at': firestore.SERVER_TIMESTAMP }
        if public_urls:
            update_doc['video_urls'] = public_urls
            update_doc['primary_video_url'] = public_urls[0]
        try:
            doc_ref.update(update_doc, timeout=5)
        except Exception:
            pass

        return jsonify({ 'video_jobs': updated_jobs, 'all_done': all_done, 'primary_video_url': (public_urls[0] if public_urls else data.get('primary_video_url')), 'video_urls': public_urls })
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

        # Public, authenticated-console style, or signed URL
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


def _publish_gcs_uri(gcs_uri: str) -> str | None:
    """Given a gs://bucket/object URI, return a public URL (or signed URL).

    If GCS_PUBLIC_READ=true, attempt to make the object public and return its public URL.
    Otherwise, return a signed URL with expiration derived from GCS_SIGNED_URL_EXPIRES_SECONDS.
    """
    try:
        if not (isinstance(gcs_uri, str) and gcs_uri.startswith('gs://')):
            return None
        from google.cloud import storage  # type: ignore
        without = gcs_uri[len('gs://'):]
        # split once: bucket / object path
        if '/' not in without:
            return None
        bucket_name, object_name = without.split('/', 1)

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        if os.getenv('GCS_PUBLIC_READ', 'true').lower() == 'true':
            try:
                blob.make_public()
            except Exception:
                pass
            # Use blob.public_url which returns https://storage.googleapis.com/bucket/object by default
            return blob.public_url
        else:
            from datetime import timedelta
            expires = int(os.getenv('GCS_SIGNED_URL_EXPIRES_SECONDS', '15552000'))
            return blob.generate_signed_url(expiration=timedelta(seconds=expires), method='GET')
    except Exception as e:
        logger.warning(f'GCS publish failed for {gcs_uri}: {e}')
        return None
