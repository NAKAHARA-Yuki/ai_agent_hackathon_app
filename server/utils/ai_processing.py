"""AI and text processing utilities"""
import json
import re
import os
import requests
import logging
from time import sleep
from typing import Optional, Dict, Any, Tuple, List
from .data_processing import normalize_places_list, normalize_route_info

logger = logging.getLogger(__name__)

# Gemini API configuration
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
    HTTP 503エラー時のリトライ処理ラッパー。
    指数バックオフでリトライし、最大回数に達した場合は最後の例外を再発生させる。
    """
    import random
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