"""Authentication utilities"""
import os
import jwt
from datetime import datetime, timedelta, timezone
from flask import request
from typing import Optional, Dict, Any

# JWT configuration
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"
_jwt_from_env = os.getenv("JWT_SECRET")

# In production, don't crash the whole app at import-time if JWT is misconfigured.
# Keep the app up (so /api/health works) and fail fast when token ops are used.
if ENV.lower() == "development":
    JWT_SECRET = _jwt_from_env or "dev-secret-change-me"
    JWT_READY = bool(_jwt_from_env)
else:
    if not _jwt_from_env or _jwt_from_env == "dev-secret-change-me":
        # Defer failure to token creation/verification time and log an error.
        import logging as _logging
        _logging.getLogger(__name__).error(
            "JWT_SECRET is not set or uses default in production; auth endpoints will be disabled until configured."
        )
        JWT_SECRET = None
        JWT_READY = False
    else:
        JWT_SECRET = _jwt_from_env
        JWT_READY = True

JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "2880"))  # 48h


def create_jwt(user_id: str) -> str:
    """Create a JWT token for the given user ID"""
    if not JWT_SECRET:
        raise RuntimeError("JWT not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MIN)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_jwt_with_ttl(user_id: str, ttl_min: int) -> str:
    """Create a JWT token with custom TTL"""
    if not JWT_SECRET:
        raise RuntimeError("JWT not configured")
    now = datetime.now(timezone.utc)
    ttl_min = max(1, min(int(ttl_min or 15), 24 * 60))
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_min)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token"""
    try:
        if not JWT_SECRET:
            raise RuntimeError("JWT not configured")
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def require_auth(req) -> Optional[Dict[str, Any]]:
    """Extract and verify JWT from Authorization header"""
    authz = req.headers.get("Authorization", "")
    if authz.startswith("Bearer "):
        token = authz.split(" ", 1)[1]
        return verify_jwt(token)
    return None


def claims_or_dev() -> Optional[Dict[str, Any]]:
    """Return JWT claims if present; in development, fall back to a dummy dev user.
    This avoids 401 spam in local no-auth sessions.
    """
    claims = require_auth(request)
    if claims:
        return claims
    if (os.getenv("FLASK_ENV", "").lower() == "development") or (ENV.lower() == "development"):
        return {'sub': 'devuser'}
    return None