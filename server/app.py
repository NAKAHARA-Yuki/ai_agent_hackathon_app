import os
from pathlib import Path
import sys
import time
import random
import re
import json
import requests
import logging
from time import monotonic, sleep
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, send_from_directory, request, Response
from dotenv import load_dotenv
from google.cloud import firestore
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

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
    from logging_config import configure_basic_cloud_logging, enforce_single_line_all  # type: ignore
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

# Ensure we load env from this directory (server/.env) even if CWD is repo root
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

# Resolve absolute path to client/dist so SPA can be served reliably from the backend
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

app = Flask(__name__, static_folder=str(_client_dist), static_url_path='/static')

# Cloud-friendly logging setup 
LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
try:
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

# Constants for active plan context formatting
MAX_ITINERARY_DAYS = 3  # Limit to avoid token limits
MAX_ITEMS_PER_DAY = 4   # Limit items per day
MAX_PLACES = 6          # Limit places in context

# Agent呼び出しHTTPタイムアウト（秒）環境変数で調整可能。デフォルト90。
try:
    AGENT_HTTP_TIMEOUT = int(os.getenv('AGENT_HTTP_TIMEOUT') or '90')
    if AGENT_HTTP_TIMEOUT <= 0:
        AGENT_HTTP_TIMEOUT = 90
except Exception:
    AGENT_HTTP_TIMEOUT = 90
logger.info(f"Agent HTTP timeout configured: {AGENT_HTTP_TIMEOUT}s")

# Whether to log request/response payloads (useful for debugging; be careful in prod)
# Forced to True as requested
LOG_PAYLOADS = True
FULL_PAYLOAD = (os.getenv('CLOUD_LOG_FULL_PAYLOAD') == '1')

SENSITIVE_KEYS = {"password", "pass", "token", "authorization", "api_key", "apikey", "secret", "jwt"}

# Agent JSON-only compliance counters (in-memory)
AGENT_JSON_OK = 0
AGENT_JSON_FAIL = 0
AGENT_JSON_FENCE_STRIPPED = 0

