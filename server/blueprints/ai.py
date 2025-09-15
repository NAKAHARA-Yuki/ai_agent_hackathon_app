"""AI and agent interaction blueprint"""
import json
import os
import logging
import random
import time
import re
import requests
from time import monotonic
from flask import Blueprint, request, jsonify, g, current_app
import base64
import io

from utils.ai_processing import (
    call_gemini_api, genai_configured, extract_trailing_json,
    extract_json_passthrough, retry_on_503, increment_agent_json_ok, increment_agent_json_fail,
    call_adk_agent_chat
)
from utils.auth import claims_or_dev
from utils.data_processing import snip_json, snip_text, normalize_places_list, normalize_route_info

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__)

# Agent configuration
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL")
AGENT_API_KEY = os.getenv("AGENT_API_KEY")
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"

# After ENV is known, apply dev fallback and compute configured flag
if not AGENT_BASE_URL and ENV.lower() == "development":
    AGENT_BASE_URL = "http://localhost:8080"

# dev 環境ではデフォルトで raw agent reply をフルログ（明示指定があればそれを優先）
if ENV.lower() == "development" and not os.getenv('AGENT_LOG_RAW'):
    os.environ['AGENT_LOG_RAW'] = 'full'

agent_configured = bool(AGENT_BASE_URL)

# Agent呼び出しHTTPタイムアウト（秒）環境変数で調整可能。デフォルト180。
try:
    AGENT_HTTP_TIMEOUT = int(os.getenv('AGENT_HTTP_TIMEOUT') or '180')
    if AGENT_HTTP_TIMEOUT <= 0:
        AGENT_HTTP_TIMEOUT = 180
except Exception:
    AGENT_HTTP_TIMEOUT = 180

# Whether to log request/response payloads (useful for debugging; be careful in prod)
LOG_PAYLOADS = True
FULL_PAYLOAD = (os.getenv('CLOUD_LOG_FULL_PAYLOAD') == '1')

# Session management - simple in-memory tracking
_session_store = {}


def is_session_initialized(user_id: str, session_id: str) -> bool:
    """Check if session is initialized"""
    key = f"{user_id}:{session_id}"
    return key in _session_store


def mark_session_initialized(user_id: str, session_id: str):
    """Mark session as initialized"""
    key = f"{user_id}:{session_id}"
    _session_store[key] = True


def normalize_grounding_meta(event: dict) -> dict:
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


