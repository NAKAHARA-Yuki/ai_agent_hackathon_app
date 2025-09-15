"""Maps and geocoding blueprint"""
import os
import re
import logging
import requests
from flask import Blueprint, request, jsonify, Response

logger = logging.getLogger(__name__)

maps_bp = Blueprint('maps', __name__)


@maps_bp.get('/api/maps-key')
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
        m = re.match(r'^([A-Za-z0-9_\-]+)', key)
        if m:
            key = m.group(1)
    except Exception:
        pass
    # mapId の取得とサニタイズ（Advanced Marker で推奨）
    map_id = os.getenv('VITE_GOOGLE_MAPS_MAP_ID') or os.getenv('GOOGLE_MAPS_MAP_ID') or ''
    try:
        map_id = (map_id or '').strip()
        m2 = re.match(r'^([A-Za-z0-9_\-]+)', map_id)
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
    adv = str(adv_env).strip().lower() in ['1', 'true', 'yes', 'on']
    # mapId 未設定なら Advanced を無効化（警告抑止と確実性のため）
    if not map_id:
        adv = False
    return jsonify({'key': key, 'mapId': map_id, 'advanced': adv})


@maps_bp.post('/api/geocode')
def geocode_places():
    """地名の配列を受け取って緯度経度に解決する。Google Geocoding APIキーはフロントのVITE_キーとは別管理のため、
    サーバー側で x-goog-api-key として GEMINI_API_KEY を使わず、環境変数 GOOGLE_MAPS_API_KEY があれば使用する。
    形式: { names: ["箱根温泉", ...] } -> { results: [{ name, lat, lng, formatted_address }] }
    """
    try:
        data = request.get_json() or {}
        names = data.get('names') or []
        if not isinstance(names, list) or not names:
            return jsonify({'results': []})
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
                            results.append({'name': nm, 'lat': lat, 'lng': lon, 'formatted_address': disp})
                except Exception:
                    continue
            return jsonify({'results': results})
        # Google Geocoding を使用
        for nm in names[:20]:
            try:
                url = 'https://maps.googleapis.com/maps/api/geocode/json'
                params = {'address': nm, 'key': api_key, 'language': 'ja'}
                r = requests.get(url, params=params, timeout=10)
                if r.ok:
                    j = r.json()
                    if j.get('results'):
                        g = j['results'][0]
                        loc = g['geometry']['location']
                        results.append({'name': nm, 'lat': loc['lat'], 'lng': loc['lng'], 'formatted_address': g.get('formatted_address')})
            except Exception:
                continue
        return jsonify({'results': results})
    except Exception as e:
        logger.exception("geocode error")
        return jsonify({'results': []})


@maps_bp.get('/api/maps/static')
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
        return jsonify({'error': 'maps_key_not_configured'}), 400
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
    if zoom:
        params['zoom'] = zoom
    if center:
        params['center'] = center
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
            return jsonify({'error': 'upstream_error', 'status': r.status_code}), 502
        return Response(r.content, content_type=f'image/{fmt}')
    except Exception as e:
        logger.exception("Static Maps request_failed")
        return jsonify({'error': 'request_failed', 'message': str(e)}), 500