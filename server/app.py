"""
Refactored Flask application using Blueprints for better organization and maintainability.
"""
import os
import sys
import json
import logging
import threading
import random
from pathlib import Path
from time import monotonic
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_from_directory, request
from dotenv import load_dotenv
from utils.firestore_dummy import firestore
import uuid
from copy import deepcopy
from utils.data_processing import snip_json

# Add shared module to path  
_this_dir = os.path.dirname(__file__)
_candidate_shared = [
    os.path.join(_this_dir, '..', 'shared'),      # repo layout
    os.path.join(_this_dir, 'shared'),            # copied inside server dir
    '/app/shared',                                # container absolute
    '/shared'                                     # alternative mount
]
for _p in _candidate_shared:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.append(_p)

try:  # prefer real shared module
    from logging_config import (
        configure_basic_cloud_logging,
    enforce_single_line_all,
        configure_gcp_json_logging,
    enforce_json_all,
    )  # type: ignore
except Exception:  # fallback if not present (logging_config missing)
    # shared/logging_config.py がコンテナに存在しない場合のフォールバック
    import logging as _logging

    class _SingleLineFormatter(_logging.Formatter):
        def format(self, record: _logging.LogRecord) -> str:  # noqa: D401
            msg = super().format(record)
            return ' '.join(msg.replace('\n', ' ').replace('\r', ' ').split())

    def configure_basic_cloud_logging(level_name: str = 'INFO', force: bool = False):  # minimal 互換
        lvl = getattr(_logging, (level_name or 'INFO').upper(), _logging.INFO)
        root = _logging.getLogger()
        if force:
            for h in list(root.handlers):
                root.removeHandler(h)
        if not root.handlers:
            h = _logging.StreamHandler()
            h.setFormatter(_SingleLineFormatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
            h.setLevel(lvl)
            root.addHandler(h)
        root.setLevel(lvl)
        return root

    def enforce_single_line_all(level: str = 'INFO'):
        lvl = getattr(_logging, (level or 'INFO').upper(), _logging.INFO)
        root = _logging.getLogger()
        for h in root.handlers:
            h.setFormatter(_SingleLineFormatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
            h.setLevel(lvl)
        root.setLevel(lvl)
    _logging.getLogger(__name__).warning("logging_config module not found; using fallback single-line logger")

# Environment configuration
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"

# Load environment variables
_env_path = Path(__file__).resolve().parent / '.env'
logging.info(f"Attempting to load .env file from: {_env_path}")
try:
    if _env_path.exists():
        load_dotenv(dotenv_path=str(_env_path), override=True)
        logging.info(".env file loaded successfully.")
    else:
        logging.warning(".env file not found at the specified path.")
except Exception as e:
    logging.error(f"Error loading .env file: {e}")
    # fallback to default search if direct load fails
    load_dotenv(override=True)

# Resolve client dist path for SPA serving
_here = Path(__file__).resolve().parent
_client_dist_env = os.getenv('CLIENT_DIST')
_candidates = []
if _client_dist_env:
    _candidates.append(Path(_client_dist_env))
# Local dev layout: <repo>/server/app.py -> <repo>/client/dist
_candidates.append(_here.parent / 'client' / 'dist')
# Container layout: /app/app.py -> /app/client/dist
_candidates.append(_here / 'client' / 'dist')
_client_dist = None
for _p in _candidates:
    try:
        if _p and _p.is_dir():
            _client_dist = _p
            break
    except Exception:
        pass
if _client_dist is None:
    # Fallback to current dir; SPA will 404 for assets, so log a warning
    _client_dist = _here
    logging.warning(f"client/dist not found in candidates: {[str(p) for p in _candidates]}. Falling back to {_client_dist}")
else:
    logging.info(f"Static assets directory: {_client_dist}")

# Create Flask app
app = Flask(__name__, static_folder=str(_client_dist), static_url_path='/static')

# Cloud-friendly logging setup
_default_level = "DEBUG" if (ENV or "").lower() == "development" else "INFO"
LOG_LEVEL = (os.getenv("LOG_LEVEL") or _default_level).upper()
LOG_FORMAT = (os.getenv("LOG_FORMAT") or "json").lower()  # singleline|json
try:
    if LOG_FORMAT == 'json':
        configure_gcp_json_logging(level_name=LOG_LEVEL, force=True, labels={'service': 'server'})
        enforce_json_all(LOG_LEVEL)
    else:
        configure_basic_cloud_logging(level_name=LOG_LEVEL, force=True)
        enforce_single_line_all(LOG_LEVEL)
except Exception:
    configure_basic_cloud_logging(level_name="INFO", force=True)
    try:
        enforce_single_line_all(LOG_LEVEL)
    except Exception:
        pass

logger = logging.getLogger("server")
app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Database setup
# Always use persistent DevDB for local execution and ignore Firestore setup
class _DevDocSnapshot:
    def __init__(self, data):
        self._data = deepcopy(data) if data is not None else None
        self.id = None  # Will be set by the collection stream method

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return deepcopy(self._data) if self._data is not None else None

class _DevDocumentRef:
    def __init__(self, db, path):
        self._db = db
        self._path = path  # tuple of segments
        self.id = path[-1] if path else None

    def _now_iso(self):
        try:
            jst = timezone(timedelta(hours=9))
            return datetime.now(jst).isoformat()
        except Exception:
            return datetime.utcnow().isoformat() + "Z"

    def _resolve(self):
        cur = self._db._store
        for seg in self._path:
            cur = cur.setdefault(seg, {})
        return cur

    def get(self, *args, **kwargs):
        self._db._load_silent()
        node = self._resolve()
        data = node.get("__doc__")
        return _DevDocSnapshot(data)

    def set(self, data, *args, **kwargs):
        self._db._load_silent()
        node = self._resolve()
        doc = deepcopy(data)
        for k, v in list(doc.items()):
            if v == firestore.SERVER_TIMESTAMP:
                doc[k] = self._now_iso()
        node["__doc__"] = doc
        self._db._save()

    def update(self, data, *args, **kwargs):
        self._db._load_silent()
        node = self._resolve()
        base = node.get("__doc__", {})
        for k, v in data.items():
            if v == firestore.SERVER_TIMESTAMP:
                base[k] = self._now_iso()
            else:
                base[k] = v
        node["__doc__"] = base
        self._db._save()

    def collection(self, name):
        return _DevCollectionRef(self._db, self._path + (name,))

class _DevCollectionRef:
    def __init__(self, db, path):
        self._db = db
        self._path = path  # tuple of segments

    def document(self, doc_id=None):
        if not doc_id:
            doc_id = uuid.uuid4().hex
        cur = self._db._store
        for seg in self._path:
            cur = cur.setdefault(seg, {})
        cur.setdefault(doc_id, {})
        return _DevDocumentRef(self._db, self._path + (doc_id,))

    def stream(self):
        self._db._load_silent()
        cur = self._db._store
        for seg in self._path:
            cur = cur.get(seg, {})
            if not isinstance(cur, dict):
                return
        for doc_id, doc_data in cur.items():
            if isinstance(doc_data, dict) and "__doc__" in doc_data:
                doc_snapshot = _DevDocSnapshot(doc_data["__doc__"])
                doc_snapshot.id = doc_id
                yield doc_snapshot

class DevDB:
    def __init__(self, filepath=None):
        if filepath is None:
            filepath = os.getenv("LOCAL_DB_PATH") or os.path.join(os.path.dirname(__file__), "dev_db.json")
        self._filepath = filepath
        self._lock = threading.Lock()
        self._store = {}
        self._load(silent=False)

    def _load(self, silent=False):
        with self._lock:
            if os.path.exists(self._filepath):
                try:
                    with open(self._filepath, 'r', encoding='utf-8') as f:
                        self._store = json.load(f)
                    if not silent:
                        logger.info(f"DevDB loaded from {self._filepath}")
                except Exception as e:
                    if not silent:
                        logger.error(f"Failed to load DevDB from {self._filepath}: {e}")
            else:
                self._store = {}

    def _load_silent(self):
        self._load(silent=True)

    def _save(self):
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
                with open(self._filepath, 'w', encoding='utf-8') as f:
                    json.dump(self._store, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save DevDB to {self._filepath}: {e}")

    def collection(self, name):
        return _DevCollectionRef(self, (name,))

db = DevDB()

# Attach db to app for blueprints to use
app.db = db

# Agent JSON metrics (global state)
app.AGENT_JSON_OK = 0
app.AGENT_JSON_FAIL = 0

@app.before_request
def _start_timer():
    # If debug, capture request body snapshot for logging (small, sanitized)
    try:
        if logger.isEnabledFor(logging.DEBUG) and request.path.startswith('/api/'):
            # Attempt to parse JSON with a small max content length guard
            body_text = None
            if request.method in ('POST', 'PUT', 'PATCH'):
                try:
                    if request.is_json:
                        body_text = snip_json(request.get_json(silent=True) or {})
                    else:
                        body_text = snip_json(request.form.to_dict() or {})
                except Exception:
                    body_text = None
            request._body_snip = body_text
    except Exception:
        pass
    """Start request timing and generate trace ID"""
    try:
        request._start_time = monotonic()
    except Exception:
        request._start_time = None
    # Prefer Cloud Trace header if present: X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=1
    try:
        hdr = request.headers.get('X-Cloud-Trace-Context')
        gcp_trace_id = None
        gcp_span_id = None
        gcp_sampled = None
        if hdr:
            # Expected format: 32-hex/span;o=1
            # e.g., 105445aa7843bc8bf206b12000100000/1;o=1
            parts = hdr.split(';')
            trace_span = parts[0]
            opts = parts[1] if len(parts) > 1 else ''
            if '/' in trace_span:
                t, s = trace_span.split('/', 1)
                gcp_trace_id = t.strip()
                gcp_span_id = s.strip()
            else:
                gcp_trace_id = trace_span.strip()
            if 'o=' in opts:
                try:
                    gcp_sampled = opts.split('o=')[1].strip()
                    gcp_sampled = True if gcp_sampled == '1' else False
                except Exception:
                    gcp_sampled = None
        request._gcp_trace_id = gcp_trace_id
        request._gcp_span_id = gcp_span_id
        request._trace_sampled = gcp_sampled
    except Exception:
        request._gcp_trace_id = None
        request._gcp_span_id = None
        request._trace_sampled = None
    # Local fallback trace id for correlation across app logs
    try:
        request._trace_id = f"{random.getrandbits(64):016x}"
    except Exception:
        request._trace_id = None

@app.after_request
def _log_request(resp):  # type: ignore
    """Log request completion with timing"""
    try:
        dur_ms = None
        if getattr(request, "_start_time", None) is not None:
            dur_ms = (monotonic() - request._start_time) * 1000
        path = request.path
        if path.startswith("/api/"):
            # Prefer GCP trace IDs for correlation
            gcp_trace = getattr(request, '_gcp_trace_id', None)
            gcp_span = getattr(request, '_gcp_span_id', None)
            tid = gcp_span or getattr(request, "_trace_id", None)
            if tid:
                resp.headers["X-Trace-Id"] = str(tid)

            # If JSON logging, emit structured access log with httpRequest
            if (os.getenv('LOG_FORMAT', 'singleline').lower() == 'json'):
                http_req = {
                    'requestMethod': request.method,
                    'requestUrl': request.base_url,
                    'status': resp.status_code,
                    'userAgent': request.headers.get('User-Agent'),
                    'remoteIp': request.headers.get('X-Forwarded-For', request.remote_addr),
                    'referer': request.referrer,
                    'latency': f"{int((dur_ms or 0))}ms",
                    'protocol': request.environ.get('SERVER_PROTOCOL'),
                }
                # Compose trace field if GCP project provided
                project_id = os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
                trace_field = None
                if project_id:
                    trace_id_for_log = gcp_trace or getattr(request, '_trace_id', None)
                    if trace_id_for_log:
                        trace_field = f"projects/{project_id}/traces/{trace_id_for_log}"
                # Optionally attach sanitized bodies at DEBUG level
                request_body = getattr(request, '_body_snip', None) if logger.isEnabledFor(logging.DEBUG) else None
                response_body = None
                if logger.isEnabledFor(logging.DEBUG):
                    try:
                        if resp.is_json:
                            response_body = snip_json(resp.get_json(silent=True) or {})
                        else:
                            response_body = None
                    except Exception:
                        response_body = None

                logger.info(
                    "request",
                    extra={
                        'trace': trace_field,
                        'spanId': gcp_span or getattr(request, '_trace_id', None),
                        'trace_sampled': getattr(request, '_trace_sampled', True) if getattr(request, '_trace_sampled', None) is not None else True,
                        'httpRequest': http_req,
                        'labels': {'route': path},
                        'requestBody': request_body,
                        'responseBody': response_body,
                    },
                )
            else:
                logger.info(f"HTTP {request.method} {path} -> {resp.status_code} {int(dur_ms or 0)}ms trace={tid}")
                if logger.isEnabledFor(logging.DEBUG):
                    try:
                        req_body = getattr(request, '_body_snip', None)
                        if req_body is not None:
                            logger.debug(f"HTTP request body: {req_body} trace={tid}")
                    except Exception:
                        pass
                    try:
                        if resp.is_json:
                            resp_body = snip_json(resp.get_json(silent=True) or {})
                            logger.debug(f"HTTP response body: {resp_body} trace={tid}")
                    except Exception:
                        pass
    except Exception:
        pass
    return resp

# Request-scoped log filter to inject trace/span for downstream logs
class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            gcp_trace = getattr(request, '_gcp_trace_id', None)
            gcp_span = getattr(request, '_gcp_span_id', None)
            tid = gcp_span or getattr(request, '_trace_id', None)
        except Exception:
            gcp_trace = None
            tid = None
        if gcp_trace or tid:
            project_id = os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
            # use gcp trace id if present, else fallback tid (local)
            trace_id_for_log = gcp_trace or getattr(request, '_trace_id', None)
            trace_field = f"projects/{project_id}/traces/{trace_id_for_log}" if (project_id and trace_id_for_log) else None
            if trace_field:
                setattr(record, 'trace', trace_field)
            setattr(record, 'spanId', tid)
            # keep sampled True by default for app logs
            sampled = getattr(request, '_trace_sampled', None)
            setattr(record, 'trace_sampled', bool(sampled) if sampled is not None else True)
        # attach minimal labels
        if not hasattr(record, 'labels'):
            setattr(record, 'labels', {'service': 'server'})
        return True

# Attach filter to all handlers
for h in logging.getLogger().handlers:
    h.addFilter(_RequestContextFilter())

# Register blueprints
from blueprints.health import health_bp
from blueprints.auth import auth_bp
from blueprints.quiz import quiz_bp
from blueprints.personas import personas_bp
from blueprints.plans import plans_bp
from blueprints.memories import memories_bp
from blueprints.ai import ai_bp

app.register_blueprint(health_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(personas_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(memories_bp)

# Static asset routes (serve built client files explicitly)
@app.route('/assets/<path:filename>')
def serve_asset(filename: str):
    try:
        return send_from_directory(app.static_folder, f'assets/{filename}')
    except Exception:
        return jsonify({'error': 'not_found'}), 404

@app.route('/favicon.ico')
def serve_favicon():
    try:
        return send_from_directory(app.static_folder, 'favicon.ico')
    except Exception:
        return jsonify({'error': 'not_found'}), 404

# SPA history fallback (serve index.html for non-API routes)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa_fallback(path: str):
    """Serve SPA for non-API routes"""
    # Do not intercept API routes
    if path.startswith('api/'):
        return jsonify({'error': 'not_found'}), 404
    try:
        # For any other path, serve the SPA entrypoint explicitly from static folder
        return send_from_directory(app.static_folder, 'index.html')
    except Exception:
        # As a last resort, return 404 to avoid masking real backend errors
        return jsonify({'error': 'not_found'}), 404


def create_dummy_user_if_needed():
    """Create a dummy development user if needed"""
    if ENV.lower() != 'development' or db is None:
        return
    
    from werkzeug.security import generate_password_hash
    from google.cloud import firestore
    
    dummy_user_id = 'devuser'
    dummy_password = 'password'
    users_ref = db.collection('users')
    doc_ref = users_ref.document(dummy_user_id)
    
    try:
        user_exists = doc_ref.get(timeout=5).exists
        if user_exists:
            user_data = doc_ref.get().to_dict()
            if user_data.get('diagnosis_completed'):
                logger.info(f"Dummy user '{dummy_user_id}' already exists and has a persona.")
                return
            else:
                logger.info(f"Dummy user '{dummy_user_id}' exists but needs a persona. Creating one...")
        else:
            logger.info(f"Creating dummy user '{dummy_user_id}'...")
            user_doc = {
                'name': 'Dev User',
                'user_id': dummy_user_id,
                'password_hash': generate_password_hash(dummy_password),
                'profile': {
                    'display_name': 'Dev User',
                    'age': 30,
                    'gender': 'その他',
                    'hobbies': ['温泉・サウナ', 'グルメ・食べ歩き'],
                    'location': '東京',
                    'budget': '気にしない',
                    'notes': '開発用のダミーユーザーです。'
                },
                'created_at': firestore.SERVER_TIMESTAMP,
            }
            doc_ref.set(user_doc, timeout=5)
            logger.info(f"Dummy user '{dummy_user_id}' created with password '{dummy_password}'.")

        # Create a dummy persona
        personas_ref = doc_ref.collection('personas')
        persona_doc_ref = personas_ref.document()
        dummy_persona_profile = {
            'title': '冒険グルメ探検家',
            'description': '未知の味と体験を求めて、計画や予算にとらわれず自由な旅を楽しむ。美味しいもののためなら、どこへでも足を運ぶ情熱的な冒険家。',
            'traitScores': {
                '新規性追求': 4, '旅程密度': 2, '予算哲学': 3, '社会的志向性': 3,
                '主な興味関心': 2, '計画志向性': 1, '快適性水準': 2, '活動レベル': 3,
                '安全性の閾値': 2, 'デジタル統合度': 3
            }
        }
        dummy_system_prompt = "あなたは、ユーザーの診断結果「冒険グルメ探検家」に基づき、日本国内のユニークな食体験を提案する専門家です。予算や計画よりも、その場でしか味わえない特別な体験を重視します。ユーザーの趣味である「温泉・サウナ」も考慮に入れ、食と癒やしを組み合わせた最高の旅を提案してください。"
        
        persona_doc = {
            'profile': dummy_persona_profile,
            'system_prompt': dummy_system_prompt,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        persona_doc_ref.set(persona_doc, timeout=5)
        
        # Update user with diagnosis_completed and last_persona_id
        doc_ref.update({
            'diagnosis_completed': True,
            'last_persona_id': persona_doc_ref.id,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, timeout=5)
        
        logger.info(f"Dummy persona created for user '{dummy_user_id}'.")

        # Seed demo plans and memories for local verification (only if none exist)
        try:
            plans_ref = doc_ref.collection('plans')
            has_any_plan = False
            try:
                for _ in plans_ref.stream():
                    has_any_plan = True
                    break
            except Exception:
                has_any_plan = False

            if not has_any_plan:
                # Minimal 1x1 PNG base64 (transparent)
                pixel_png_b64 = (
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA'
                    'ASsJTYQAAAAASUVORK5CYII='
                )

                demo_itinerary = [
                    { 'day': 1, 'items': [
                        { 'time': '10:00', 'title': '浅草寺', 'detail': '歴史的なお寺を散策' },
                        { 'time': '12:00', 'title': '仲見世通り', 'detail': '食べ歩きと土産' },
                        { 'time': '15:00', 'title': 'スカイツリー', 'detail': '展望台からの景色' }
                    ]},
                    { 'day': 2, 'items': [
                        { 'time': '09:30', 'title': '上野公園', 'detail': '美術館や動物園エリアを散策' },
                        { 'time': '13:00', 'title': '秋葉原', 'detail': '電気街とカルチャー巡り' }
                    ]}
                ]

                plan_doc = {
                    'title': '東京シティブレイク 2日間',
                    'text': '下町情緒と近代的な東京をバランスよく楽しむ2日間の旅。',
                    'summary': '浅草・上野・スカイツリーなどを巡るシティブレイク。',
                    'suggestions': [
                        { 'title': '隅田川クルーズ', 'tags': ['クルーズ','夜景'], 'brief': '夕暮れ～夜にかけてのクルーズがおすすめ' }
                    ],
                    'itinerary': demo_itinerary,
                    'places': [ { 'name': '浅草寺' }, { 'name': '東京スカイツリー' }, { 'name': '上野公園' } ],
                    'route_info': None,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP,
                    'source': 'chat',
                    'status': 'confirmed',
                    'image_base64': pixel_png_b64,
                    'image_mime_type': 'image/png',
                }

                plan_ref = plans_ref.document()
                plan_ref.set(plan_doc, timeout=5)
                logger.info("Demo plan seeded for devuser.")

                # Seed one memory linked to the plan
                memories_ref = doc_ref.collection('memories')
                mem_doc = {
                    'plan_id': plan_ref.id,
                    'title': plan_doc.get('title'),
                    'images': [ { 'image_base64': pixel_png_b64, 'image_mime_type': 'image/png' } ],
                    'itinerary': demo_itinerary,
                    'text': plan_doc['text'],
                    'summary': plan_doc['summary'],
                    'trip_start_date': '2025-10-10',
                    'trip_end_date': '2025-10-11',
                    'video_jobs': [],
                    'video_urls': [],
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP,
                }
                mem_ref = memories_ref.document()
                mem_ref.set(mem_doc, timeout=5)
                logger.info("Demo memory seeded for devuser.")
            else:
                logger.info("Plans already exist for devuser; skipping demo seed.")
        except Exception as se:
            logger.warning(f"Demo seed failed: {se}")

    except Exception as e:
        logger.error(f"Failed to create/update dummy user or persona: {e}")


if __name__ == '__main__':
    create_dummy_user_if_needed()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))