def call_agent_plan(persona: dict = None) -> dict:
    """Call the agent planning service"""
    if not agent_configured:
        raise Exception("Agent service not configured")
    
    def _make_request():
        url = f"{AGENT_BASE_URL}/v1/plan"
        headers = {"Content-Type": "application/json"}
        if AGENT_API_KEY:
            headers["Authorization"] = f"Bearer {AGENT_API_KEY}"
        
        payload = {"persona": persona or {}}
        resp = requests.post(url, json=payload, headers=headers, timeout=AGENT_HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    
    return retry_on_503(_make_request)


# ===== Vertex AI (REST) helpers for image generation =====
def _vertex_project_location() -> tuple[str, str]:
    """Resolve GCP project and location from environment.
    Uses GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID. Location defaults to 'global' or env VERTEX_LOCATION.
    """
    project = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT_ID')
    location = os.getenv('VERTEX_LOCATION') or 'global'
    return project, location


def _build_image_prompt_from_plan(plan: dict, style: str | None = None) -> str:
    """Craft an English prompt for image generation from a travel plan dict."""
    title = str(plan.get('title') or 'Japan Travel Plan')
    summary = str(plan.get('summary') or '')
    places = []
    try:
        for p in (plan.get('places') or []):
            name = p.get('name') or p.get('title')
            if name:
                places.append(str(name))
    except Exception:
        pass
    # Extract 3-5 key itinerary items for visual cues
    items = []
    try:
        for day in (plan.get('itinerary') or [])[:3]:
            for it in (day.get('items') or [])[:3]:
                t = it.get('title') or it.get('name')
                if t:
                    items.append(str(t))
            if len(items) >= 5:
                break
    except Exception:
        pass

    style_hint = style or 'high-quality photorealistic travel poster, vibrant, cinematic lighting'
    bullets = []
    if places:
        bullets.append(f"Key places: {', '.join(places[:6])}.")
    if items:
        bullets.append(f"Activities: {', '.join(items[:6])}.")
    if summary:
        bullets.append(f"Trip vibe: {summary[:220]}")

    prompt = (
        f"Create an image for a Japanese travel plan titled '{title}'.\n"
        f"Style: {style_hint}.\n"
        "Focus on iconic scenery and mood matching the plan.\n"
        + ("\n".join(bullets) if bullets else '')
    )
    return prompt


_token_cache = {"access_token": None, "exp": 0.0}


def _get_access_token_via_metadata() -> str | None:
    """Fetch an OAuth2 access token from Cloud Run/metadata server.
    Caches token until near expiry. Returns None if not available.
    """
    # Env override (useful for local/dev)
    env_token = os.getenv('GCP_ACCESS_TOKEN')
    if env_token:
        return env_token

    # Cache valid token
    now = time.time()
    if _token_cache.get('access_token') and now < (_token_cache.get('exp', 0) - 60):
        return _token_cache['access_token']

    try:
        meta_url = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
        h = {'Metadata-Flavor': 'Google'}
        r = requests.get(meta_url, headers=h, timeout=3)
        if r.status_code == 200:
            data = r.json()
            token = data.get('access_token')
            expires_in = float(data.get('expires_in') or 0)
            if token:
                _token_cache['access_token'] = token
                _token_cache['exp'] = now + max(0.0, expires_in)
                return token
    except Exception:
        # Not on Cloud Run / metadata not reachable
        pass
    return None


def _generate_image_with_vertex_rest(prompt: str, model_id: str, project: str, location: str):
    """Call Vertex AI REST to generate image and optional text.
    Returns (base64_data, mime_type, text_output)
    """
    access_token = _get_access_token_via_metadata()
    if not access_token:
        raise RuntimeError('No access token available. On Cloud Run, ensure default service account and metadata server access. For local dev, set GCP_ACCESS_TOKEN.')

    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/"
        f"publishers/google/models/{model_id}:generateContent"
    )
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    # Vertex expects array contents with role+parts
    body = {
        'contents': [
            {
                'role': 'user',
                'parts': [ { 'text': str(prompt) } ],
            }
        ],
        'generation_config': {
            'response_modalities': ['TEXT', 'IMAGE'],
            'candidate_count': 1,
        }
    }

    r = requests.post(url, headers=headers, json=body, timeout=60)
    if r.status_code >= 300:
        # Log minimal detail; return clean error
        logger.warning('Vertex REST error %s: %s', r.status_code, snip_text(r.text))
        raise RuntimeError(f'Vertex REST error: HTTP {r.status_code}')

    resp = r.json()
    b64 = None
    mime = None
    texts = []
    try:
        cand = (resp.get('candidates') or [None])[0]
        content = cand and cand.get('content') or {}
        parts = content.get('parts') or []
        for part in parts:
            # Text part
            if isinstance(part, dict) and part.get('text'):
                texts.append(str(part.get('text')))
                continue
            # Image part (camelCase inlineData from REST, with snake_case fallback)
            inline = None
            if isinstance(part, dict):
                inline = part.get('inlineData') or part.get('inline_data')
            if inline:
                data = inline.get('data')
                if data:
                    # Assume base64; validate and fallback to encoding
                    try:
                        base64.b64decode(data, validate=True)
                        b64 = data
                    except Exception:
                        b64 = base64.b64encode(str(data).encode('utf-8')).decode('ascii')
                m = inline.get('mimeType') or inline.get('mime_type')
                if m:
                    mime = m
    except Exception:
        pass

    if not b64:
        raise RuntimeError('No image content returned by model')
    return b64, (mime or 'image/png'), ("\n".join([t for t in texts if t]) or None)


