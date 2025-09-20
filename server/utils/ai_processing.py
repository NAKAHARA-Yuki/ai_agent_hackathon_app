"""AI and text processing utilities"""
import json
import re
import os
import requests
import logging
from time import sleep
from typing import Optional, Dict, Any, Tuple, List
from time import monotonic
from .data_processing import normalize_places_list, normalize_route_info, snip_json, snip_text

logger = logging.getLogger(__name__)

# Gemini API configuration
# Note: genai_configured は後方互換のため残すが、実呼び出しでは毎回環境変数を参照して検証する
api_key = os.getenv("GEMINI_API_KEY")
genai_configured = bool(api_key and api_key != "YOUR_API_KEY_HERE")

# Agent JSON-only compliance counters - will be managed by the main app
def get_agent_json_ok():
    """Get current AGENT_JSON_OK count from app context"""
    try:
        from flask import current_app
        return getattr(current_app, 'AGENT_JSON_OK', 0)
    except:
        return 0

def get_agent_json_fail():
    """Get current AGENT_JSON_FAIL count from app context"""
    try:
        from flask import current_app
        return getattr(current_app, 'AGENT_JSON_FAIL', 0)
    except:
        return 0

def increment_agent_json_ok():
    """Increment AGENT_JSON_OK counter"""
    try:
        from flask import current_app
        current_app.AGENT_JSON_OK = getattr(current_app, 'AGENT_JSON_OK', 0) + 1
    except:
        pass

def increment_agent_json_fail():
    """Increment AGENT_JSON_FAIL counter"""
    try:
        from flask import current_app
        current_app.AGENT_JSON_FAIL = getattr(current_app, 'AGENT_JSON_FAIL', 0) + 1
    except:
        pass


def retry_on_503(func, max_retries=3, base_delay=1.0, *args, **kwargs):
    """
    一時的な失敗時のリトライ処理ラッパー。
    - HTTP 503 を指数バックオフで再試行
    - ReadTimeout / ConnectTimeout / ConnectionError も一時的エラーとして再試行
    最大回数に達した場合は最後の例外を再発生させる。
    """
    import random
    last_exception = None

    for attempt in range(max_retries + 1):  # 初回 + リトライ回数
        try:
            return func(*args, **kwargs)
        except requests.RequestException as e:
            last_exception = e
            # 例外タイプ判定
            is_timeout = isinstance(e, (requests.ReadTimeout, requests.ConnectTimeout, requests.Timeout))
            is_conn_err = isinstance(e, requests.ConnectionError)
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)

            transient = (status_code == 503) or is_timeout or is_conn_err
            if not transient:
                # それ以外は即時再発生
                raise

            # 最大リトライ回数に達した場合は例外を再発生
            if attempt >= max_retries:
                kind = (
                    '503' if status_code == 503 else
                    'timeout' if is_timeout else
                    'connection'
                )
                logger.warning(f"{kind} retry exhausted after {max_retries} attempts, giving up")
                raise

            # 指数バックオフで待機
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            kind = (
                '503' if status_code == 503 else
                'timeout' if is_timeout else
                'connection'
            )
            logger.info(f"Transient {kind} error, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries + 1})")
            sleep(delay)
        except Exception:
            # requests以外の例外（JSON解析エラーなど）はすぐに再発生
            raise

    # ここには到達しないはずだが、念のため
    if last_exception:
        raise last_exception


def call_gemini_api(prompt: str, model_name: str = 'gemini-2.5-flash') -> Dict[str, Any]:
    """
    Gemini APIをRESTで呼び出す共通関数。503エラー時は自動リトライを行う。
    """
    # 毎回最新の環境変数を参照し、誤検知（プロセス起動後に設定変更された場合など）を避ける
    _api_key = os.getenv("GEMINI_API_KEY")
    if not _api_key or _api_key == "YOUR_API_KEY_HERE":
        raise Exception("GEMINI_API_KEY is not configured.")

    def _make_request():
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model_name}:generateContent?key={_api_key}"
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        return response.json()
    
    return retry_on_503(_make_request)


def balanced_first_object(seg: str) -> Optional[str]:
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


