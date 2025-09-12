"""Data processing and normalization utilities"""
import json
import re
from typing import Optional, List, Dict, Any, Union


def to_float(v) -> Optional[float]:
    """Convert value to float safely"""
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def normalize_places_list(raw) -> Optional[List[Dict[str, Any]]]:
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
                    out.append({'name': item, 'lat': None, 'lng': None})
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
                    'lat': to_float(lat),
                    'lng': to_float(lng),
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


def normalize_route_info(obj) -> Optional[Dict[str, Any]]:
    """Normalize route information"""
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
        if mode not in ('driving', 'walking', 'bicycling', 'transit'):
            mode = None
    else:
        mode = None
    if not origin and not dest:
        return None
    out = {'origin': origin, 'destination': dest}
    if wps:
        out['waypoints'] = wps
    if mode:
        out['mode'] = mode
    return out


def sanitize_title(s: str) -> str:
    """Sanitize title text"""
    try:
        s = str(s or '').strip()
        # Remove control chars and angle brackets
        s = re.sub(r'[\x00-\x1F<>]', '', s)
        return s[:120]
    except Exception:
        return ''


def sanitize_text(s: str) -> str:
    """Sanitize long text content"""
    try:
        s = str(s or '')
        # Limit very long texts (frontend has full copy anyway)
        if len(s) > 200000:
            s = s[:200000]
        return s
    except Exception:
        return ''


def snip_text(s: str, limit: int = 2000) -> str:
    """Truncate text with indication of remaining characters"""
    try:
        if s is None:
            return "null"
        if len(s) <= limit:
            return s
        more = len(s) - limit
        return s[:limit] + f"...(+{more} chars)"
    except Exception:
        return str(s)[:limit]


SENSITIVE_KEYS = {"password", "pass", "token", "authorization", "api_key", "apikey", "secret", "jwt"}


def sanitize(obj, depth: int = 0, max_depth: int = 5):
    """Recursively sanitize objects for logging, removing sensitive data"""
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
                    out[key] = sanitize(v, depth + 1, max_depth)
            return out
        if isinstance(obj, list):
            return [sanitize(v, depth + 1, max_depth) for v in obj]
        if isinstance(obj, (int, float)):
            return obj
        if isinstance(obj, str):
            return obj
        return str(obj)
    except Exception:
        return str(obj)


def snip_json(obj, limit: int = 2000) -> str:
    """Convert object to JSON string with truncation and sanitization"""
    try:
        s = json.dumps(sanitize(obj), ensure_ascii=False, default=str)
    except Exception:
        try:
            s = str(obj)
        except Exception:
            s = "<unserializable>"
    return snip_text(s, limit)