def _compress_image_base64_if_needed(b64_data: str, mime_type: str | None, max_bytes: int = 1_000_000) -> tuple[str, str]:
    """If decoded base64 exceeds max_bytes, reduce quality by re-encoding as JPEG.
    Returns (b64, mime) of possibly re-encoded image. Falls back gracefully on errors.
    """
    try:
        raw = base64.b64decode(b64_data)
    except Exception:
        # Invalid base64; return as-is
        return b64_data, (mime_type or 'image/png')

    if len(raw) <= max_bytes:
        return b64_data, (mime_type or 'image/png')

    try:
        from PIL import Image
    except Exception:
        # Pillow not available; return original
        logger.warning('Pillow not installed; cannot compress image. Returning original image.')
        return b64_data, (mime_type or 'image/png')

    try:
        with Image.open(io.BytesIO(raw)) as im:
            # Convert to RGB for JPEG (drop alpha on white background if needed)
            if im.mode in ('RGBA', 'LA'):
                bg = Image.new('RGB', im.size, (255, 255, 255))
                bg.paste(im.convert('RGBA'), mask=im.split()[-1])
                work = bg
            else:
                work = im.convert('RGB')

            # Try decreasing quality steps
            qualities = [85, 75, 65, 55, 45, 35, 25, 20, 15, 10, 5]
            best_b = None
            for q in qualities:
                buf = io.BytesIO()
                work.save(buf, format='JPEG', quality=q, optimize=True)
                b = buf.getvalue()
                if len(b) <= max_bytes:
                    best_b = b
                    break
                # keep smallest so far
                if best_b is None or len(b) < len(best_b):
                    best_b = b
            # Fallback to smallest even if still > max
            if best_b is not None:
                return base64.b64encode(best_b).decode('ascii'), 'image/jpeg'
    except Exception:
        logger.exception('Image compression failed')

    # As last resort, return original
    return b64_data, (mime_type or 'image/png')


@ai_bp.post('/api/agent/chat')
def agent_chat():
    """Main agent chat endpoint with comprehensive error handling and response processing"""
    try:
        # Get user authentication
        claims = claims_or_dev()
        if not claims:
            return jsonify({'reply': '認証が必要です。ログインしてから再試行してください。'}), 401
        
        req_user_id = claims['sub']
        data = request.get_json() or {}
        message = data.get('message', '')
        req_session_id = data.get('session_id', 'default')
        
        tid = getattr(request, '_trace_id', None)
        
        if not message:
            return jsonify({'reply': '何かご質問やご要望をお聞かせください。'}), 400
        
        # Fallback to Gemini if agent not configured
        if not agent_configured:
            try:
                if not genai_configured:
                    return jsonify({
                        'reply': 'AIサービスが設定されていません。管理者にお問い合わせください。',
                        'places': None,
                        'citations': [],
                        'grounding_html': None,
                        'route_info': None
                    }), 503
                
                # Simple Gemini fallback
                prompt = f"""
                あなたは日本国内の旅行計画を提案する専門家です。
                ユーザーからの質問に日本語で回答してください。
                
                ユーザーの質問: {message}
                """
                api_response = call_gemini_api(prompt)
                reply = api_response['candidates'][0]['content']['parts'][0]['text']
                
                return jsonify({
                    'reply': reply,
                    'places': None,
                    'citations': [],
                    'grounding_html': None,
                    'route_info': None
                })
            except Exception as e:
                logger.exception("Gemini fallback error")
                return jsonify({
                    'reply': 'AIサービスでエラーが発生しました。しばらく待ってから再試行してください。'
                }), 500
        
        # Prepare response container and attach structured agent output if available
        resp = {}
        try:
            struct = getattr(g, 'agent_struct', None)
            if isinstance(struct, dict):
                if struct.get('summary'):
                    resp['summary'] = struct.get('summary')
                if 'plans' in struct and struct.get('plans'):
                    resp['plans'] = struct.get('plans')
                if 'suggestions' in struct and struct.get('suggestions'):
                    resp['suggestions'] = struct.get('suggestions')
                if 'itinerary' in struct and struct.get('itinerary'):
                    resp['itinerary'] = struct.get('itinerary')
                if 'response_type' in struct and struct.get('response_type'):
                    resp['response_type'] = struct.get('response_type')
        except Exception:
            pass
        
        if LOG_PAYLOADS:
            try:
                logger.info(f"/api/agent/chat response body: {snip_json(resp)} trace={tid}")
            except Exception:
                # Be robust to any logging/snip failures
                logger.info(f"/api/agent/chat response body: <unavailable> trace={tid}")
        if tid:
            resp['trace_id'] = tid
        
        return jsonify(resp)
    
    except Exception as e:
        logger.exception("agent_chat error")
        resp = {'reply': 'エラーが発生しました。時間をおいて再試行してください。'}
        try:
            _tid = getattr(request, '_trace_id', None)
            if _tid:
                resp['trace_id'] = _tid
        except Exception:
            pass
        return jsonify(resp), 500