def retry_on_503(func, max_retries=3, base_delay=1.0, *args, **kwargs):
    """
    HTTP 503エラー時のリトライ処理ラッパー。
    指数バックオフでリトライし、最大回数に達した場合は最後の例外を再発生させる。
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):  # 初回 + リトライ回数
        try:
            return func(*args, **kwargs)
        except requests.RequestException as e:
            last_exception = e
            
            # 503以外のHTTPエラーまたは非HTTPエラーの場合はすぐに再発生
            if not hasattr(e, 'response') or e.response is None:
                raise
            
            status_code = e.response.status_code
            if status_code != 503:
                raise
                
            # 最大リトライ回数に達した場合は例外を再発生
            if attempt >= max_retries:
                logger.warning(f"503 retry exhausted after {max_retries} attempts, giving up")
                raise
                
            # 指数バックオフで待機
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.info(f"503 error detected, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries + 1})")
            sleep(delay)
        except Exception as e:
            # requests以外の例外（JSON解析エラーなど）はすぐに再発生
            raise
    
    # ここには到達しないはずだが、念のため
    if last_exception:
        raise last_exception

def _balanced_first_object(seg: str):
    """Return the first complete top-level JSON object substring found in seg using
    balancing of braces (supports nested objects and strings with escapes). If none
    found, return None. Does not attempt to validate trailing extraneous content.
    """
    try:
        start = seg.find('{')
        if start == -1:
            return None
        i = start
        depth = 0
        in_str = False
        esc = False
        while i < len(seg):
            ch = seg[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return seg[start:i+1]
            i += 1
    except Exception:
        return None
    return None

def _snip_text(s: str, limit: int = 2000) -> str:
    try:
        if s is None:
            return "null"
        if len(s) <= limit:
            return s
        more = len(s) - limit
        return s[:limit] + f"...(+{more} chars)"
    except Exception:
        return str(s)[:limit]

def _sanitize(obj, depth: int = 0, max_depth: int = 5):
    if depth > max_depth:
        return "<max_depth>"
    try:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                key = str(k)
                if any(sk in key.lower() for sk in SENSITIVE_KEYS):
                    out[key] = "***"
                else:
                    out[key] = _sanitize(v, depth+1, max_depth)
            return out
        if isinstance(obj, list):
            return [_sanitize(v, depth+1, max_depth) for v in obj]
        if isinstance(obj, (int, float)):
            return obj
        if isinstance(obj, str):
            return obj
        return str(obj)
    except Exception:
        return str(obj)

def _snip_json(obj, limit: int = 2000) -> str:
    try:
        s = json.dumps(_sanitize(obj), ensure_ascii=False, default=str)
    except Exception:
        try:
            s = str(obj)
        except Exception:
            s = "<unserializable>"
    return _snip_text(s, limit)

def _to_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None

def _normalize_places_list(raw):
    """Normalize various shapes of places into list[{name,lat,lng,note}]."""
    if raw is None:
        return None
    out = []
    try:
        if isinstance(raw, dict):
            # Sometimes single object
            raw = [raw]
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    out.append({ 'name': item, 'lat': None, 'lng': None })
                    continue
                if not isinstance(item, dict):
                    continue
                name = item.get('name') or item.get('title') or item.get('label') or item.get('place')
                lat = item.get('lat') if 'lat' in item else item.get('latitude')
                lng = item.get('lng') if 'lng' in item else item.get('lon') if 'lon' in item else item.get('longitude')
                # location: {lat, lng}
                loc = item.get('location')
                if isinstance(loc, dict):
                    lat = lat if lat is not None else loc.get('lat')
                    lng = lng if lng is not None else (loc.get('lng') if 'lng' in loc else loc.get('lon') if 'lon' in loc else loc.get('longitude'))
                note = item.get('note') or item.get('description') or item.get('address')
                # optional rich fields for client map
                url = item.get('url') or item.get('link')
                image_url = item.get('imageUrl') or item.get('image') or item.get('thumbnail')
                icon_url = item.get('iconUrl') or item.get('icon')
                label = item.get('label') if isinstance(item.get('label'), str) else None
                color = item.get('color') if isinstance(item.get('color'), str) else None
                address = item.get('address')
                out.append({
                    'name': name,
                    'lat': _to_float(lat),
                    'lng': _to_float(lng),
                    'note': note,
                    'url': url,
                    'imageUrl': image_url,
                    'iconUrl': icon_url,
                    'label': label,
                    'color': color,
                    'address': address
                })
        return out
    except Exception:
        return None

def _normalize_route_info(obj):
    if not isinstance(obj, dict):
        return None
    origin = obj.get('origin') or obj.get('from') or obj.get('start')
    dest = obj.get('destination') or obj.get('to') or obj.get('end')
    # optional: waypoints and travel mode
    wps = obj.get('waypoints') or obj.get('via') or obj.get('stops')
    if isinstance(wps, (list, tuple)):
        # keep only strings or {lat,lng}/{name}
        norm_wps = []
        for w in wps:
            if isinstance(w, str):
                norm_wps.append(w)
            elif isinstance(w, dict):
                nm = w.get('name')
                lat = w.get('lat') if 'lat' in w else w.get('latitude')
                lng = w.get('lng') if 'lng' in w else w.get('lon') if 'lon' in w else w.get('longitude')
                if isinstance(nm, str) and nm:
                    norm_wps.append(nm)
                elif lat is not None and lng is not None:
                    try:
                        norm_wps.append(f"{float(lat)},{float(lng)}")
                    except Exception:
                        pass
        wps = norm_wps
    else:
        wps = None
    mode = (obj.get('mode') or obj.get('travel_mode') or obj.get('travelMode'))
    if isinstance(mode, str):
        mode = mode.lower()
        if mode not in ('driving','walking','bicycling','transit'):
            mode = None
    else:
        mode = None
    if not origin and not dest:
        return None
    out = { 'origin': origin, 'destination': dest }
    if wps: out['waypoints'] = wps
    if mode: out['mode'] = mode
    return out

def _extract_trailing_json(s: str):
    """Extract trailing JSON object if present; returns (prefix_text, places, route_info, text_field).
    簡素化版: シリアルに候補抽出を試行し最初の成功で終了。"""
    import re as _re

    # --- Helpers ---
    try:
        from flask import g as _flask_g  # type: ignore
    except Exception:
        _flask_g = None

    def _strip_citations(txt: str) -> str:
        return _re.sub(r"(?:\s*\[[0-9,\s]+\])+\s*$", "", txt or "")

    def _attach(obj: dict):
        if not isinstance(obj, dict):
            return
        summary = obj.get('summary') if isinstance(obj.get('summary'), str) else None
        plans = obj.get('plans') if isinstance(obj.get('plans'), list) else None
        plans_norm = []
        def _norm_itinerary(v):
            out = []
            if isinstance(v, list):
                for day_blk in v[:14]:
                    if not isinstance(day_blk, dict):
                        continue
                    day = day_blk.get('day') or day_blk.get('day_number') or day_blk.get('dayNumber')
                    try: day = int(day)
                    except Exception: day = None
                    items_raw = day_blk.get('items') or day_blk.get('plans') or []
                    its = []
                    if isinstance(items_raw, list):
                        for it in items_raw[:24]:
                            if not isinstance(it, dict):
                                continue
                            title = it.get('title') or it.get('name')
                            if not isinstance(title, str) or not title.strip():
                                continue
                            time_s = it.get('time') or it.get('slot') or it.get('start')
                            if isinstance(time_s, (int,float)):
                                if 0 <= time_s < 24: time_s = f"{int(time_s):02d}:00"
                                else: time_s = str(time_s)
                            if not isinstance(time_s, str): time_s = None
                            detail = it.get('detail') or it.get('desc') or it.get('description')
                            if not isinstance(detail, str): detail = None
                            its.append({'time': time_s, 'title': title.strip(), 'detail': detail.strip() if detail else None})
                    out.append({'day': day, 'items': its})
            return out
        if plans:
            for p in plans[:6]:
                if not isinstance(p, dict):
                    continue
                title = p.get('title') if isinstance(p.get('title'), str) else None
                if not title: continue
                tags = p.get('tags') if isinstance(p.get('tags'), list) else []
                tags = [str(t) for t in tags if isinstance(t,(str,int,float))][:8]
                brief = p.get('brief') if isinstance(p.get('brief'), str) else None
                itin = _norm_itinerary(p.get('itinerary'))
                pls = _normalize_places_list(p.get('places'))
                rinfo = _normalize_route_info(p.get('route_info') or p.get('route') or p.get('routeInfo'))
                text_body = p.get('text') if isinstance(p.get('text'), str) else None
                plans_norm.append({'title': title.strip(),'tags': tags,'brief': brief.strip() if brief else None,'itinerary': itin or [],'places': pls or [],'route_info': rinfo,'text': text_body})
        if _flask_g is not None and (summary or plans_norm):
            try:
                _flask_g.agent_struct = {'summary': summary,'plans': plans_norm,'suggestions': [],'itinerary': []}
            except Exception:
                pass

    def _extract_from_obj(obj: dict):
        places = obj.get('places') if isinstance(obj, dict) else None
        if places is None and isinstance(obj, dict):
            places = obj.get('place')
        route_info = obj.get('route_info') if isinstance(obj, dict) else None
        if route_info is None and isinstance(obj, dict):
            route_info = obj.get('route') or obj.get('routeInfo')
        text_field = obj.get('text') if isinstance(obj, dict) else None
        _attach(obj)
        places = _normalize_places_list(places)
        route_info = _normalize_route_info(route_info)
        return places, route_info, (text_field if isinstance(text_field, str) else None)

    s = _strip_citations(s)
    stripped = s.strip()

    # 1. direct parse
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            places, rinfo, text_field = _extract_from_obj(obj)
            return "", places, rinfo, text_field
    except Exception:
        pass

    # 2. single extra '}' recovery
    if stripped.endswith('}}') and stripped.startswith('{'):
        try:
            obj = json.loads(stripped[:-1])
            if isinstance(obj, dict):
                places, rinfo, text_field = _extract_from_obj(obj)
                return "", places, rinfo, text_field
        except Exception:
            pass

    # 3. balanced object with trailing lone '}'
    if stripped.endswith('}'):
        cand = _balanced_first_object(stripped)
        if cand and len(cand) < len(stripped):
            remainder = stripped[len(cand):].strip()
            if remainder in ('','}'):
                try:
                    obj = json.loads(cand)
                    if isinstance(obj, dict):
                        places, rinfo, text_field = _extract_from_obj(obj)
                        return "", places, rinfo, text_field
                except Exception:
                    pass

    # 4. fenced code block (last)
    fenced_blocks = _re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", s)
    if fenced_blocks:
        raw_block = fenced_blocks[-1]
        cand = _balanced_first_object(raw_block)
        if cand:
            try:
                obj = json.loads(cand)
                if isinstance(obj, dict):
                    places, rinfo, text_field = _extract_from_obj(obj)
                    last_idx = s.rfind('```')
                    prefix = s[:last_idx].rstrip() if last_idx != -1 else s
                    return prefix, places, rinfo, text_field
            except Exception:
                pass

    # 5. regex object containing key of interest
    m = _re.search(r"(\{[\s\S]*?(?:\"places\"|\"place\"|\"route_info\")[\s\S]*?\})\s*(?:\[[0-9,\s]+\]\s*)*$", s)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                places, rinfo, text_field = _extract_from_obj(obj)
                return s[:m.start(1)].rstrip(), places, rinfo, text_field
        except Exception:
            pass

    # 6. heuristic broken places array recovery (simplified)
    mp = _re.search(r"(\{\s*\"(places|place)\"\s*:\s*\[)", s)
    if mp:
        head = s[:mp.start()]
        arr_tail = s[mp.end():]
        # collect object snippets
        objs=[]; i=0
        while i < len(arr_tail):
            if arr_tail[i] == '{':
                depth=1; j=i+1
                while j < len(arr_tail) and depth>0:
                    ch = arr_tail[j]
                    if ch=='"':
                        j+=1
                        while j < len(arr_tail):
                            if arr_tail[j]=='\\': j+=2; continue
                            if arr_tail[j]=='"': j+=1; break
                            j+=1
                        continue
                    elif ch=='{': depth+=1
                    elif ch=='}': depth-=1
                    j+=1
                if depth==0:
                    objs.append(arr_tail[i:j])
                    i=j
                    while i < len(arr_tail) and arr_tail[i] in ' \t\r\n,': i+=1
                    continue
                else:
                    break
            else:
                i+=1
        if objs:
            places=[]
            for o in objs:
                try: places.append(json.loads(o))
                except Exception: continue
            places=_normalize_places_list(places)
            if places:
                return head.rstrip(), places, None, None

    return s, None, None, None

def _normalize_grounding_meta(event: dict) -> dict:
    """Accepts an agent event and normalizes grounding metadata to snake_case keys.
    Returns dict with keys: grounding_chunks, grounding_supports, search_entry_point.
    Handles both camelCase and snake_case structures.
    """
    try:
        if not isinstance(event, dict):
            return {}
        meta = event.get('groundingMetadata') or event.get('grounding_metadata') or {}
        if not isinstance(meta, dict):
            return {}
        # Top-level lists
        chunks = meta.get('grounding_chunks')
        if chunks is None:
            chunks = meta.get('groundingChunks')
        supports = meta.get('grounding_supports')
        if supports is None:
            supports = meta.get('groundingSupports')

        # search entry point
        sep = meta.get('search_entry_point')
        if sep is None:
            sep = meta.get('searchEntryPoint')
        if isinstance(sep, dict):
            rendered = sep.get('rendered_content')
            if rendered is None:
                rendered = sep.get('renderedContent')
            queries = sep.get('web_search_queries')
            if queries is None:
                queries = sep.get('webSearchQueries')
            sep = {'rendered_content': rendered, 'web_search_queries': queries}
        else:
            sep = None

        return {
            'grounding_chunks': chunks or [],
            'grounding_supports': supports or [],
            'search_entry_point': sep or {}
        }
    except Exception:
        return {}

@app.before_request
def _start_timer():
    try:
        request._start_time = monotonic()
    except Exception:
        request._start_time = None
    try:
        request._trace_id = f"{random.getrandbits(64):016x}"
    except Exception:
        request._trace_id = None

@app.after_request
def _log_request(resp):  # type: ignore
    try:
        dur_ms = None
        if getattr(request, "_start_time", None) is not None:
            dur_ms = (monotonic() - request._start_time) * 1000
        path = request.path
        if path.startswith("/api/"):
            tid = getattr(request, "_trace_id", None)
            if tid:
                resp.headers["X-Trace-Id"] = tid
            logger.info(f"HTTP {request.method} {path} -> {resp.status_code} {int(dur_ms or 0)}ms trace={tid}")
    except Exception:
        pass
    return resp

# Gemini APIキーの設定
api_key = os.getenv("GEMINI_API_KEY")
genai_configured = bool(api_key and api_key != "YOUR_API_KEY_HERE")

if not genai_configured:
    logger.warning("GEMINI_API_KEY is not set or is a placeholder. The AI analysis will use dummy data.")
else:
    # ここでは genai.configure は呼び出しません。
    # REST API を直接呼び出すため、SDKの設定は不要です。
    logger.info("Gemini API key is set. Using REST API for AI analysis.")

# Agent microservice config (ADK api_server)
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL")  # e.g., http://localhost:8080 or Cloud Run URL
AGENT_API_KEY = os.getenv("AGENT_API_KEY")  # optional simple auth header if you set one

# Auth / DB config
FIRESTORE_PROJECT = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")

# JWT Secret 強化: 本番では未設定を許可しない
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"
logger.info(f"Starting server in {ENV.upper()} mode.")

_jwt_from_env = os.getenv("JWT_SECRET")
_jwt_from_env = os.getenv("JWT_SECRET")
if ENV.lower() == "development":
    JWT_SECRET = _jwt_from_env or "dev-secret-change-me"
else:
    if not _jwt_from_env or _jwt_from_env == "dev-secret-change-me":
        raise RuntimeError("JWT_SECRET environment variable must be set in production.")
    JWT_SECRET = _jwt_from_env

JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "2880"))  # 48h

# After ENV is known, apply dev fallback and compute configured flag
if not AGENT_BASE_URL and ENV.lower() == "development":
    AGENT_BASE_URL = "http://localhost:8080"
# dev 環境ではデフォルトで raw agent reply をフルログ（明示指定があればそれを優先）
if ENV.lower() == "development" and not os.getenv('AGENT_LOG_RAW'):
    os.environ['AGENT_LOG_RAW'] = 'full'
agent_configured = bool(AGENT_BASE_URL)
if agent_configured:
    logger.info(f"Agent base URL configured: {AGENT_BASE_URL}")

db = None
try:
    db = firestore.Client(project=FIRESTORE_PROJECT) if FIRESTORE_PROJECT else firestore.Client()
    logger.info("Firestore client initialized.")
except Exception as e:
    logger.warning(f"Firestore client init failed: {e}")
    db = None

# Development fallback: in-memory DB when Firestore is unavailable
if db is None and (os.getenv("FLASK_ENV", "").lower() == "development" or os.getenv("ENV", "").lower() == "development"):
    import uuid
    from copy import deepcopy

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
        def __init__(self, store, path):
            self._store = store
            self._path = path  # tuple of segments
            self.id = path[-1] if path else None

        def _now_iso(self):
            return datetime.utcnow().isoformat() + "Z"

        def _resolve(self):
            cur = self._store
            for seg in self._path:
                cur = cur.setdefault(seg, {})
            return cur

        def get(self, *args, **kwargs):
            node = self._resolve()
            data = node.get("__doc__")
            return _DevDocSnapshot(data)

        def set(self, data, *args, **kwargs):
            node = self._resolve()
            doc = deepcopy(data)
            # replace Firestore server timestamps if present
            for k, v in list(doc.items()):
                if v is getattr(firestore, "SERVER_TIMESTAMP", object()):
                    doc[k] = self._now_iso()
            node["__doc__"] = doc

        def update(self, data, *args, **kwargs):
            node = self._resolve()
            base = node.get("__doc__", {})
            for k, v in data.items():
                base[k] = v
            node["__doc__"] = base

        def collection(self, name):
            return _DevCollectionRef(self._store, self._path + (name,))

    class _DevCollectionRef:
        def __init__(self, store, path):
            self._store = store
            self._path = path  # tuple of segments

        def document(self, doc_id=None):
            if not doc_id:
                doc_id = uuid.uuid4().hex
            # ensure collection container exists
            cur = self._store
            for seg in self._path:
                cur = cur.setdefault(seg, {})
            # create doc node
            cur.setdefault(doc_id, {})
            return _DevDocumentRef(self._store, self._path + (doc_id,))

        def stream(self):
            """Stream all documents in the collection for DevDB compatibility with Firestore"""
            # Navigate to the collection in the store
            cur = self._store
            for seg in self._path:
                cur = cur.get(seg, {})
                if not isinstance(cur, dict):
                    return  # Collection doesn't exist
            
            # Yield document snapshots for each document in the collection
            for doc_id, doc_data in cur.items():
                if isinstance(doc_data, dict) and "__doc__" in doc_data:
                    doc_ref = _DevDocumentRef(self._store, self._path + (doc_id,))
                    doc_snapshot = _DevDocSnapshot(doc_data["__doc__"])
                    # Set the document ID on the snapshot to match Firestore behavior
                    doc_snapshot.id = doc_id
                    yield doc_snapshot

    class DevDB:
        def __init__(self):
            self._store = {}

        def collection(self, name):
            return _DevCollectionRef(self._store, (name,))

    db = DevDB()
    logger.info("DevDB initialized (in-memory). Firestore is not used in development mode.")

# 簡易ヘルスチェック
@app.route('/api/health', methods=['GET'])
def health():
    try:
        db_kind = 'unknown'
        if db is not None:
            db_kind = 'firestore'
            # DevDB クラス名で判断
            if type(db).__name__ == 'DevDB':
                db_kind = 'devdb'
        return jsonify({
            "status": "ok",
            "env": ENV,
            "db": db_kind,
            "gemini_configured": genai_configured,
            "jwt_configured": bool(JWT_SECRET),
            "agent_json_metrics": {"ok": AGENT_JSON_OK, "fail": AGENT_JSON_FAIL}
        })
    except Exception as e:
        logger.exception("/api/health error")
        return jsonify({"status": "error", "message": str(e)}), 500

def create_jwt(user_id: str):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MIN)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_jwt_with_ttl(user_id: str, ttl_min: int):
    now = datetime.now(timezone.utc)
    ttl_min = max(1, min(int(ttl_min or 15), 24 * 60))
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_min)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def require_auth(req):
    authz = req.headers.get("Authorization", "")
    if authz.startswith("Bearer "):
        token = authz.split(" ", 1)[1]
        return verify_jwt(token)
    return None

def _claims_or_dev():
    """Return JWT claims if present; in development, fall back to a dummy dev user.
    This avoids 401 spam in local no-auth sessions.
    """
    claims = require_auth(request)
    if claims:
        return claims
    if (os.getenv("FLASK_ENV", "").lower() == "development") or (ENV.lower() == "development"):
        return { 'sub': 'devuser' }
    return None


@app.get('/api/maps-key')
def get_maps_js_key():
    """Expose Google Maps JavaScript API key to the client.
    It is expected to be public on the frontend. Prefer VITE_GOOGLE_MAPS_API_KEY, fallback to GOOGLE_MAPS_API_KEY.
    """
    key = os.getenv('VITE_GOOGLE_MAPS_API_KEY') or os.getenv('GOOGLE_MAPS_API_KEY') or ''
    # avoid returning placeholder text
    if key == 'YOUR_API_KEY_HERE':
        key = ''
    # sanitize: 改行漏れやURLエンコードされた連結を切り落とす
    try:
        key = (key or '').strip()
        # 代表的なセパレータで最初に分割
        for sep in ['FLASK_ENV', 'ENV=', '%3D', '&', '?', '\n', '\r']:
            if sep in key:
                key = key.split(sep)[0].strip()
        # 許可文字以外で早期終了
        import re as _re
        m = _re.match(r'^([A-Za-z0-9_\-]+)', key)
        if m:
            key = m.group(1)
    except Exception:
        pass
    # mapId の取得とサニタイズ（Advanced Marker で推奨）
    map_id = os.getenv('VITE_GOOGLE_MAPS_MAP_ID') or os.getenv('GOOGLE_MAPS_MAP_ID') or ''
    try:
        map_id = (map_id or '').strip()
        import re as _re
        m2 = _re.match(r'^([A-Za-z0-9_\-]+)', map_id)
        if m2:
            map_id = m2.group(1)
    except Exception:
        pass
    # Advanced Marker の有効化フラグ（サーバー側で制御可能）
    adv_env = (
        os.getenv('ENABLE_ADVANCED_MARKER')
        or os.getenv('VITE_ENABLE_ADVANCED_MARKER')
        or os.getenv('GOOGLE_MAPS_ENABLE_ADVANCED_MARKER')
        or ''
    )
    adv = str(adv_env).strip().lower() in ['1','true','yes','on']
    # mapId 未設定なら Advanced を無効化（警告抑止と確実性のため）
    if not map_id:
        adv = False
    return jsonify({ 'key': key, 'mapId': map_id, 'advanced': adv })



# レポートに基づいた10個全ての質問データ
QUESTIONS = [
    {
        "id": 1,
        "trait": "新規性追求",
        "trait_description": "新しい、未知の体験をどれだけ好むかを示します。スコアが高いほど、冒険的で型にはまらない旅を求める傾向があります。",
        "question": "あなたの理想の旅に最も近いのはどれですか？",
        "options": [
            {"text": "すべて手配済みの人気観光地への快適なパッケージツアー。", "score": 1},
            {"text": "有名な都市のホテルに滞在し、自分で名所を巡る旅。", "score": 2},
            {"text": "あまり知られていない地域へ自ら手配し、定番から外れた体験を目指す旅。", "score": 3},
            {"text": "観光インフラが未整備な地域へ赴き、現地の生活に完全に溶け込む旅。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "最も「生きている」と感じた旅の思い出を教えてください。何が特別でしたか？",
        "free_text_placeholder": "例：誰もいない早朝のビーチで、水平線から昇る朝日を独り占めした時。"
    },
    {
        "id": 2,
        "trait": "旅程密度",
        "trait_description": "旅行中にどれだけ多くの活動を詰め込みたいかを示します。スコアが高いほど、多くの体験を効率的にこなすことを好む傾向があります。",
        "question": "旅行中の1日の過ごし方として、どちらを好みますか？",
        "options": [
            {"text": "1つの場所に腰を据え、何もしない贅沢を味わう。", "score": 1},
            {"text": "主な見どころをいくつか、ゆったりしたペースで巡る。", "score": 2},
            {"text": "効率的に計画を立て、多くのスポットや体験を組み合わせる。", "score": 3},
            {"text": "朝から晩まで、分刻みのスケジュールで活動的に動き回る。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "理想的な旅行の1日を、朝起きてから寝るまでどのように過ごしたいですか？",
        "free_text_placeholder": "例：朝はカフェでゆっくり過ごし、午後は美術館へ。夜は地元の人気レストランでディナー。"
    },
    {
        "id": 3,
        "trait": "予算哲学",
        "trait_description": "旅行におけるお金の使い方に関する考え方を示します。スコアが高いほど、価格よりも体験の質を重視する傾向があります。",
        "question": "旅行の計画を立てる際、予算についてどのように考えますか？",
        "options": [
            {"text": "最も重要なのは価格。常に最もお得な選択肢を探す。", "score": 1},
            {"text": "予算内で最大限の価値を得られるよう、コストパフォーマンスを重視する。", "score": 2},
            {"text": "素晴らしい体験のためなら、多少予算を超えても構わない。", "score": 3},
            {"text": "予算は二の次。最高の体験を得るために必要な費用は惜しまない。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "「これはお金をかけて良かった」と感じた旅行体験は何ですか？その理由も教えてください。",
        "free_text_placeholder": "例：少し高かったけど、熱気球から見た朝焼けの景色は一生の思い出になった。"
    },
    {
        "id": 4,
        "trait": "社会的志向性",
        "trait_description": "旅行中に他人とどの程度関わりたいかを示します。スコアが高いほど、現地の人や他の旅行者との交流を積極的に求める傾向があります。",
        "question": "旅行先で、どのような人との関わり方を好みますか？",
        "options": [
            {"text": "できるだけ人と関わらず、一人の時間を静かに楽しみたい。", "score": 1},
            {"text": "同行者との時間を大切にし、グループ内での交流を深めたい。", "score": 2},
            {"text": "他の旅行者と情報交換したり、食事を共にしたりするのも楽しい。", "score": 3},
            {"text": "現地の人々と積極的に交流し、その土地の文化を肌で感じたい。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "旅行先で誰かと交流して楽しかった経験があれば教えてください。",
        "free_text_placeholder": "例：ゲストハウスで出会った旅行者と意気投合し、一緒に観光したこと。"
    },
    {
        "id": 5,
        "trait": "主な興味関心",
        "trait_description": "旅行の主な目的が何であるかを示します。スコアはリラックス(1)→食事(2)→自然(3)→文化(4)という軸で評価されますが、グラフでは総合的な興味の方向性として解釈されます。",
        "question": "旅行の最大の目的となることが多いのは、次のうちどれですか？",
        "options": [
            {"text": "日常を忘れて心身ともにリラックスすること。", "score": 1},
            {"text": "その土地ならではの美味しい食事やお酒を堪能すること。", "score": 2},
            {"text": "美しい自然の風景や野生動物との出会いを楽しむこと。", "score": 3},
            {"text": "美術館や史跡を巡り、歴史や文化に触れること。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "これまでの旅行で最も情熱を注いだテーマ（食、アート、自然など）と、その具体的なエピソードを教えてください。",
        "free_text_placeholder": "例：ラーメンが好きで、旅行先では必ず地元の人気店を3軒以上はしごします。"
    },
    {
        "id": 6,
        "trait": "計画志向性",
        "trait_description": "旅行をどの程度詳細に計画するかを示します。スコアが高いほど、事前の計画を重視し、スケジュール通りに行動することを好む傾向があります。",
        "question": "旅行の計画はどの程度立てますか？",
        "options": [
            {"text": "ほとんど計画せず、その場の気分や出会いを大切にする。", "score": 1},
            {"text": "大まかな行き先だけ決め、詳細は現地で決めることが多い。", "score": 2},
            {"text": "行きたい場所ややりたいことをリストアップし、大まかな日程を組む。", "score": 3},
            {"text": "交通機関やレストランまで予約し、詳細な旅程表を作成する。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "計画通りに進まなかったけれど、結果的に最高の思い出になった経験はありますか？",
        "free_text_placeholder": "例：乗る予定のバスを逃したが、そのおかげで素敵なカフェを見つけられた。"
    },
    {
        "id": 7,
        "trait": "快適性水準",
        "trait_description": "宿泊施設や移動手段にどれだけの快適さを求めるかを示します。スコアが高いほど、快適さや豪華さを重視する傾向があります。",
        "question": "宿泊施設を選ぶ際に、最も重視する点は何ですか？",
        "options": [
            {"text": "価格と立地。寝るだけなので最低限の設備で十分。", "score": 1},
            {"text": "清潔で安全、かつ機能的であること。", "score": 2},
            {"text": "デザイン性が高く、快適なアメニティやサービスが揃っていること。", "score": 3},
            {"text": "スパや高級レストランなど、施設内で特別な体験ができること。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "今までで最高のホテル体験と、その理由を教えてください。",
        "free_text_placeholder": "例：部屋の窓から見える景色が素晴らしく、朝食も美味しかったホテル。"
    },
    {
        "id": 8,
        "trait": "活動レベル",
        "trait_description": "旅行中にどれだけ身体を動かすことを好むかを示します。スコアが高いほど、ハイキングやスポーツなどのアクティブな活動を求める傾向があります。",
        "question": "旅行中の身体活動について、あなたの好みはどれですか？",
        "options": [
            {"text": "ほとんど歩き回らず、乗り物や施設内でゆったり過ごしたい。", "score": 1},
            {"text": "のんびり散策したり、景色を楽しんだりする程度が心地よい。", "score": 2},
            {"text": "街歩きや軽いハイキングなど、積極的に体を動かしたい。", "score": 3},
            {"text": "登山やマリンスポーツなど、挑戦的なアクティビティを楽しみたい。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "旅行先で体を動かして楽しかったアクティビティは何ですか？",
        "free_text_placeholder": "例：初めて挑戦したカヤックで、川の上からの景色を楽しんだこと。"
    },
    {
        "id": 9,
        "trait": "安全性の閾値",
        "trait_description": "旅行先の安全性やリスクをどの程度重視するかを示します。スコアが高いほど、安全性を最優先し、リスクを避ける傾向があります。",
        "question": "新しい旅行先を選ぶ際、安全性についてどの程度考慮しますか？",
        "options": [
            {"text": "あまり気にしない。多少のリスクは冒険の一部だと考える。", "score": 1},
            {"text": "一般的な観光地であれば、特に問題ないだろうと考える。", "score": 2},
            {"text": "事前に外務省の安全情報などを確認し、治安の良い地域を選ぶ。", "score": 3},
            {"text": "医療体制や衛生環境を含め、最高レベルの安全が確保されている場所を選ぶ。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "旅行の準備で、安全のために特別に行っていることはありますか？",
        "free_text_placeholder": "例：海外旅行では、スリ対策のために体の前にかけるバッグを使っている。"
    },
    {
        "id": 10,
        "trait": "デジタル統合度",
        "trait_description": "旅行中にスマートフォンやアプリなどのテクノロジーをどの程度活用するかを示します。スコアが高いほど、テクノロジーを駆使して旅を効率化・記録することを好む傾向があります。",
        "question": "旅行中にテクノロジーをどのように活用しますか？",
        "options": [
            {"text": "デジタルデトックスを好み、スマホやPCはほとんど使わない。", "score": 1},
            {"text": "地図アプリや翻訳アプリなど、必要最低限のツールのみ利用する。", "score": 2},
            {"text": "予約管理、情報収集、SNS投稿など、積極的にテクノロジーを活用する。", "score": 3},
            {"text": "最新のガジェットやアプリを駆使し、旅の全てを記録・最適化する。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "あなたの旅行を劇的に便利にしたアプリやウェブサイトがあれば教えてください。",
        "free_text_placeholder": "例：Google Mapsのオフライン機能のおかげで、電波がない場所でも迷わなかった。"
    }
]

# 趣味マスタ（likesOptions と同等のデータ）
HOBBIES_MASTER = [
    { "id": "onsen", "label": "温泉・サウナ", "emoji": "♨️", "weights": { "comfort": 0.6, "pace": -0.2 } },
    { "id": "relax", "label": "リラックス・スパ", "emoji": "🧖", "weights": { "comfort": 0.8, "activity": -0.4, "pace": -0.4 } },
    { "id": "art", "label": "アート・美術館", "emoji": "🖼️", "weights": { "culture": 0.7, "novelty": 0.1 } },
    { "id": "history", "label": "歴史・世界遺産", "emoji": "🏛️", "weights": { "culture": 0.8 } },
    { "id": "nature", "label": "自然・絶景", "emoji": "🏞️", "weights": { "nature": 0.8, "activity": 0.2 } },
    { "id": "gourmet", "label": "グルメ・食べ歩き", "emoji": "🍣", "weights": { "gourmet": 0.8, "comfort": 0.1 } },
    { "id": "citywalk", "label": "まち歩き", "emoji": "🚶", "weights": { "activity": 0.4, "culture": 0.2 } },
    { "id": "adventure", "label": "アドベンチャー", "emoji": "🧗", "weights": { "novelty": 0.6, "risk": 0.4, "activity": 0.6 } },
    { "id": "themepark", "label": "テーマパーク", "emoji": "🎢", "weights": { "comfort": 0.2, "pace": 0.2 } },
    { "id": "island", "label": "離島ステイ", "emoji": "🏝️", "weights": { "nature": 0.6, "novelty": 0.3, "comfort": 0.2 } },
    { "id": "snow", "label": "雪・ウィンター", "emoji": "❄️", "weights": { "activity": 0.4, "risk": 0.2, "comfort": -0.1 } },
    { "id": "festival", "label": "祭り・イベント", "emoji": "🎊", "weights": { "social": 0.6, "culture": 0.2 } },

    { "id": "pilgrimage", "label": "聖地巡礼（アニメ・ドラマ）", "emoji": "🎬", "weights": { "culture": 0.5, "novelty": 0.3, "planning": 0.2 } },
    { "id": "cafe", "label": "カフェめぐり", "emoji": "☕", "weights": { "gourmet": 0.6, "comfort": 0.2, "pace": -0.1 } },
    { "id": "coffee", "label": "コーヒー巡り", "emoji": "☕", "weights": { "gourmet": 0.5, "comfort": 0.2, "pace": -0.1 } },
    { "id": "sweets", "label": "スイーツ巡り", "emoji": "🍰", "weights": { "gourmet": 0.5, "comfort": 0.2 } },
    { "id": "bakery", "label": "ベーカリー巡り", "emoji": "🍞", "weights": { "gourmet": 0.4, "comfort": 0.2, "pace": -0.1 } },
    { "id": "ramen", "label": "ラーメン", "emoji": "🍜", "weights": { "gourmet": 0.5 } },
    { "id": "sushi_love", "label": "寿司巡り", "emoji": "🍣", "weights": { "gourmet": 0.5 } },
    { "id": "wagashi", "label": "和菓子", "emoji": "🍡", "weights": { "gourmet": 0.4, "culture": 0.2 } },
    { "id": "craftbeer", "label": "クラフトビール", "emoji": "🍺", "weights": { "gourmet": 0.4, "social": 0.3 } },
    { "id": "wine", "label": "ワイン", "emoji": "🍷", "weights": { "gourmet": 0.4, "comfort": 0.2 } },
    { "id": "sake", "label": "日本酒", "emoji": "🍶", "weights": { "gourmet": 0.4, "culture": 0.2 } },
    { "id": "vegan", "label": "ヴィーガン対応", "emoji": "🥦", "weights": { "gourmet": 0.2, "planning": 0.2, "comfort": 0.1 } },

    { "id": "shrines", "label": "神社仏閣", "emoji": "⛩️", "weights": { "culture": 0.6, "pace": -0.1 } },
    { "id": "goshuin", "label": "御朱印集め", "emoji": "📖", "weights": { "culture": 0.5, "planning": 0.2 } },
    { "id": "castles", "label": "城めぐり", "emoji": "🏯", "weights": { "culture": 0.6, "activity": 0.2 } },
    { "id": "hanabi", "label": "花火", "emoji": "🎆", "weights": { "social": 0.3, "culture": 0.2 } },
    { "id": "sakura", "label": "桜", "emoji": "🌸", "weights": { "nature": 0.4, "culture": 0.2 } },
    { "id": "momiji", "label": "紅葉", "emoji": "🍁", "weights": { "nature": 0.5, "activity": 0.1, "pace": -0.1 } },
    { "id": "waterfalls", "label": "滝めぐり", "emoji": "🏞️", "weights": { "nature": 0.6, "activity": 0.3, "risk": 0.1 } },
    { "id": "stargazing", "label": "星空観察", "emoji": "🌌", "weights": { "nature": 0.5, "pace": -0.2 } },
    { "id": "nightview", "label": "夜景・イルミ", "emoji": "🌃", "weights": { "culture": 0.2, "novelty": 0.1, "comfort": 0.1 } },
    { "id": "aquarium", "label": "水族館", "emoji": "🐠", "weights": { "culture": 0.2, "comfort": 0.2 } },
    { "id": "zoo", "label": "動物園・牧場", "emoji": "🦁", "weights": { "nature": 0.3, "social": 0.2 } },

    { "id": "kids", "label": "子連れに優しい", "emoji": "👨‍👩‍👧", "weights": { "comfort": 0.4, "risk": 0.2, "pace": -0.2 } },
    { "id": "pet", "label": "ペット同伴OK", "emoji": "🐶", "weights": { "comfort": 0.2, "planning": 0.2, "nature": 0.2 } },
    { "id": "couple", "label": "カップル向け", "emoji": "💑", "weights": { "comfort": 0.2, "gourmet": 0.2, "pace": -0.1 } },
    { "id": "girls", "label": "女子旅", "emoji": "👭", "weights": { "gourmet": 0.3, "culture": 0.2 } },
    { "id": "solo", "label": "ひとり旅", "emoji": "🧍", "weights": { "novelty": 0.2, "planning": 0.1, "comfort": -0.1 } },
    { "id": "photography", "label": "写真撮影", "emoji": "📸", "weights": { "nature": 0.3, "culture": 0.2, "planning": 0.1 } },
    { "id": "instaspot", "label": "映えスポット", "emoji": "✨", "weights": { "digital": 0.3, "novelty": 0.2, "culture": 0.1 } },

    { "id": "surf", "label": "サーフィン", "emoji": "🏄", "weights": { "activity": 0.7, "risk": 0.3, "nature": 0.3 } },
    { "id": "sup", "label": "SUP・カヤック", "emoji": "🛶", "weights": { "activity": 0.6, "nature": 0.3 } },
    { "id": "snorkel", "label": "シュノーケリング", "emoji": "🤿", "weights": { "activity": 0.6, "nature": 0.4 } },
    { "id": "ski", "label": "スキー・スノボ", "emoji": "🎿", "weights": { "activity": 0.7, "risk": 0.3, "nature": 0.3 } },
    { "id": "hike", "label": "ハイキング", "emoji": "🥾", "weights": { "activity": 0.5, "nature": 0.5 } },
    { "id": "climb", "label": "登山", "emoji": "⛰️", "weights": { "activity": 0.7, "risk": 0.3, "nature": 0.4 } },
    { "id": "trailrun", "label": "トレイルラン", "emoji": "🏃‍♂️", "weights": { "activity": 0.7, "risk": 0.2, "nature": 0.3 } },
    { "id": "cycle", "label": "サイクリング", "emoji": "🚴", "weights": { "activity": 0.5, "nature": 0.3 } },
    { "id": "drive", "label": "ドライブ", "emoji": "🚗", "weights": { "comfort": 0.2, "activity": 0.2 } },

    { "id": "rail", "label": "鉄道旅", "emoji": "🚆", "weights": { "culture": 0.2, "planning": 0.3, "comfort": 0.1 } },
    { "id": "scenic_train", "label": "絶景列車", "emoji": "🚞", "weights": { "nature": 0.3, "comfort": 0.2 } },
    { "id": "ferry", "label": "フェリー旅", "emoji": "⛴️", "weights": { "comfort": 0.2, "nature": 0.2 } },
    { "id": "cruise", "label": "クルーズ", "emoji": "🚢", "weights": { "comfort": 0.6, "pace": -0.2 } },

    { "id": "craft", "label": "伝統工芸体験", "emoji": "🎎", "weights": { "culture": 0.6, "novelty": 0.2, "activity": 0.1 } },
    { "id": "pottery", "label": "陶芸体験", "emoji": "🏺", "weights": { "culture": 0.5, "activity": 0.2 } },
    { "id": "kintsugi", "label": "金継ぎ", "emoji": "🪡", "weights": { "culture": 0.5, "planning": 0.2 } },
    { "id": "dyeing", "label": "染物体験", "emoji": "🧶", "weights": { "culture": 0.5 } },
    { "id": "sushi_making", "label": "寿司握り体験", "emoji": "🍣", "weights": { "gourmet": 0.4, "culture": 0.3, "activity": 0.1 } },
    { "id": "tea", "label": "茶道・抹茶体験", "emoji": "🍵", "weights": { "culture": 0.6, "pace": -0.2 } },
    { "id": "kimono", "label": "着物レンタル", "emoji": "👘", "weights": { "culture": 0.5, "digital": 0.1 } },
    { "id": "markets", "label": "朝市・市場", "emoji": "🧺", "weights": { "gourmet": 0.4, "culture": 0.2, "pace": 0.1 } },
    { "id": "outlet", "label": "アウトレット・ショッピング", "emoji": "🛍️", "weights": { "budget": 0.3, "comfort": 0.2 } },
    { "id": "thrift", "label": "古着・蚤の市", "emoji": "👗", "weights": { "budget": 0.2, "novelty": 0.2, "culture": 0.2 } },
    { "id": "tech", "label": "テック・ガジェット巡り", "emoji": "📱", "weights": { "digital": 0.6, "novelty": 0.2 } },
    { "id": "science_museum", "label": "科学館・博物館", "emoji": "🧪", "weights": { "culture": 0.5 } },
    { "id": "concept_cafe", "label": "コンセプトカフェ", "emoji": "🧋", "weights": { "social": 0.2, "culture": 0.2, "novelty": 0.2 } },

    { "id": "yoga", "label": "ヨガ・ウェルネス", "emoji": "🧘", "weights": { "comfort": 0.6, "activity": 0.2, "pace": -0.3 } },
]

@app.route('/api/hobbies', methods=['GET'])
def list_hobbies_master():
    """趣味マスタを返す。DBに未保存ならシードして返す。
    形式: { items: [ {id,label,emoji,weights}, ... ] }
    """
    try:
        meta_ref = db.collection('meta').document('hobbies_master')
        snap = meta_ref.get(timeout=5)
        if snap and snap.exists:
            data = snap.to_dict() or {}
            items = data.get('items')
            if isinstance(items, list) and items:
                return jsonify({"items": items})
        # seed
        to_save = { 'items': HOBBIES_MASTER, 'updated_at': firestore.SERVER_TIMESTAMP }
        meta_ref.set(to_save, timeout=5)
        return jsonify({"items": HOBBIES_MASTER})
    except Exception as e:
        logger.exception("/api/hobbies error")
        # フォールバック: 定数を返す
        return jsonify({"items": HOBBIES_MASTER})

@app.route('/api/questions')
def get_questions():
    return jsonify(QUESTIONS)

def call_gemini_api(prompt, model_name='gemini-2.5-flash'):
    """
    Gemini APIをRESTで呼び出す共通関数。503エラー時は自動リトライを行う。
    """
    if not genai_configured:
        raise Exception("GEMINI_API_KEY is not configured.")

    def _make_request():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key
        }
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() # HTTPエラーがあれば例外を発生させる
        
        # APIからのレスポンスを直接JSONとしてパース
        return response.json()
    
    return retry_on_503(_make_request)

def call_agent_plan(persona: dict, profile: dict | None = None, constraints: dict | None = None, timeout_sec: int = 30):
    """
    Agent サービスの /v1/plan を呼び出す。503エラー時は自動リトライを行う。
    persona: { title: str, description: str, traitScores?: dict }
    """
    if not agent_configured:
        raise Exception("Agent base URL is not configured.")
    
    def _make_request():
        url = AGENT_BASE_URL.rstrip('/') + '/v1/plan'
        headers = { 'Content-Type': 'application/json' }
        if AGENT_API_KEY:
            headers['Authorization'] = f"Bearer {AGENT_API_KEY}"
        payload = {
            "persona": persona,
        }
        if profile:
            payload["profile"] = profile
        if constraints:
            payload["constraints"] = constraints
        
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        resp.raise_for_status()
        return resp.json()
    
    return retry_on_503(_make_request)

def call_adk_agent_chat(app_name: str, user_id: str, session_id: str, message_text: str, timeout_sec: int = 60, base_url: str | None = None, ensure_session: bool = True):
    """ADK api_server に従った呼び出し手順でチャット実行。
    1) /list-apps で存在を確認（任意）
    2) /apps/{app_name}/users/{user_id}/sessions/{session_id} に空ボディPOSTでセッション作成
    3) /run に { app_name, user_id, session_id, new_message } をPOST
    戻り値: events配列（最終応答はevents内のmodelメッセージ）
    """
    if not (base_url or AGENT_BASE_URL):
        raise Exception("Agent base URL is not configured.")
    base = (base_url or AGENT_BASE_URL).rstrip('/')
    headers = { 'Content-Type': 'application/json' }
    if AGENT_API_KEY:
        headers['Authorization'] = f"Bearer {AGENT_API_KEY}"

    bridge_logger = logging.getLogger("agent_bridge")

    # 2) セッション作成（初回のみ／冪等）
    if ensure_session:
        def _create_session():
            sess_url = f"{base}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
            bridge_logger.info(f"Create session: POST {sess_url}")
            r = requests.post(sess_url, headers=headers, json={}, timeout=timeout_sec)
            text_snip = (r.text[:300] + '…') if (getattr(r, 'text', None) and len(r.text) > 300) else (r.text or '')
            already_exists = (r.status_code == 400 and isinstance(r.text, str) and 'session already exists' in r.text.lower())
            if 200 <= r.status_code < 300 or r.status_code == 409 or already_exists:
                if already_exists:
                    bridge_logger.info(f"Create session OK (already exists): {r.status_code} body={text_snip}")
                else:
                    bridge_logger.info(f"Create session OK: {r.status_code}")
                return r
            else:
                bridge_logger.error(f"Create session unexpected status: {r.status_code} body={text_snip}")
                r.raise_for_status()
            return r
            
        try:
            retry_on_503(_create_session)
        except Exception as e:
            bridge_logger.error(f"Create session failed: {e}")
            raise RuntimeError(f"Failed to create session: {e}")
    else:
        bridge_logger.info("Skip create session (already initialized on server side)")

    # 3) 実行
    def _run_agent():
        run_url = f"{base}/run"
        # 強制的にJSON-onlyを促す前置き注記（モデル/サーバ側が対応すればMIME強制に近い効果）
        prefix = (
            "以下の応答は、単一のJSONオブジェクトのみで返してください。"
            "前後に説明やコードフェンス、余分な空白・句読点を一切付けないでください。\n"
            "必ず次のスキーマに厳密に従ってください。\n"
            "{\n"
            "  \"text\": \"ユーザーへ見せる本文。GFMのMarkdownを使用可（見出し・箇条書き・表）。表はパイプ区切りのMarkdownテーブルで記述してください。\",\n"
            "  \"places\": [ { \"name\": string, \"lat\": number|null, \"lng\": number|null, \"note\": string|null, \"url\": string|null } ] (省略可),\n"
            "  \"route_info\": { \"origin\": string, \"destination\": string, \"waypoints\": [string], \"mode\": \"driving|walking|bicycling|transit\" } (省略可)\n"
            "}\n\n"
            "注意: \n"
            "- 本文(text)にリストや比較を載せる場合はMarkdownテーブルを活用してください。\n"
        "- 旅行日程(スケジュール)は、可能なら以下の列を持つ表で提示してください: アイコン|時間|予定|詳細|[その他(場所/費用/備考など)]。\n"
            "- URLは本文かplaces.urlに含められます。\n"
        )
        payload = {
            "app_name": app_name,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": { "role": "user", "parts": [{"text": prefix + message_text}] }
        }
        bridge_logger.info(f"Run agent: POST {run_url} app={app_name} user={user_id} session={session_id} msg_len={len(message_text)}")
        if LOG_PAYLOADS:
            try:
                bridge_logger.info(f"Run payload: {_snip_json(payload)}")
            except Exception:
                pass
                
        r2 = requests.post(run_url, headers=headers, json=payload, timeout=timeout_sec)
        r2.raise_for_status()
        return r2
        
    t0 = monotonic()
    try:
        r2 = retry_on_503(_run_agent)
    except requests.RequestException as e:
        dt = (monotonic() - t0) * 1000
        status = getattr(getattr(e, 'response', None), 'status_code', 'n/a')
        body = None
        try:
            body = e.response.text if getattr(e, 'response', None) is not None else None
        except Exception:
            body = None
        body_snip = (body[:500] + '…') if body and len(body) > 500 else (body or '')
        bridge_logger.error(f"Run agent failed: status={status} {int(dt)}ms body={body_snip}")
        raise

    # 成功時の処理
    dt = (monotonic() - t0) * 1000
    j = r2.json()
    bridge_logger.info(f"Run agent OK: {r2.status_code} {int(dt)}ms events={len(j) if isinstance(j, list) else 'n/a'}")
    bridge_logger.debug(f"Raw agent response: {_snip_json(j)}")
    if LOG_PAYLOADS:
        try:
            if FULL_PAYLOAD:
                bridge_logger.info(f"Run response(full): {_snip_json(j)}")
            else:
                bridge_logger.info(f"Run response: {_snip_text(_snip_json(j), 1200)}")
        except Exception:
            pass
    return j

def _extract_locations_via_llm(reply_text: str, user_id: str, session_id: str, timeout_sec: int = 30):
    """第二段: 本文から場所とルートを抽出するために、非エージェントのLLM（Gemini REST）を優先して使用。
    返信は JSON オブジェクトのみを期待。失敗時は (None, None) を返す。
    """
    try:
        # 1) Gemini REST を優先
        if genai_configured:
            model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
            prompt = (
                "以下の文章から、旅行に関係する場所候補（places）と任意のルート情報（route_info）を抽出してください。\n"
                "要件:\n"
                "- 出力は JSON オブジェクトのみ（前後に説明やコードフェンスを付けない）\n"
                "- 形式: {\"places\":[{\"name\":\"…\",\"lat\":null,\"lng\":null,\"note\":\"…\",\"url\":null,\"imageUrl\":null,\"iconUrl\":null,\"label\":null,\"color\":null,\"address\":null}], \"route_info\":{\"origin\":\"…\",\"destination\":\"…\",\"waypoints\":[""],\"mode\":\"driving|walking|bicycling|transit\"}}\n"
                "- places は最大10件。name は自然言語の地名・施設名。lat/lng が不明なら null。\n"
                "- route_info は存在する場合のみ。waypoints は文字列の配列で良い。\n\n"
                "[対象テキスト]\n" + (reply_text or "")
            )
            try:
                resp = call_gemini_api(prompt, model_name=model)
                text_out = ''
                try:
                    for c in (resp.get('candidates') or []):
                        parts = ((c.get('content') or {}).get('parts') or [])
                        for p in parts:
                            t = p.get('text')
                            if isinstance(t, str):
                                text_out += t
                except Exception:
                    text_out = ''
                places, route_info = None, None
                if isinstance(text_out, str) and text_out.strip():
                    try:
                        obj = json.loads(text_out.strip())
                        places = obj.get('places') if isinstance(obj, dict) else None
                        if places is None and isinstance(obj, dict):
                            places = obj.get('place')
                        route_info = obj.get('route_info') if isinstance(obj, dict) else None
                        if route_info is None and isinstance(obj, dict):
                            route_info = obj.get('route') or obj.get('routeInfo')
                        places = _normalize_places_list(places)
                        route_info = _normalize_route_info(route_info)
                    except Exception:
                        try:
                            # フェンス/余白混入時は末尾抽出で救済
                            _, places, route_info = _extract_trailing_json(text_out.strip())
                        except Exception:
                            places, route_info = None, None
                if places is not None or route_info is not None:
                    return places, route_info
            except Exception as e:
                logging.getLogger('extract').warning(f"Gemini extraction failed: {e}")

        # 2) フォールバック: （オプション）ADKエージェントに抽出依頼（利用不可や失敗時はスキップ）
        try:
            extract_sid = f"{session_id}-extract"
            prompt2 = (
                "以下の文章から、旅行に関係する場所候補（places）と任意のルート情報（route_info）を抽出してください。\n"
                "出力は JSON オブジェクトのみで、説明やコードフェンスは不要です。\n\n"
                "[対象テキスト]\n" + (reply_text or "")
            )
            events = call_adk_agent_chat('root_coordinator', user_id, extract_sid, prompt2, timeout_sec=timeout_sec, ensure_session=True)
            if isinstance(events, list) and events:
                final_event = events[-1]
                content = final_event.get('content') or {}
                if content.get('role') == 'model':
                    text = "\n".join(p.get('text', '') for p in (content.get('parts') or []))
                    try:
                        _, places, route_info = _extract_trailing_json(text.strip())
                        if places is not None or route_info is not None:
                            return places, route_info
                    except Exception:
                        pass
        except Exception as e:
            logging.getLogger('extract').warning(f"Agent fallback extraction failed: {e}")

        return None, None
    except Exception as e:
        logging.getLogger('extract').warning(f"LLM extraction wrapper failed: {e}")
        return None, None

# ---- Session initialization tracking (first-message detection) ----
_primed_sessions = set()

def _session_key(user_id: str, session_id: str) -> str:
    return f"{user_id}::{session_id}"

def is_session_initialized(user_id: str, session_id: str) -> bool:
    key = _session_key(user_id, session_id)
    if key in _primed_sessions:
        return True
    try:
        if db is not None:
            doc = db.collection('agent_sessions').document(key).get(timeout=3)
            if getattr(doc, 'exists', False):
                d = doc.to_dict() or {}
                return bool(d.get('initialized'))
    except Exception:
        pass
    return False

def mark_session_initialized(user_id: str, session_id: str):
    key = _session_key(user_id, session_id)
    _primed_sessions.add(key)
    try:
        if db is not None:
            db.collection('agent_sessions').document(key).set({
                'initialized': True,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            })
    except Exception:
        pass

@app.post('/api/agent/chat')
def agent_chat():
    """チャットAPI。"""
    try:
        data = request.get_json() or {}
        tid = getattr(request, '_trace_id', None)
        if LOG_PAYLOADS:
            logger.info(f"/api/agent/chat request body: {_snip_json(data)} trace={tid}")
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({"reply": "ご希望を教えてください。"})

        # Determine agent base for this request
        effective_base = AGENT_BASE_URL
        if not effective_base:
            if (ENV.lower() == 'development'):
                effective_base = 'http://localhost:8080'
            else:
                logger.error("agent_service_not_configured: AGENT_BASE_URL is missing in non-development env")
                return jsonify({
                    "reply": "内部設定エラーが発生しました。時間をおいて再試行してください。",
                    "error": "agent_service_not_configured"
                }), 503
        logger.info(f"/api/agent/chat delegating to ADK base={effective_base}")

        req_user_id = (data.get('user_id') or '').strip() or 'u_local'
        req_session_id = (data.get('session_id') or '').strip()
        if not req_session_id:
            return jsonify({"error": "session_id is required"}), 400
        logger.info(f"/api/agent/chat start app=root_coordinator user={req_user_id or 'auto'} session={req_session_id} msg_len={len(message)} timeout={AGENT_HTTP_TIMEOUT}s trace={tid}")

        claims = require_auth(request)
        user_info, last_persona, active_plan_context = None, None, ""
        if claims and db:
            try:
                udoc = db.collection('users').document(claims['sub']).get(timeout=3)
                if udoc.exists:
                    u = udoc.to_dict() or {}
                    user_info = {'id': claims['sub'], 'name': u.get('name'), 'profile': u.get('profile') or {}}
                    last_id = u.get('last_persona_id')
                    if last_id:
                        pdoc = db.collection('users').document(claims['sub']).collection('personas').document(last_id).get(timeout=3)
                        if pdoc.exists:
                            last_persona = (pdoc.to_dict() or {}).get('profile')
                    
                    # Check for active travel plan
                    active_plan_id = u.get('active_plan_id')
                    if active_plan_id:
                        try:
                            plan_doc = db.collection('users').document(claims['sub']).collection('plans').document(active_plan_id).get(timeout=3)
                            if plan_doc and plan_doc.exists:
                                plan_data = plan_doc.to_dict() or {}
                                # Format active plan context for the agent
                                plan_title = plan_data.get('title', '旅行プラン')
                                plan_summary = plan_data.get('summary', '')
                                itinerary = plan_data.get('itinerary', [])
                                places = plan_data.get('places', [])
                                
                                active_plan_context = f"[アクティブな旅行プラン]\nタイトル: {plan_title}\n"
                                if plan_summary:
                                    active_plan_context += f"概要: {plan_summary}\n"
                                
                                if itinerary:
                                    active_plan_context += "日程:\n"
                                    for day in itinerary[:MAX_ITINERARY_DAYS]:
                                        day_num = day.get('day', 1)
                                        active_plan_context += f"Day {day_num}:\n"
                                        items = day.get('items', [])
                                        for item in items[:MAX_ITEMS_PER_DAY]:
                                            time_str = item.get('time', '')
                                            title = item.get('title', '')
                                            active_plan_context += f"  {time_str} {title}\n"
                                
                                if places:
                                    place_names = [p.get('name', '') for p in places[:MAX_PLACES] if p.get('name')]
                                    if place_names:
                                        active_plan_context += f"関連スポット: {', '.join(place_names)}\n"
                                
                                active_plan_context += "\nこのプランを参考に、旅行当日の相談や質問に対して具体的で実用的なアドバイスを提供してください。\n"
                                
                        except Exception as e:
                            logger.warning(f"Failed to retrieve active plan: {e}")
                            
            except Exception as e:
                logger.warning(f"Error fetching user/persona info: {e}")

        message_to_send = message
        if not is_session_initialized(req_user_id, req_session_id):
            context = {'user': user_info, 'persona': last_persona}
            context_str = "[ユーザー情報]\n" + json.dumps(context, ensure_ascii=False) + "\n\n"
            if active_plan_context:
                context_str += active_plan_context + "\n"
            message_to_send = context_str + "[ユーザーからの依頼]\n" + message
        else:
            # For ongoing sessions, still include active plan context if available
            if active_plan_context:
                message_to_send = active_plan_context + "\n[ユーザーからの依頼]\n" + message
    # 保存はフロントエンドの明示ボタンでのみ実行（エージェント経由トークン付与は廃止）
        
        logger.info(f"About to call agent with message: {message_to_send[:100]}...")
        try:
            events = call_adk_agent_chat('root_coordinator', req_user_id, req_session_id, message_to_send, timeout_sec=AGENT_HTTP_TIMEOUT, base_url=effective_base, ensure_session=True)
        except Exception as e:
            logger.exception("agent_backend_unreachable")
            return jsonify({
                "reply": "現在プラン作成サービスに接続できません。しばらくしてからお試しください。",
                "error": "agent_backend_unreachable"
            }), 502
        logger.info(f"Agent call returned {len(events) if events else 0} events.")
        logger.debug(f"Agent events raw: {_snip_json(events)}")

        reply_text, places, route_info, citations, grounding_html = None, None, None, [], None
        raw_reply_text = None

        if isinstance(events, list) and events:
            final_event = events[-1]
            content = final_event.get('content') or {}
            if content.get('role') == 'model':
                # 第1段: 自然文のみ（JSONを含めない）
                reply_text = "\n".join(p.get('text', '') for p in (content.get('parts') or []))
                raw_reply_text = reply_text  # JSON抽出前の生文字列を保持
                # 先頭フェンス即時除去（後段抽出の成功率向上）
                try:
                    import re as _re2
                    rt_strip = reply_text.lstrip()
                    if rt_strip.startswith('```'):
                        m_fence = _re2.match(r'^```(?:json)?\s*([\s\S]*?)\s*```', rt_strip)
                        if m_fence:
                            inner = m_fence.group(1)
                            global AGENT_JSON_FENCE_STRIPPED
                            AGENT_JSON_FENCE_STRIPPED += 1
                            reply_text = inner
                            raw_reply_text = inner
                            if LOG_PAYLOADS:
                                logger.info("agent_reply_fence_stripped: initial fenced block removed")
                except Exception:
                    pass
                # Debug: raw agent reply logging (controlled by env AGENT_LOG_RAW)
                if os.getenv('AGENT_LOG_RAW') == '1':
                    try:
                        _snippet = (raw_reply_text or '').replace('\n', ' ')[:400]
                        logger.info(f"agent_raw_reply_snippet len={len(raw_reply_text or '')} snippet='{_snippet}'")
                    except Exception:
                        pass
                elif os.getenv('AGENT_LOG_RAW') == 'full':
                    try:
                        if FULL_PAYLOAD:
                            logger.info(f"agent_raw_reply_full len={len(raw_reply_text or '')} body={raw_reply_text}")
                        else:
                            logger.info(f"agent_raw_reply_full len={len(raw_reply_text or '')} body={_snip_text(raw_reply_text, 4000)}")
                    except Exception:
                        pass
                # もし誤ってJSONが混じっても本文として扱い、抽出は第2段で別途行う

            meta_norm = _normalize_grounding_meta(final_event)
            if meta_norm:
                grounding_chunks = meta_norm.get('grounding_chunks') or []
                grounding_supports = meta_norm.get('grounding_supports') or []
                citation_map = {i + 1: (chunk.get('web', {}) if isinstance(chunk, dict) else {}) for i, chunk in enumerate(grounding_chunks)}

                # JSON本体（reply_textが '{' 始まり）の場合は、ここで本文に引用を挿入しない（JSONを破壊するため）
                if reply_text and (not str(reply_text).lstrip().startswith('{')) and grounding_supports and citation_map:
                    segment_citations = {}
                    segment_texts = {}
                    for support in grounding_supports:
                        segment = support.get('segment') if isinstance(support, dict) else None
                        if not segment:
                            continue
                        try:
                            start = int(segment.get('start_index'))
                            end = int(segment.get('end_index'))
                        except Exception:
                            start = None
                            end = None
                        seg_key = (start, end)
                        if seg_key not in segment_citations:
                            segment_citations[seg_key] = set()
                        # Keep segment text if available for fallback search
                        if isinstance(segment.get('text'), str):
                            segment_texts[seg_key] = segment.get('text')
                        for chunk_idx in support.get('grounding_chunk_indices', []):
                            try:
                                segment_citations[seg_key].add(int(chunk_idx) + 1)
                            except Exception:
                                continue

                    # Sort by start desc so string indices remain valid as we insert
                    sorted_segments = sorted(segment_citations.items(), key=lambda item: (item[0][0] if isinstance(item[0][0], int) else -1), reverse=True)
                    inserted_any = False
                    for (start, end), indices in sorted_segments:
                        if not indices:
                            continue
                        # Prefer a compact readable list with comma separation
                        citation_str = f" [{', '.join(map(str, sorted(list(indices))))}]"
                        inserted = False
                        # 1) If end index looks valid, clamp and insert
                        if isinstance(end, int) and end >= 0:
                            try:
                                e = min(max(end, 0), len(reply_text))
                                reply_text = reply_text[:e] + citation_str + reply_text[e:]
                                inserted = True
                            except Exception:
                                inserted = False
                        # 2) Fallback: search by segment text and insert after its last occurrence
                        if not inserted:
                            seg_text = segment_texts.get((start, end))
                            if seg_text:
                                try:
                                    idx = reply_text.rfind(seg_text)
                                    if idx != -1:
                                        e = idx + len(seg_text)
                                        reply_text = reply_text[:e] + citation_str + reply_text[e:]
                                        inserted = True
                                except Exception:
                                    inserted = False
                        if inserted:
                            inserted_any = True
                    if not inserted_any and citation_map and isinstance(reply_text, str):
                        # Fallback: match by citation title text and append [n] after the last occurrence
                        inserts = []
                        for i, c in citation_map.items():
                            title = c.get('title') if isinstance(c, dict) else None
                            if not title or not isinstance(title, str):
                                continue
                            try:
                                pos = reply_text.rfind(title)
                                if pos != -1:
                                    inserts.append((pos + len(title), f" [{i}]"))
                            except Exception:
                                continue
                        # apply from back to front to keep indices stable
                        for pos, frag in sorted(inserts, key=lambda x: x[0], reverse=True):
                            try:
                                reply_text = reply_text[:pos] + frag + reply_text[pos:]
                                inserted_any = True
                            except Exception:
                                continue
                    # Final fallback: append consolidated indices at the tail if nothing was inserted
                    if not inserted_any and citation_map and isinstance(reply_text, str) and len(reply_text) > 0:
                        try:
                            all_idx = sorted([i for i in citation_map.keys() if isinstance(i, int)])
                            if all_idx:
                                reply_text = reply_text.rstrip() + f" [{', '.join(map(str, all_idx))}]"
                                inserted_any = True
                        except Exception:
                            pass
                    if LOG_PAYLOADS:
                        logger.info(f"inline citations inserted={inserted_any} segments={len(sorted_segments)}")

                citations = []
                for i, c in citation_map.items():
                    original_uri = c.get('uri') if isinstance(c, dict) else None
                    title = c.get('title') if isinstance(c, dict) else None
                    if original_uri and "vertexaisearch.cloud.google.com/grounding-api-redirect/" in original_uri:
                        if title:
                            citations.append({"index": i, "title": title, "uri": f"https://www.google.com/search?q={requests.utils.quote(title)}"})
                        else:
                            citations.append({"index": i, "title": title, "uri": original_uri})
                    else:
                        citations.append({"index": i, "title": title, "uri": original_uri})

                sep = meta_norm.get('search_entry_point') or {}
                rendered = sep.get('rendered_content') if isinstance(sep, dict) else None
                queries = sep.get('web_search_queries') if isinstance(sep, dict) else None
                if rendered:
                    grounding_html = rendered
                    if LOG_PAYLOADS:
                        logger.info(f"grounding_html set from rendered_content len={len(grounding_html or '')}")
                elif queries:
                    chips_html = []
                    for query in queries:
                        encoded_query = requests.utils.quote(str(query))
                        chips_html.append(f'<a href="https://www.google.com/search?q={encoded_query}" target="_blank" rel="noopener" style="display:inline-block; border:solid 1px; border-radius:16px; min-width:14px; padding:5px 16px; text-align:center; margin: 0 8px;">{query}</a>')
                    grounding_html = f'<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">{" ".join(chips_html)}</div>'
                    if LOG_PAYLOADS:
                        logger.info(f"grounding_html generated from web_search_queries count={len(queries or [])}")

        # JSON-onlyバリデーション: 先頭の非JSON文字を除去し、JSON未検出なら明示的に再要求
        if isinstance(reply_text, str) and reply_text.strip():
            json_found = False
            try:
                # まず末尾JSON抽出を試行
                reply_text2, p_h, r_h, t_h = _extract_trailing_json(reply_text)
                json_found = (p_h is not None) or (r_h is not None) or (isinstance(t_h, str) and t_h.strip())
                # 表示本文はJSONを除去。JSON内textがあれば優先して本文に採用。
                reply_text = (t_h if isinstance(t_h, str) and t_h.strip() else reply_text2)
                if p_h is not None:
                    places = p_h
                if r_h is not None:
                    route_info = r_h

                # JSONが全く見つからない場合は、最後の '{' 以降のみを残して再試行（先頭非JSON除去）
                if not json_found:
                    try:
                        # 生の応答からJSON開始位置を探索（本文除去後だとJSONが失われる可能性があるため）
                        source = raw_reply_text if isinstance(raw_reply_text, str) else reply_text
                        last_brace = source.rfind('{') if isinstance(source, str) else -1
                        if last_brace != -1:
                            tail = source[last_brace:]
                            rt2, p2, r2, t2 = _extract_trailing_json(tail)
                            if (p2 is not None) or (r2 is not None) or (isinstance(t2, str) and t2.strip()):
                                # 採用
                                reply_text = (t2 if isinstance(t2, str) and t2.strip() else rt2)
                                if p2 is not None:
                                    places = p2
                                if r2 is not None:
                                    route_info = r2
                                json_found = True
                    except Exception:
                        pass

                # それでもJSONが無い場合: raw_reply 全体が実は完全な JSON か最終確認 (セーフガード)
                if not json_found and isinstance(raw_reply_text, str):
                    try:
                        obj_guard = json.loads(raw_reply_text.strip())
                        if isinstance(obj_guard, dict):
                            # 直接抽出 (places/route_info/text)
                            places_g = obj_guard.get('places') or obj_guard.get('place')
                            route_g = obj_guard.get('route_info') or obj_guard.get('route') or obj_guard.get('routeInfo')
                            text_g = obj_guard.get('text') if isinstance(obj_guard.get('text'), str) else None
                            places = _normalize_places_list(places_g)
                            route_info = _normalize_route_info(route_g)
                            reply_text = text_g or ''
                            json_found = True
                    except Exception:
                        pass

                # 依然 JSON 不在ならユーザー再要求（attempted_json_snippet は廃止）
                if not json_found:
                    global AGENT_JSON_FAIL
                    AGENT_JSON_FAIL += 1
                    try:
                        snippet = (raw_reply_text or '')
                        if isinstance(snippet, str):
                            snippet = snippet.strip().replace('\n', ' ')[:200]
                        logger.warning(f"agent_output_not_json: no JSON detected in agent reply snippet='{snippet}'")
                    except Exception:
                        logger.warning("agent_output_not_json: no JSON detected in agent reply")
                    msg = "内部AIの応答形式が不正でした。もう一度、要件を短く伝えてください。"
                    return jsonify({
                        'reply': msg,
                        'places': None,
                        'citations': [],
                        'grounding_html': None,
                        'route_info': None,
                        'error': 'agent_output_not_json',
                        'raw_reply': raw_reply_text
                    }), 502
            except Exception:
                pass
            # JSON検出成功をカウント
            try:
                if json_found:
                    global AGENT_JSON_OK
                    AGENT_JSON_OK += 1
            except Exception:
                pass

        # 進捗ログ（route_info の有無も記録）
        has_route = bool(route_info and isinstance(route_info, dict) and route_info.get('origin') and route_info.get('destination'))
        logger.info(f"/api/agent/chat done user={req_user_id} session={req_session_id} reply_len={len(reply_text or '')} places={len(places or [])} citations={len(citations)} route={'1' if has_route else '0'} trace={tid}")
        if has_route and LOG_PAYLOADS:
            try:
                logger.info(f"route_info summary: {_snip_json(route_info)}")
            except Exception:
                pass
        if not is_session_initialized(req_user_id, req_session_id):
            mark_session_initialized(req_user_id, req_session_id)

        # ログで見切れないよう route_info を先に配置
        resp = { 'reply': reply_text or '提案を作成しました。', 'route_info': route_info, 'places': places, 'citations': citations, 'grounding_html': grounding_html }
        # Attach structured agent output (new schema) if extraction stored it
        try:
            from flask import g as _g  # type: ignore
            struct = getattr(_g, 'agent_struct', None)
            if isinstance(struct, dict):
                if struct.get('summary'):
                    resp['summary'] = struct.get('summary')
                if 'plans' in struct and struct.get('plans'):
                    resp['plans'] = struct.get('plans')
                if 'suggestions' in struct and struct.get('suggestions'):
                    resp['suggestions'] = struct.get('suggestions')
                if 'itinerary' in struct and struct.get('itinerary'):
                    resp['itinerary'] = struct.get('itinerary')
        except Exception:
            pass
        if LOG_PAYLOADS:
            logger.info(f"/api/agent/chat response body: {_snip_json(resp)} trace={tid}")
        if tid:
            resp['trace_id'] = tid
        return jsonify(resp)

    except Exception as e:
        logger.exception("agent_chat error")
        resp = { 'reply': 'エラーが発生しました。時間をおいて再試行してください。' }
        try:
            _tid = getattr(request, '_trace_id', None)
            if _tid:
                resp['trace_id'] = _tid
        except Exception:
            pass
        return jsonify(resp), 500

@app.post('/api/geocode')
def geocode_places():
    """地名の配列を受け取って緯度経度に解決する。Google Geocoding APIキーはフロントのVITE_キーとは別管理のため、
    サーバー側で x-goog-api-key として GEMINI_API_KEY を使わず、環境変数 GOOGLE_MAPS_API_KEY があれば使用する。
    形式: { names: ["箱根温泉", ...] } -> { results: [{ name, lat, lng, formatted_address }] }
    """
    try:
        data = request.get_json() or {}
        names = data.get('names') or []
        if not isinstance(names, list) or not names:
            return jsonify({ 'results': [] })
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        results = []
        if not api_key:
            # Googleキーが無い場合は軽量な OSM Nominatim をフォールバックで利用
            # 注意: 公開環境での大量利用は避け、User-Agent を明示
            headers = {
                'User-Agent': os.getenv('NOMINATIM_UA', 'izatabi-app/1.0 (+https://example.com/contact)')
            }
            for nm in names[:15]:
                try:
                    url = 'https://nominatim.openstreetmap.org/search'
                    params = {
                        'q': nm,
                        'format': 'json',
                        'limit': 1,
                        'addressdetails': 0,
                        'accept-language': 'ja'
                    }
                    r = requests.get(url, params=params, headers=headers, timeout=10)
                    if r.ok:
                        arr = r.json() or []
                        if arr:
                            g = arr[0]
                            lat = float(g.get('lat')) if g.get('lat') is not None else None
                            lon = float(g.get('lon')) if g.get('lon') is not None else None
                            disp = g.get('display_name')
                            results.append({ 'name': nm, 'lat': lat, 'lng': lon, 'formatted_address': disp })
                except Exception:
                    continue
            return jsonify({ 'results': results })
        # Google Geocoding を使用
        for nm in names[:20]:
            try:
                url = 'https://maps.googleapis.com/maps/api/geocode/json'
                params = { 'address': nm, 'key': api_key, 'language': 'ja' }
                r = requests.get(url, params=params, timeout=10)
                if r.ok:
                    j = r.json()
                    if j.get('results'):
                        g = j['results'][0]
                        loc = g['geometry']['location']
                        results.append({ 'name': nm, 'lat': loc['lat'], 'lng': loc['lng'], 'formatted_address': g.get('formatted_address') })
            except Exception:
                continue
        return jsonify({ 'results': results })
    except Exception as e:
        logger.exception("geocode error")
        return jsonify({ 'results': [] })

@app.get('/api/maps/static')
def static_map():
    """Return a Google Static Maps image for given markers.
    Query:
      size: e.g., 640x480 (default 640x480)
      markers: multiple allowed, format 'lat,lng|label:Name' or 'lat,lng'
      path: optional polyline path points (repeatable)
      zoom, center: optional; if omitted, Google fits markers
    """
    key = os.getenv('GOOGLE_MAPS_API_KEY') or os.getenv('VITE_GOOGLE_MAPS_API_KEY')
    if not key or key == 'YOUR_API_KEY_HERE':
        return jsonify({ 'error': 'maps_key_not_configured' }), 400
    size = request.args.get('size', '640x480')
    zoom = request.args.get('zoom')
    center = request.args.get('center')
    scale = request.args.get('scale', '2')
    fmt = request.args.get('format', 'png')
    # markers/path can be repeated
    markers = request.args.getlist('markers')
    paths = request.args.getlist('path')
    params = {
        'size': size,
        'scale': scale,
        'format': fmt,
        'key': key,
        'language': 'ja'
    }
    if zoom: params['zoom'] = zoom
    if center: params['center'] = center
    # Build query manually to allow repeated params
    base = 'https://maps.googleapis.com/maps/api/staticmap'
    # basic validation for size
    if 'x' not in size:
        params['size'] = '640x480'
    query_parts = [f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()]
    for m in markers[:50]:
        query_parts.append('markers=' + requests.utils.quote(m))
    for p in paths[:10]:
        query_parts.append('path=' + requests.utils.quote(p))
    url = base + '?' + '&'.join(query_parts)
    try:
        r = requests.get(url, timeout=15)
        if not r.ok:
            try:
                body_snip = (r.text[:500] + '…') if r.text and len(r.text) > 500 else (r.text or '')
            except Exception:
                body_snip = ''
            logger.warning(f"Static Maps upstream error: status={r.status_code} body={body_snip}")
            return jsonify({ 'error': 'upstream_error', 'status': r.status_code }), 502
        return Response(r.content, content_type=f'image/{fmt}')
    except Exception as e:
        logger.exception("Static Maps request_failed")
        return jsonify({ 'error': 'request_failed', 'message': str(e) }), 500

 

@app.route('/api/analyze', methods=['POST'])
def analyze_text():
    """
    自由記述のテキストを受け取り、AIで分析してスコアと解説を返すAPIエンドポイント。
    """
    data = request.get_json()
    text = data.get('text', '')
    question_trait = data.get('trait', '')
    question_text = data.get('question', '')

    # 自由記述がない場合でも、選択式回答に基づいて基本的な解説を生成する
    if not text:
        base_score = data.get('base_score', 0)
        options = next((q['options'] for q in QUESTIONS if q['id'] == data.get('question_id')), [])
        selected_option_text = next((opt['text'] for opt in options if opt['score'] == base_score), "未選択")

        # AIに解説生成を依頼
        try:
            prompt = f"""
            あなたは、ユーザーの旅行スタイルを分析する専門家です。
            以下の質問とユーザーが選択した回答に基づいて、なぜその選択が特定の旅行スタイルを示すのかを簡潔に（50文字程度で）解説してください。

            ### 質問の特性
            {question_trait}

            ### 質問文
            {question_text}

            ### ユーザーが選択した回答
            「{selected_option_text}」

            ### 解説の生成例
            「計画性よりも、その場の出会いや発見を大切にする冒険家タイプですね。」

            ---
            あなたの解説：
            """
            api_response = call_gemini_api(prompt)
            # APIレスポンスのテキスト部分を抽出
            explanation = api_response['candidates'][0]['content']['parts'][0]['text'].strip()
            return jsonify({"analyzed_score": base_score, "explanation": explanation})

        except Exception as e:
            logger.exception("Error generating explanation for non-free-text answer")
            # エラーが発生した場合は、汎用的な解説を返す
            return jsonify({"analyzed_score": base_score, "explanation": f"「{question_trait}」の観点から、あなたの選択は一貫したスタイルを示しています。"})

    if not genai_configured:
        logger.warning("Skipping Gemini API call due to missing configuration.")
        time.sleep(1)
        dummy_score = random.randint(1, 4)
        dummy_explanation = f"これは「{question_trait}」に関するダミーの解説です。スコアは{dummy_score}と評価されました。"
        return jsonify({"analyzed_score": dummy_score, "explanation": dummy_explanation})


    try:
        prompt = f"""
        あなたは、ユーザーの旅行スタイルを分析する専門家です。
        以下の質問とユーザーの自由記述回答を分析し、2つのタスクを実行してください。

        1.  **スコアリング**: ユーザーの旅行スタイルが特定の特性においてどの程度かを1から4の尺度で評価してください。
            -   評価の基準は質問の選択肢を参考にしてください。スコアが低いほど選択肢1に近く、高いほど選択肢4に近いことを意味します。
            -   例えば、「1: 依存型」〜「4: 冒険型」のような尺度です。

        2.  **解説の生成**: なぜそのスコアになったのか、ユーザーの回答のどの部分からそう判断したのかを、簡潔に（50文字程度で）説明してください。

        ---
        ### 質問の特性
        {question_trait}

        ### 質問文
        {question_text}

        ### ユーザーの自由記述回答
        {text}
        ---

        分析と評価を行い、必ず以下のJSON形式で結果を返してください。
        {{
          "analyzed_score": <1から4の整数スコア>,
          "explanation": "<評価の根拠となる簡潔な解説>"
        }}
        """
        
        api_response = call_gemini_api(prompt)
        
        # レスポンスからコンテンツを抽出
        content_text = api_response['candidates'][0]['content']['parts'][0]['text']
        result_data = json.loads(content_text)
        
        score = int(result_data.get("analyzed_score", 0))
        score = max(1, min(4, score))
        
        explanation = result_data.get("explanation", "解説を生成できませんでした。")

        return jsonify({"analyzed_score": score, "explanation": explanation})

    except Exception as e:
        logger.exception("An error occurred during Gemini API call")
        score = random.randint(1, 4)
        explanation = f"AIの分析中にエラーが発生しました。ダミーデータ（スコア: {score}）を返します。"
        return jsonify({"analyzed_score": score, "explanation": explanation})

@app.route('/api/generate_plan', methods=['POST'])
def generate_plan():
    data = request.get_json()
    if not data or 'travel_type' not in data or 'description' not in data:
        return jsonify({"error": "Missing travel_type or description"}), 400

    # まず Agent サービスが設定されていれば委譲
    if agent_configured:
        try:
            persona = {
                "title": data['travel_type'],
                "description": data['description']
            }
            # 将来的にユーザープロフィールも付与可
            agent_result = call_agent_plan(persona=persona)
            # 期待形式 {"plans": [{title, description} ...]}
            if isinstance(agent_result, dict) and isinstance(agent_result.get('plans'), list):
                return jsonify(agent_result)
            else:
                logger.warning("Agent response shape unexpected; falling back to Gemini path")
        except Exception as e:
            logger.exception("Agent call failed, fallback to Gemini")

    if not genai_configured:
        logger.warning("Skipping Gemini API call for plan generation due to missing configuration.")
        # ダミーのプランを返す
        dummy_plans = {
            "plans": [
                {"title": "設定エラー", "description": "APIキーが設定されていないため、AIプランを生成できません。"},
                {"title": "管理者向け", "description": "server/.env ファイルに有効な GEMINI_API_KEY を設定してください。"}
            ]
        }
        return jsonify(dummy_plans)

    try:
        travel_type = data['travel_type']
        description = data['description']

        prompt = f"""
        あなたは日本の旅行プランを提案する専門家です。
        以下の旅行者タイプ診断の結果に基づいて、その人に合った日本の国内旅行プランを3つ提案してください。

        # 診断結果
        ## 旅行タイプ
        {travel_type}

        ## タイプの説明
        {description}

        # 指示
        1.  提案は必ず日本の国内旅行に限定してください。
        2.  多様な地域のプランを提案してください（例：北海道、本州、九州・沖縄など）。
        3.  各プランには「タイトル」と「簡単な説明」を含めてください。
        4.  出力は必ず以下のJSON形式に従ってください。
            {{
              "plans": [
                {{
                  "title": "<プラン1のタイトル>",
                  "description": "<プラン1の簡単な説明>"
                }},
                {{
                  "title": "<プラン2のタイトル>",
                  "description": "<プラン2の簡単な説明>"
                }},
                {{
                  "title": "<プラン3のタイトル>",
                  "description": "<プラン3の簡単な説明>"
                }}
              ]
            }}
        """

        api_response = call_gemini_api(prompt)
        
        # レスポンスからコンテンツを抽出
        content_text = api_response['candidates'][0]['content']['parts'][0]['text']
        plan_result = json.loads(content_text)

        return jsonify(plan_result)

    except Exception as e:
        logger.exception("An error occurred during plan generation")
        return jsonify({"error": "Failed to generate travel plans with AI", "details": str(e)}), 500


# ==== Auth endpoints (Firestore) ====
USER_ID_REGEX = r'[a-z0-9_-]{3,30}'
@app.route('/api/auth/signup', methods=['POST'])
def signup():
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
    return jsonify({"token": token, "user": {"id": user_id, "name": name, "diagnosis_completed": False}})


@app.route('/api/auth/login', methods=['POST'])
def login():
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
    return jsonify({"token": token, "user": {"id": user_id, "name": user.get('name'), "diagnosis_completed": bool(user.get('diagnosis_completed'))}})

## /api/plans/issue-token 廃止（エージェント経由保存を停止）


# ==== Persona generation and storage ====
@app.route('/api/persona', methods=['POST'])
def create_persona():
    if db is None:
        return jsonify({"error": "Database not configured"}), 500
    claims = require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json() or {}
    # Expect: { profile: {traitScores.., title, description}, system_prompt?: string }
    profile = data.get('profile') or {}
    system_prompt = data.get('system_prompt')

    # Collect user hobbies: prefer from request profile, else from user's saved profile
    user_hobbies = []
    try:
        hb = profile.get('hobbies')
        if isinstance(hb, list):
            user_hobbies = [str(x) for x in hb if str(x).strip()]
        elif isinstance(hb, str) and hb.strip():
            user_hobbies = [s.strip() for s in hb.split(',') if s.strip()]
        # Fallback to user's stored profile
        if not user_hobbies:
            udoc = db.collection('users').document(claims['sub']).get(timeout=5)
            if udoc and udoc.exists:
                up = (udoc.to_dict() or {}).get('profile') or {}
                hb2 = up.get('hobbies')
                if isinstance(hb2, list):
                    user_hobbies = [str(x) for x in hb2 if str(x).strip()]
    except Exception:
        pass

    # If system_prompt not provided, generate via Gemini
    if not system_prompt:
        if not genai_configured:
            system_prompt = (
                "あなたは旅行者の嗜好に基づき、国内旅行の提案と旅程調整を行うペルソナエージェントです。"
                "安全・予算・移動時間に配慮し、ユーザーのタイプ（{title}）の説明（{desc}）を尊重して提案します。"
                "ユーザーの趣味・関心も強く反映してください。以下の趣味参考: {hobbies}"
            ).format(title=profile.get('title'), desc=profile.get('description'), hobbies=json.dumps(user_hobbies, ensure_ascii=False))
        else:
            try:
                prompt = f"""
                あなたは旅行者専用のペルソナエージェントのシステムプロンプトを作成します。
                以下の診断結果（タイプ名と説明、特性スコア）を読み、エージェントが守るべき原則・口調・判断基準・制約を日本語で明確に列挙してください。
                出力は純テキストのみ（箇条書き可）。

                # タイプ
                {profile.get('title')}

                # 説明
                {profile.get('description')}

                # 特性スコア
                {json.dumps(profile.get('traitScores', {}), ensure_ascii=False)}

                # ユーザーの趣味（旅行で重視するテーマや体験）
                {json.dumps(user_hobbies, ensure_ascii=False)}
                """
                api_response = call_gemini_api(prompt)
                system_prompt = api_response['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                logger.exception("Persona prompt generation error")
                system_prompt = (
                    "ユーザーの診断結果および趣味の傾向を尊重し、日本国内の旅行計画を丁寧に提案・調整すること。"
                )

    personas_ref = db.collection('users').document(claims['sub']).collection('personas')
    doc_ref = personas_ref.document()
    doc = {
        'profile': profile,
        'system_prompt': system_prompt,
        'created_at': firestore.SERVER_TIMESTAMP
    }
    try:
        doc_ref.set(doc, timeout=5)
    except Exception as e:
        logger.exception("Persona DB error")
        return jsonify({"error": "database unavailable"}), 503
    # mark user as diagnosis completed and track last persona id
    try:
        db.collection('users').document(claims['sub']).update({
            'diagnosis_completed': True,
            'last_persona_id': doc_ref.id,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, timeout=5)
    except Exception as e2:
        logger.exception("User update after persona error")
    return jsonify({"id": doc_ref.id, "profile": profile, "system_prompt": system_prompt})

# ==== Current user info ====
@app.route('/api/me', methods=['GET'])
def me():
    claims = _claims_or_dev()
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
        return jsonify({"id": claims['sub']}), 200

# ==== Latest persona ====
@app.route('/api/persona/latest', methods=['GET'])
def persona_latest():
    claims = _claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    try:
        user_doc = db.collection('users').document(claims['sub']).get(timeout=5)
        last_id = None
        if user_doc and user_doc.exists:
            data = user_doc.to_dict() or {}
            last_id = data.get('last_persona_id')
        if last_id:
            pdoc = db.collection('users').document(claims['sub']).collection('personas').document(last_id).get(timeout=5)
            if pdoc.exists:
                pd = pdoc.to_dict() or {}
                return jsonify({"id": last_id, "profile": pd.get('profile'), "system_prompt": pd.get('system_prompt')})
        return jsonify({}), 404
    except Exception as e:
        logger.exception("/api/persona/latest error")
        return jsonify({}), 404

# (removed: duplicate catch-all route; use spa_fallback below)

# ==== User profile (basic) ====
@app.route('/api/profile', methods=['GET', 'POST'])
def profile():
    claims = _claims_or_dev()
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    user_id = claims['sub']
    user_ref = db.collection('users').document(user_id)
    if request.method == 'GET':
        try:
            snap = user_ref.get(timeout=5)
            profile = {}
            name = None
            if snap and snap.exists:
                data = snap.to_dict() or {}
                profile = data.get('profile') or {}
                name = data.get('name')
            return jsonify({
                "name": name,
                "profile": profile
            })
        except Exception as e:
            logger.exception("/api/profile GET error")
            return jsonify({"profile": {}}), 200
    else:
        # POST: upsert profile with validation
        payload = request.get_json() or {}
        prof = payload.get('profile') or {}
        sanitized = {}
        errors = []

        def as_str(x):
            try:
                return str(x).strip()
            except Exception:
                return ''

        def strip_ng(s: str):
            # remove control chars and angle brackets to avoid simple injection
            return re.sub(r'[\x00-\x1F<>]', '', s)

        # display_name
        if 'display_name' in prof:
            dn = strip_ng(as_str(prof.get('display_name')))
            if dn and len(dn) <= 50:
                sanitized['display_name'] = dn
            elif dn:
                errors.append('display_name must be <= 50 chars')

        # age
        if 'age' in prof:
            try:
                age = int(prof.get('age'))
                if 0 <= age <= 120:
                    sanitized['age'] = age
                else:
                    errors.append('age must be between 0 and 120')
            except Exception:
                errors.append('age must be an integer')

        # birthdate (YYYY-MM-DD)
        if 'birthdate' in prof:
            bd = as_str(prof.get('birthdate'))
            if bd:
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', bd):
                    sanitized['birthdate'] = bd
                else:
                    errors.append('invalid birthdate format')

        # gender
        if 'gender' in prof:
            g = as_str(prof.get('gender'))
            allowed_genders = {'', '男性', '女性', 'その他', '回答しない'}
            if g in allowed_genders:
                sanitized['gender'] = g
            else:
                errors.append('invalid gender')

        # hobbies
        if 'hobbies' in prof:
            hobbies = prof.get('hobbies')
            arr = []
            if isinstance(hobbies, list):
                arr = [strip_ng(as_str(h)) for h in hobbies]
            elif isinstance(hobbies, str):
                arr = [strip_ng(as_str(p)) for p in hobbies.split(',')]
            arr = [h for h in arr if h]
            # de-dup and length constraints
            seen = set()
            cleaned = []
            for h in arr:
                if h.lower() in seen:
                    continue
                seen.add(h.lower())
                if len(h) > 30:
                    errors.append('each hobby must be <= 30 chars')
                else:
                    cleaned.append(h)
            if len(cleaned) > 10:
                errors.append('max 10 hobbies')
                cleaned = cleaned[:10]
            if cleaned:
                sanitized['hobbies'] = cleaned

        # other optional fields with length limits
        limits = {'location': 100, 'budget': 100, 'notes': 500}
        for key, limit in limits.items():
            if key in prof:
                val = strip_ng(as_str(prof.get(key)))
                if len(val) > limit:
                    errors.append(f'{key} too long (>{limit})')
                elif val:
                    sanitized[key] = val

        if errors:
            return jsonify({"error": "; ".join(errors)}), 400
        try:
            # merge into existing profile
            snap = user_ref.get(timeout=5)
            base = {}
            if snap and snap.exists:
                data = snap.to_dict() or {}
                base = data.get('profile') or {}
            base.update(sanitized)
            user_ref.update({
                'profile': base,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, timeout=5)
        except Exception as e:
            # if update fails (e.g., doc missing), set instead
            try:
                user_ref.set({
                    'profile': sanitized,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True, timeout=5)
            except Exception as e2:
                logger.exception("/api/profile POST error")
                return jsonify({"error": "database unavailable"}), 503
        return jsonify({"profile": base if base else sanitized})

# ==== Active Plan Management ====
@app.route('/api/active-plan', methods=['GET', 'POST'])
def active_plan():
    claims = _claims_or_dev()
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

# ==== Travel Plans (save to Firestore) ====
def _sanitize_title(s: str) -> str:
    try:
        s = str(s or '').strip()
        # Remove control chars and angle brackets
        s = re.sub(r'[\x00-\x1F<>]', '', s)
        return s[:120]
    except Exception:
        return ''

def _sanitize_text(s: str) -> str:
    try:
        s = str(s or '')
        # Limit very long texts (frontend has full copy anyway)
        if len(s) > 200000:
            s = s[:200000]
        return s
    except Exception:
        return ''

@app.route('/api/plans', methods=['GET', 'POST'])
def plans_collection():
    claims = _claims_or_dev()
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
    title = _sanitize_title(payload.get('title') or '')
    text = _sanitize_text(payload.get('text') or '')
    # Normalize optional structures
    places = _normalize_places_list(payload.get('places'))
    route_info = _normalize_route_info(payload.get('route_info') or {})
    summary = _sanitize_text(payload.get('summary')) if isinstance(payload.get('summary'), str) else None
    suggestions = payload.get('suggestions') if isinstance(payload.get('suggestions'), list) else None
    itinerary = payload.get('itinerary') if isinstance(payload.get('itinerary'), list) else None
    status = payload.get('status') if isinstance(payload.get('status'), str) else 'confirmed'
    status = status.lower()
    if status not in ('confirmed','draft'):
        status = 'confirmed'

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
        }
        return jsonify(out), 201
    except Exception as e:
        logger.exception("/api/plans POST error")
        return jsonify({"error": "database_unavailable"}), 503


@app.route('/api/plans/<plan_id>', methods=['GET', 'DELETE'])
def plans_item(plan_id: str):
    claims = _claims_or_dev()
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

## /api/plans/by-token 廃止（エージェント経由保存を停止）

# ---- SPA history fallback (serve index.html for non-API routes) ----
# This allows reloading deep links like /planner or /result without 404.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa_fallback(path: str):
    # Do not intercept API routes
    if path.startswith('api/'):
        return jsonify({ 'error': 'not_found' }), 404
    try:
        # Serve known static assets under /static path
        static_root = app.static_folder or ''
        if path in ('favicon.ico',):
            fp = os.path.join(static_root, path)
            if os.path.isfile(fp):
                return app.send_static_file(path)
        if path.startswith('assets/'):
            fp = os.path.join(static_root, path)
            if os.path.isfile(fp):
                # Prefix with static_url_path to satisfy Flask's static route
                return app.send_static_file(path)
        # Otherwise serve the SPA entrypoint
        return app.send_static_file('index.html')
    except Exception:
        # As a last resort, return 404 to avoid masking real backend errors
        return jsonify({ 'error': 'not_found' }), 404

def create_dummy_user_if_needed():
    if ENV.lower() != 'development' or db is None:
        return
    
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

    except Exception as e:
        logger.error(f"Failed to create/update dummy user or persona: {e}")

if __name__ == '__main__':
    create_dummy_user_if_needed()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))



