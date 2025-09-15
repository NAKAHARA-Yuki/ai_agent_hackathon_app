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
        
        # Attach structured agent output if available
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
            logger.info(f"/api/agent/chat response body: {snip_json(resp)} trace={tid}")
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