@ai_bp.route('/api/generate_plan', methods=['POST'])
def generate_plan():
    """Generate travel plans based on user personality type"""
    data = request.get_json()
    if not data or 'travel_type' not in data or 'description' not in data:
        return jsonify({"error": "Missing travel_type or description"}), 400

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


@ai_bp.post('/api/agent/generate_plan')
def agent_generate_plan():
    """Generate 3 travel plan options via ADK agent chat using Firestore persona + UI keyword."""
    try:
        claims = claims_or_dev()
        if not claims:
            return jsonify({"error": "auth_required"}), 401

        body = request.get_json(silent=True) or {}
        # UIからのキーワード（任意）
        keyword = (body.get('keyword') or body.get('travel_type') or '').strip()

        # Firestore の診断結果（persona）を優先
        travel_type = ''
        description = ''
        try:
            db = getattr(current_app, 'db', None)
            user_id = claims['sub']
            if db is not None:
                uref = db.collection('users').document(user_id)
                udoc = uref.get(timeout=5)
                last_pid = None
                if udoc and getattr(udoc, 'exists', False):
                    udata = udoc.to_dict() or {}
                    last_pid = udata.get('last_persona_id')
                pref = uref.collection('personas')
                pdoc = pref.document(last_pid).get(timeout=5) if last_pid else None
                # Fallback: 最初のペルソナ
                if not pdoc or not getattr(pdoc, 'exists', False):
                    try:
                        for _d in pref.stream():
                            pdoc = _d
                            break
                    except Exception:
                        pdoc = None
                if pdoc and getattr(pdoc, 'exists', False):
                    pdata = pdoc.to_dict() or {}
                    prof = pdata.get('profile') or {}
                    travel_type = str(prof.get('title') or '').strip()
                    description = str(prof.get('description') or '').strip()
        except Exception:
            logger.exception('failed to load persona from firestore; falling back to request body')

        # 最終フォールバック: リクエストの値
        if not travel_type:
            travel_type = (body.get('travel_type') or '').strip()
        if not description:
            description = (body.get('description') or '').strip()
        session_id = (body.get('session_id') or 'plan-wizard').strip() or 'plan-wizard'

        if not travel_type or not description:
            return jsonify({"error": "missing_parameters", "message": "診断結果（title/description）が見つかりません"}), 400

        # Agent path via ADK chat（travel_planner に明示委譲する前置き）
        user_id = claims['sub']
        prefix_lines = [
            "travel_planner", 
            "診断結果",
            f"旅行タイプ: {travel_type}",
            f"説明: {description}",
        ]
        if keyword:
            prefix_lines.append(f"キーワード: {keyword}")
        prefix_text = "\n".join(prefix_lines) + "\n"

        # 本文は短く補足のみ（実処理はプレフィックスの診断結果を使用）
        message = f"（キーワード: {keyword}）" if keyword else ""

        if LOG_PAYLOADS:
            logger.info(f"agent_generate_plan request user={user_id} session={session_id} type='{travel_type}' len(desc)={len(description)}")
        events = call_adk_agent_chat(
            app_name='root_coordinator',
            user_id=user_id,
            session_id=session_id,
            message_text=message,
            timeout_sec=AGENT_HTTP_TIMEOUT,
            base_url=AGENT_BASE_URL,
            ensure_session=True,
            prefix=prefix_text,
        )

        # Join final model parts into text
        text = ''
        if isinstance(events, list) and events:
            final = events[-1] or {}
            content = final.get('content') or {}
            if content.get('role') == 'model':
                text = "\n".join(p.get('text', '') for p in (content.get('parts') or []))

        # Try passthrough fenced JSON
        if text:
            return jsonify(extract_json_passthrough(text))
        else:
            return jsonify({"error": "agent_output_not_json"},{"request":prefix_text},{"response": events}), 502

    except Exception:
        logger.exception("agent_generate_plan error")
        return jsonify({"error": "internal_error"}), 500