def extract_json_passthrough(s: str) -> Optional[Dict[str, Any]]:
    """最初と最後の ``` を抜いて、必要なら先頭の 'json' トークンを落とし、そのままJSONを返す。
    返り値: dict または None（失敗時）。
    """
    try:
        if not isinstance(s, str) or not s.strip():
            return None
        txt = s.strip()
        # 末尾のフェンスブロックがあれば中身を使う
        m = re.findall(r"```\s*([\s\S]*?)\s*```", txt)
        if m:
            txt = m[-1].strip()
        # 全体が引用で囲まれていれば剥がす
        if (txt.startswith('"') and txt.endswith('"')) or (txt.startswith("'") and txt.endswith("'")):
            txt = txt[1:-1].strip()
        # 先頭の 'json' または 'JSON' トークンを落とす（任意の空白/記号をスキップし最初の '{' まで進める）
        if txt.lower().startswith('json'):
            # 'json' の後ろから最初の '{' を探す
            brace = txt.find('{')
            if brace != -1:
                txt = txt[brace:]
        # 先頭の '{' から末尾の '}' までを抽出
        start = txt.find('{')
        end = txt.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        cand = txt[start:end+1]
        obj = json.loads(cand)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def extract_trailing_json(s: str) -> Tuple[str, Optional[List], Optional[Dict], Optional[str]]:
    """Extract JSON from agent reply in a simple, robust order.
    Returns (prefix_text, places, route_info, text_field).
    Strategy:
      1) Parse the last fenced ```json block
    """
    
    def strip_citations(txt: str) -> str:
        return re.sub(r"(?:\s*\[[0-9,\s]+\])+\s*$", "", txt or "")

    def attach(obj: dict):
        """Attach structured data to Flask g context if available"""
        if not isinstance(obj, dict):
            return
        try:
            from flask import g as _flask_g
            summary = obj.get('summary') if isinstance(obj.get('summary'), str) else None
            plans = obj.get('plans') if isinstance(obj.get('plans'), list) else None
            plans_norm = []
            # advisor系: suggestions / updated_schedule / response_type を取り込む
            suggestions_raw = obj.get('suggestions') if isinstance(obj.get('suggestions'), list) else None
            updated_schedule_raw = (
                obj.get('updated_schedule')
                if (isinstance(obj.get('updated_schedule'), list) or isinstance(obj.get('updated_schedule'), dict))
                else (obj.get('updatedSchedule') if (isinstance(obj.get('updatedSchedule'), list) or isinstance(obj.get('updatedSchedule'), dict)) else None)
            )
            response_type = obj.get('response_type') or obj.get('responseType')

            def norm_itinerary(v):
                out = []
                if isinstance(v, list):
                    for day_blk in v[:14]:
                        if not isinstance(day_blk, dict):
                            continue
                        day = day_blk.get('day') or day_blk.get('day_number') or day_blk.get('dayNumber')
                        try:
                            day = int(day)
                        except Exception:
                            day = None
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
                                if isinstance(time_s, (int, float)):
                                    if 0 <= time_s < 24:
                                        time_s = f"{int(time_s):02d}:00"
                                    else:
                                        time_s = str(time_s)
                                if not isinstance(time_s, str):
                                    time_s = None
                                detail = it.get('detail') or it.get('desc') or it.get('description')
                                if not isinstance(detail, str):
                                    detail = None
                                its.append({
                                    'time': time_s,
                                    'title': title.strip(),
                                    'detail': detail.strip() if detail else None
                                })
                        out.append({'day': day, 'items': its})
                return out

            if plans:
                for p in plans[:6]:
                    if not isinstance(p, dict):
                        continue
                    title = p.get('title') if isinstance(p.get('title'), str) else None
                    if not title:
                        continue
                    tags = p.get('tags') if isinstance(p.get('tags'), list) else []
                    tags = [str(t) for t in tags if isinstance(t, (str, int, float))][:8]
                    brief = p.get('brief') if isinstance(p.get('brief'), str) else None
                    itin = norm_itinerary(p.get('itinerary'))
                    pls = normalize_places_list(p.get('places'))
                    rinfo = normalize_route_info(p.get('route_info') or p.get('route') or p.get('routeInfo'))
                    text_body = p.get('text') if isinstance(p.get('text'), str) else None
                    plans_norm.append({
                        'title': title.strip(),
                        'tags': tags,
                        'brief': brief.strip() if brief else None,
                        'itinerary': itin or [],
                        'places': pls or [],
                        'route_info': rinfo,
                        'text': text_body
                    })
            
            # suggestions の正規化
            suggestions_norm = []
            if isinstance(suggestions_raw, list):
                for s_it in suggestions_raw[:20]:
                    if isinstance(s_it, str):
                        txt = s_it.strip()
                        if txt:
                            suggestions_norm.append(txt)
                    elif isinstance(s_it, dict):
                        # 代表的な形: {text, title}
                        t = s_it.get('text') or s_it.get('title') or s_it.get('suggestion')
                        if isinstance(t, str) and t.strip():
                            suggestions_norm.append(t.strip())
            
            # updated_schedule の正規化（配列 または {itinerary: [...]}）
            itinerary_norm = []
            if isinstance(updated_schedule_raw, dict):
                if isinstance(updated_schedule_raw.get('itinerary'), list):
                    itinerary_norm = norm_itinerary(updated_schedule_raw.get('itinerary')) or []
                else:
                    # 単なる items リストのみの場合は day=1 扱い
                    items_raw = updated_schedule_raw.get('items') or []
                    if isinstance(items_raw, list):
                        itinerary_norm = norm_itinerary([{'day': 1, 'items': items_raw}]) or []
            elif isinstance(updated_schedule_raw, list):
                itinerary_norm = norm_itinerary(updated_schedule_raw) or []

            if _flask_g is not None and (summary or plans_norm or suggestions_norm or itinerary_norm or response_type):
                _flask_g.agent_struct = {
                    'summary': summary,
                    'plans': plans_norm,
                    'suggestions': suggestions_norm,
                    'itinerary': itinerary_norm,
                    'response_type': response_type if isinstance(response_type, str) else None,
                }
        except Exception:
            pass

    def extract_from_obj(obj: dict):
        places = obj.get('places') if isinstance(obj, dict) else None
        if places is None and isinstance(obj, dict):
            places = obj.get('place')
        route_info = obj.get('route_info') if isinstance(obj, dict) else None
        if route_info is None and isinstance(obj, dict):
            route_info = obj.get('route') or obj.get('routeInfo')
        # 本文: text が無ければ advisor 系の assistant_message を採用
        text_field = obj.get('text') if isinstance(obj, dict) else None
        if text_field is None and isinstance(obj, dict):
            am = obj.get('assistant_message') or obj.get('assistantMessage')
            if isinstance(am, str) and am.strip():
                text_field = am
        attach(obj)
        places = normalize_places_list(places)
        route_info = normalize_route_info(route_info)
        return places, route_info, (text_field if isinstance(text_field, str) else None)

    s = strip_citations(s or "")
    stripped = s.strip()

    # 1) Last fenced block
    fenced_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped)
    if fenced_blocks:
        blk = fenced_blocks[-1]
        try:
            obj = json.loads(blk.strip())
            if isinstance(obj, dict):
                places, rinfo, text_field = extract_from_obj(obj)
                last_idx = stripped.rfind('```')
                prefix = stripped[:last_idx].rstrip() if last_idx != -1 else ''
                return prefix, places, rinfo, text_field
        except Exception:
            pass

    return stripped, None, None, None


