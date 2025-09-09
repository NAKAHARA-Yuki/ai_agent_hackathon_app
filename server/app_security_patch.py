"""
セキュリティパッチ - 既存のapp.pyに追加するセキュリティ強化コード
このファイルの内容を既存のapp.pyに統合してください
"""

# セキュリティミドルウェアのインポート（app.pyの先頭に追加）
try:
    from security_middleware import SecurityMiddleware, rate_limit, security_log, jwt_required
    SECURITY_MIDDLEWARE_AVAILABLE = True
except ImportError:
    SECURITY_MIDDLEWARE_AVAILABLE = False
    logging.warning("Security middleware not available - using basic security")

# app作成後に追加（既存のapp = Flask(__name__)の後）
if SECURITY_MIDDLEWARE_AVAILABLE:
    # セキュリティミドルウェアを初期化
    security = SecurityMiddleware(app)
    logging.info("Security middleware enabled")
else:
    # フォールバック：基本的なセキュリティヘッダーのみ
    @app.after_request
    def add_basic_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY' 
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

# セキュリティログ関数を既存関数から呼び出すための統合コード
def log_auth_failure(user_id=None, reason=""):
    """認証失敗のセキュリティログ記録"""
    if SECURITY_MIDDLEWARE_AVAILABLE:
        security_log('auth_failure', {
            'user_id': user_id, 
            'reason': reason,
            'ip': request.headers.get('X-Forwarded-For', request.remote_addr)
        })
    else:
        logger.warning(f"Auth failure: user_id={user_id}, reason={reason}")

def log_suspicious_activity(activity_type, details=None):
    """怪しい活動のログ記録"""
    if SECURITY_MIDDLEWARE_AVAILABLE:
        security_log(activity_type, details)
    else:
        logger.warning(f"Suspicious activity: {activity_type}, details={details}")

# 既存のlogin関数への統合例（実際のコードでは対応する部分を修正）
"""
# 元のlogin関数内で認証失敗時に以下を追加:
if not user_doc.exists:
    log_auth_failure(user_id, "user_not_found")
    return jsonify({"error": "invalid credentials"}), 401

user_data = user_doc.to_dict() or {}
stored_hash = user_data.get('password_hash')
if not stored_hash or not check_password_hash(stored_hash, password):
    log_auth_failure(user_id, "invalid_password")
    return jsonify({"error": "invalid credentials"}), 401
"""

# レート制限を適用したい関数の例（実際のコードでは@rate_limit()を追加）
"""
@app.route('/api/auth/login', methods=['POST'])
@rate_limit(requests_per_minute=10)  # ログインは10回/分に制限
def login():
    # 既存のコード...
"""

"""
@app.route('/api/auth/signup', methods=['POST']) 
@rate_limit(requests_per_minute=5)   # サインアップは5回/分に制限
def signup():
    # 既存のコード...
"""

# セキュリティ設定の確認エンドポイント（/api/healthに追加情報として統合可能）
def get_security_status():
    """セキュリティ設定の状態を返す"""
    return {
        "security_middleware_enabled": SECURITY_MIDDLEWARE_AVAILABLE,
        "rate_limiting_enabled": SECURITY_MIDDLEWARE_AVAILABLE,
        "security_headers_enabled": True,
        "jwt_configured": bool(JWT_SECRET),
        "environment": ENV
    }

# 既存の/api/healthエンドポイントに追加する情報
"""
# 既存のhealth関数に以下を追加:
security_status = get_security_status()
return jsonify({
    "status": "ok",
    "env": ENV,
    "db": db_kind,
    "gemini_configured": genai_configured,
    "jwt_configured": bool(JWT_SECRET),
    "security": security_status,  # 追加
    "agent_json_metrics": {"ok": AGENT_JSON_OK, "fail": AGENT_JSON_FAIL}
})
"""