@ai_bp.post('/api/agent/modify_plan')
def agent_modify_plan():
    """Modify an existing travel plan via ADK agent (travel_modifier).
    Expects JSON body with:
      - plan: object (required)
      - change_requests: string|object (required)
      - constraints: object (optional)
      - context: object (optional)
      - session_id: string (optional)
    Returns: strict JSON from agent (single object).
    """
    try:
        claims = claims_or_dev()
        if not claims:
            return jsonify({"error": "auth_required"}), 401

        body = request.get_json(silent=True) or {}
        plan = body.get('plan')
        change_requests = body.get('change_requests') or body.get('request')
        constraints = body.get('constraints')
        context_info = body.get('context')
        session_id = (body.get('session_id') or 'plan-modifier').strip() or 'plan-modifier'

        if not isinstance(plan, dict):
            return jsonify({"error": "invalid_parameters", "message": "plan must be an object"}), 400
        if change_requests is None or (isinstance(change_requests, str) and not change_requests.strip()):
            return jsonify({"error": "invalid_parameters", "message": "change_requests is required"}), 400

        # Prepare prefix targeted to travel_modifier
        prefix_lines = [
            "travel_modifier",
            "current_plan:",
            json.dumps(plan, ensure_ascii=False),
            "change_requests:",
            change_requests if isinstance(change_requests, str) else json.dumps(change_requests, ensure_ascii=False),
        ]
        if isinstance(constraints, (dict, list)) and constraints:
            prefix_lines += ["constraints:", json.dumps(constraints, ensure_ascii=False)]
        if isinstance(context_info, (dict, list)) and context_info:
            prefix_lines += ["context:", json.dumps(context_info, ensure_ascii=False)]
        prefix_text = "\n".join(prefix_lines) + "\n"

        message = "(プラン修正リクエスト)"

        user_id = claims['sub']
        if LOG_PAYLOADS:
            logger.info(f"agent_modify_plan user={user_id} session={session_id} plan_itins={len((plan or {}).get('itinerary') or [])}")

        events = call_adk_agent_chat(
            app_name='root_coordinator',
            user_id=user_id,
            session_id=session_id,
            message_text=message,
            timeout_sec=AGENT_HTTP_TIMEOUT,
            base_url=AGENT_BASE_URL,
            ensure_session=True,
            prefix=prefix_text,
        )

        text = ''
        if isinstance(events, list) and events:
            final = events[-1] or {}
            content = final.get('content') or {}
            if content.get('role') == 'model':
                text = "\n".join(p.get('text', '') for p in (content.get('parts') or []))

        if text:
            return jsonify(extract_json_passthrough(text))
        else:
            return jsonify({"error": "agent_output_not_json"},{"request":prefix_text},{"response": events}), 502

    except Exception:
        logger.exception("agent_modify_plan error")
        return jsonify({"error": "internal_error"}), 500