def call_adk_agent_chat(
    app_name: str,
    user_id: str,
    session_id: str,
    message_text: str,
    timeout_sec: int = 60,
    base_url: Optional[str] = None,
    ensure_session: bool = True,
    prefix: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """ADK api_server に従った呼び出し手順でチャット実行。
    1) /apps/{app_name}/users/{user_id}/sessions/{session_id} に空ボディPOSTでセッション作成（任意/冪等）
    2) /run に { app_name, user_id, session_id, new_message } をPOST
    戻り値: events配列（最終応答はevents内のmodelメッセージ）

    環境変数:
    - AGENT_BASE_URL: エージェントAPIベースURL（base_url未指定時に使用）
    - AGENT_API_KEY: 認可ヘッダ付与に使用（任意）
    - CLOUD_LOG_FULL_PAYLOAD: '1' のとき応答ログをフルに出力
    """
    AGENT_BASE_URL = base_url or os.getenv("AGENT_BASE_URL")
    AGENT_API_KEY = os.getenv("AGENT_API_KEY")
    if not AGENT_BASE_URL:
        raise Exception("Agent base URL is not configured.")

    headers = { 'Content-Type': 'application/json' }
    if AGENT_API_KEY:
        headers['Authorization'] = f"Bearer {AGENT_API_KEY}"

    bridge_logger = logging.getLogger("agent_bridge")
    LOG_PAYLOADS = True
    FULL_PAYLOAD = (os.getenv('CLOUD_LOG_FULL_PAYLOAD') == '1')

    base = AGENT_BASE_URL.rstrip('/')

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
        retry_on_503(_create_session)
    else:
        bridge_logger.info("Skip create session (already initialized on server side)")

    # 3) 実行
    def _run_agent():
        run_url = f"{base}/run"
        # 応答スキーマの前置き注記（上書き可能）。None の場合はデフォルトスキーマ、"" なら前置きなし
        default_prefix = ""
        prefix_to_use = default_prefix if prefix is None else prefix
        payload = {
            "app_name": app_name,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": { "role": "user", "parts": [{"text": (prefix_to_use + message_text) if prefix_to_use else message_text}] }
        }
        bridge_logger.info(f"Run agent: POST {run_url} app={app_name} user={user_id} session={session_id} msg_len={len(message_text)}")
        if LOG_PAYLOADS:
            try:
                bridge_logger.info(f"Run payload: {snip_json(payload)}")
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
    bridge_logger.debug(f"Raw agent response: {snip_json(j)}")
    if LOG_PAYLOADS:
        try:
            if FULL_PAYLOAD:
                bridge_logger.info(f"Run response(full): {snip_json(j)}")
            else:
                bridge_logger.info(f"Run response: {snip_text(snip_json(j), 1200)}")
        except Exception:
            pass
    # 期待形式は events のリスト
    if not isinstance(j, list):
        # 互換: v1/chat など別APIの戻りを透過してしまった場合
        raise RuntimeError("Unexpected agent response shape (expected list of events)")
    return j