"""AI and agent interaction blueprint"""
import json
import os
import logging
import random
import time
import requests
from time import monotonic
from flask import Blueprint, request, jsonify, g

from utils.ai_processing import (
    call_gemini_api, genai_configured, extract_trailing_json, 
    extract_json_passthrough, retry_on_503, increment_agent_json_ok, increment_agent_json_fail
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

# Agent呼び出しHTTPタイムアウト（秒）環境変数で調整可能。デフォルト90。
try:
    AGENT_HTTP_TIMEOUT = int(os.getenv('AGENT_HTTP_TIMEOUT') or '90')
    if AGENT_HTTP_TIMEOUT <= 0:
        AGENT_HTTP_TIMEOUT = 90
except Exception:
    AGENT_HTTP_TIMEOUT = 90

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
        
        # Call agent service
        try:
            headers = {"Content-Type": "application/json"}
            if AGENT_API_KEY:
                headers["Authorization"] = f"Bearer {AGENT_API_KEY}"
            
            payload = {
                "message": message,
                "user_id": req_user_id,
                "session_id": req_session_id
            }
            
            if LOG_PAYLOADS:
                logger.info(f"agent_chat request: {snip_json(payload)} trace={tid}")
            
            def _make_agent_request():
                url = f"{AGENT_BASE_URL}/v1/chat"
                resp = requests.post(url, json=payload, headers=headers, timeout=AGENT_HTTP_TIMEOUT)
                resp.raise_for_status()
                return resp.json()
            
            response_data = retry_on_503(_make_agent_request)
            
        except requests.exceptions.RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            if status_code == 404:
                return jsonify({
                    'reply': 'エージェントサービスが見つかりません。管理者に連絡してください。',
                    'places': None,
                    'citations': [],
                    'grounding_html': None,
                    'route_info': None,
                    'error': 'agent_not_found'
                }), 502
            elif status_code in (503, 502, 504):
                return jsonify({
                    'reply': 'エージェントサービスが一時的に利用できません。しばらく待ってから再試行してください。',
                    'places': None,
                    'citations': [],
                    'grounding_html': None,
                    'route_info': None,
                    'error': 'agent_unavailable'
                }), 502
            else:
                logger.exception(f"Agent request failed: status={status_code}")
                return jsonify({
                    'reply': 'エージェントサービスでエラーが発生しました。時間をおいて再試行してください。',
                    'places': None,
                    'citations': [],
                    'grounding_html': None,
                    'route_info': None,
                    'error': 'agent_error'
                }), 502
        except Exception as e:
            logger.exception("Agent call error")
            return jsonify({
                'reply': 'システムエラーが発生しました。時間をおいて再試行してください。',
                'places': None,
                'citations': [],
                'grounding_html': None,
                'route_info': None,
                'error': 'system_error'
            }), 500
        
        # Process agent response
        reply_text = response_data.get('reply', '')
        places = response_data.get('places', [])
        route_info = response_data.get('route_info')
        raw_reply_text = reply_text
        citations = []
        grounding_html = None
        
        # Process grounding metadata if present
        events = response_data.get('events', [])
        if isinstance(events, list):
            for event in events:
                if not isinstance(event, dict):
                    continue
                meta_norm = normalize_grounding_meta(event)
                grounding_chunks = meta_norm.get('grounding_chunks') or []
                grounding_supports = meta_norm.get('grounding_supports') or []
                
                # Build citation map
                citation_map = {}
                for chunk in grounding_chunks:
                    if not isinstance(chunk, dict):
                        continue
                    chunk_id = chunk.get('chunk_id')
                    title = chunk.get('title')
                    uri = chunk.get('uri')
                    if chunk_id and title:
                        citation_map[len(citation_map) + 1] = {"title": title, "uri": uri}
                
                # Process citations in reply text
                if citation_map and isinstance(reply_text, str):
                    # Process inline citations
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
                
                # Generate grounding HTML
                sep = meta_norm.get('search_entry_point') or {}
                rendered = sep.get('rendered_content') if isinstance(sep, dict) else None
                queries = sep.get('web_search_queries') if isinstance(sep, dict) else None
                if rendered:
                    grounding_html = rendered
                elif queries:
                    chips_html = []
                    for query in queries:
                        encoded_query = requests.utils.quote(str(query))
                        chips_html.append(f'<a href="https://www.google.com/search?q={encoded_query}" target="_blank" rel="noopener" style="display:inline-block; border:solid 1px; border-radius:16px; min-width:14px; padding:5px 16px; text-align:center; margin: 0 8px;">{query}</a>')
                    grounding_html = f'<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">{" ".join(chips_html)}</div>'
        
        # Try JSON passthrough extraction first
        if isinstance(reply_text, str) and reply_text.strip():
            passthrough = extract_json_passthrough(reply_text)
            if passthrough is not None:
                if LOG_PAYLOADS:
                    logger.info("agent_reply_passthrough_json: returning raw JSON object")
                return jsonify(passthrough)
            
            # Fallback to simplified extraction
            prefix_text, p_h, r_h, t_h = extract_trailing_json(reply_text)
            reply_text = (t_h if isinstance(t_h, str) and t_h.strip() else prefix_text)
            if p_h is not None:
                places = p_h
            if r_h is not None:
                route_info = r_h
            json_found = (p_h is not None) or (r_h is not None) or (isinstance(t_h, str) and t_h.strip())
            if not json_found:
                increment_agent_json_fail()
                snippet = (raw_reply_text or '')
                if isinstance(snippet, str):
                    snippet = snippet.strip().replace('\n', ' ')[:200]
                logger.warning(f"agent_output_not_json: no JSON detected in agent reply snippet='{snippet}'")
                return jsonify({
                    'reply': '内部AIの応答形式が不正でした。もう一度、要件を短く伝えてください。',
                    'places': None,
                    'citations': [],
                    'grounding_html': None,
                    'route_info': None,
                    'error': 'agent_output_not_json',
                    'raw_reply': raw_reply_text
                }), 502
            
            increment_agent_json_ok()
        
        # Log completion
        has_route = bool(route_info and isinstance(route_info, dict) and route_info.get('origin') and route_info.get('destination'))
        logger.info(f"/api/agent/chat done user={req_user_id} session={req_session_id} reply_len={len(reply_text or '')} places={len(places or [])} citations={len(citations)} route={'1' if has_route else '0'} trace={tid}")
        
        if not is_session_initialized(req_user_id, req_session_id):
            mark_session_initialized(req_user_id, req_session_id)
        
        # Build response
        resp = {
            'reply': reply_text or '提案を作成しました。',
            'route_info': route_info,
            'places': places,
            'citations': citations,
            'grounding_html': grounding_html
        }
        
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