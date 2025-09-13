"""Authentication utilities"""
import os
import jwt
from datetime import datetime, timedelta, timezone
from flask import request
from typing import Optional, Dict, Any

# JWT configuration
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"
_jwt_from_env = os.getenv("JWT_SECRET")

if ENV.lower() == "development":
    JWT_SECRET = _jwt_from_env or "dev-secret-change-me"
else:
    if not _jwt_from_env or _jwt_from_env == "dev-secret-change-me":
        raise RuntimeError("JWT_SECRET environment variable must be set in production.")
    JWT_SECRET = _jwt_from_env

JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "2880"))  # 48h


def create_jwt(user_id: str) -> str:
    """Create a JWT token for the given user ID"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MIN)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_jwt_with_ttl(user_id: str, ttl_min: int) -> str:
    """Create a JWT token with custom TTL"""
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