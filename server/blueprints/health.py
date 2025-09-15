"""Health check blueprint"""
import os
import logging
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

# Environment and configuration
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"
api_key = os.getenv("GEMINI_API_KEY")
genai_configured = bool(api_key and api_key != "YOUR_API_KEY_HERE")

# Import JWT_SECRET from auth utils
from utils.auth import JWT_SECRET

# Agent JSON metrics - we'll import these from app context
def get_agent_metrics():
    """Get agent JSON metrics from application context"""
    try:
        from flask import current_app
        return {
            "ok": getattr(current_app, 'AGENT_JSON_OK', 0),
            "fail": getattr(current_app, 'AGENT_JSON_FAIL', 0)
        }
    except:
        return {"ok": 0, "fail": 0}


@health_bp.route('/api/health', methods=['GET'])
def health():
    """Simple health check endpoint"""
    try:
        # Get database reference from current app
        from flask import current_app
        db = getattr(current_app, 'db', None)
        
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
            "agent_json_metrics": get_agent_metrics()
        })
    except Exception as e:
        logger.exception("/api/health error")
        return jsonify({"status": "error", "message": str(e)}), 500