@ai_bp.post('/api/agent/day_advice')
def agent_day_advice():
    """Provide day-of travel advice via ADK agent (travel_advisor).
    Expects JSON body with:
      - plan: object (required)
      - user_message: string (required)
      - current_context: object (optional)  # location/time/weather etc.
      - session_id: string (optional)
    Returns: strict JSON from agent (single object).
    """
    try:
        claims = claims_or_dev()
        if not claims:
            return jsonify({"error": "auth_required"}), 401

        body = request.get_json(silent=True) or {}
        plan = body.get('plan')
        user_message = (body.get('user_message') or body.get('message') or '').strip()
        current_context = body.get('current_context') or body.get('context')
        session_id = (body.get('session_id') or 'day-advisor').strip() or 'day-advisor'

        if not isinstance(plan, dict):
            return jsonify({"error": "invalid_parameters", "message": "plan must be an object"}), 400
        if not user_message:
            return jsonify({"error": "invalid_parameters", "message": "user_message is required"}), 400

        # Prepare prefix targeted to travel_advisor
        prefix_lines = [
            "travel_advisor",
            "travel_plan:",
            json.dumps(plan, ensure_ascii=False),
            "user_message:",
            user_message,
        ]
        if isinstance(current_context, (dict, list)) and current_context:
            prefix_lines += ["current_context:", json.dumps(current_context, ensure_ascii=False)]
        prefix_text = "\n".join(prefix_lines) + "\n"

        message = "(当日サポート)"

        user_id = claims['sub']
        if LOG_PAYLOADS:
            logger.info(f"agent_day_advice user={user_id} session={session_id} msg_len={len(user_message)}")

        events = call_adk_agent_chat(
            app_name='root_coordinator',
            user_id=user_id,
            session_id=session_id,
            message_text=message,
            timeout_sec=AGENT_HTTP_TIMEOUT,
            base_url=AGENT_BASE_URL,
            ensure_session=True,
            prefix=prefix_text,
        )

        text = ''
        if isinstance(events, list) and events:
            final = events[-1] or {}
            content = final.get('content') or {}
            if content.get('role') == 'model':
                text = "\n".join(p.get('text', '') for p in (content.get('parts') or []))

        if text:
            return jsonify(extract_json_passthrough(text))
        else:
            return jsonify({"error": "agent_output_not_json"},{"request":prefix_text},{"response": events}), 502

    except Exception:
        logger.exception("agent_day_advice error")
        return jsonify({"error": "internal_error"}), 500


@ai_bp.post('/api/agent/generate_plan_image')
def generate_plan_image():
    """Generate an illustrative image from a travel plan via Vertex AI (Gemini image preview model).
    Request JSON:
      - plan: object (required)
      - style: string (optional)  e.g., 'watercolor illustration', 'retro poster', 'photorealistic'
      - model_id: string (optional) default 'gemini-2.5-flash-image-preview'
    Response JSON on success:
      { image_base64: str, image_mime_type: str, text: str|null, model_id: str }
    """
    try:
        claims = claims_or_dev()
        if not claims:
            return jsonify({"error": "auth_required"}), 401

        body = request.get_json(silent=True) or {}
        plan = body.get('plan')
        style = body.get('style')
        model_id = (body.get('model_id') or os.getenv('PLAN_IMAGE_MODEL_ID') or 'gemini-2.5-flash-image-preview').strip()

        if not isinstance(plan, dict):
            return jsonify({"error": "invalid_parameters", "message": "plan must be an object"}), 400

        project, location = _vertex_project_location()
        if not project:
            return jsonify({"error": "vertex_not_configured", "message": "Set GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID"}), 503

        prompt = _build_image_prompt_from_plan(plan, style)

        if LOG_PAYLOADS:
            logger.info(f"generate_plan_image user={claims['sub']} model={model_id} loc={location} prompt_len={len(prompt)}")

        image_b64, mime, text_out = _generate_image_with_vertex_rest(prompt, model_id, project, location)
        # Enforce max size ~1MB by lowering quality if necessary
        image_b64, mime = _compress_image_base64_if_needed(image_b64, mime, 1_000_000)

        resp = {
            'image_base64': image_b64,
            'image_mime_type': mime,
            'text': text_out,
            'model_id': model_id,
        }
        tid = getattr(request, '_trace_id', None)
        if tid:
            resp['trace_id'] = tid
        return jsonify(resp)

    except RuntimeError as re:
        logger.exception('generate_plan_image runtime error')
        return jsonify({"error": "runtime_error", "message": str(re)}), 500
    except Exception:
        logger.exception('generate_plan_image error')
        return jsonify({"error": "internal_error"}), 500