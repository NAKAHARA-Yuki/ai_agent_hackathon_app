"""
セキュリティミドルウェア
認証、レート制限、セキュリティヘッダーの設定
"""

import os
import time
import logging
from functools import wraps
from collections import defaultdict, deque
from flask import request, jsonify, g
from datetime import datetime, timedelta, timezone
import jwt

logger = logging.getLogger(__name__)

# レート制限設定
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))  # リクエスト数
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))       # 時間窓（秒）

# レート制限ストレージ（本番環境ではRedisを推奨）
rate_limit_storage = defaultdict(deque)

class SecurityMiddleware:
    """セキュリティ機能を提供するミドルウェア"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Flaskアプリケーションにセキュリティミドルウェアを追加"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """リクエスト前の処理：レート制限、セキュリティチェック"""
        # リクエスト開始時刻を記録
        g.request_start_time = time.time()
        
        # セキュリティヘッダーのチェック
        self._check_security_headers()
        
        # レート制限チェック
        if not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded for IP: {self._get_client_ip()}")
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds'
            }), 429
        
        # 怪しいリクエストパターンの検出
        self._detect_suspicious_patterns()
    
    def after_request(self, response):
        """レスポンス後の処理：セキュリティヘッダー追加、ログ記録"""
        # セキュリティヘッダーを追加
        response = self._add_security_headers(response)
        
        # リクエストログを記録
        self._log_request()
        
        return response
    
    def _get_client_ip(self):
        """クライアントIPアドレスを取得（プロキシ考慮）"""
        # Cloud Run / Load Balancer環境での実際のIP取得
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote_addr or 'unknown'
    
    def _check_rate_limit(self):
        """レート制限チェック"""
        client_ip = self._get_client_ip()
        current_time = time.time()
        
        # IP別のリクエスト履歴を取得
        requests = rate_limit_storage[client_ip]
        
        # 時間窓外の古いリクエストを削除
        while requests and requests[0] <= current_time - RATE_LIMIT_WINDOW:
            requests.popleft()
        
        # リクエスト数をチェック
        if len(requests) >= RATE_LIMIT_REQUESTS:
            return False
        
        # 現在のリクエストを記録
        requests.append(current_time)
        return True
    
    def _check_security_headers(self):
        """セキュリティ関連ヘッダーのチェック"""
        # Content-Type チェック（JSONエンドポイント用）
        if request.method in ['POST', 'PUT', 'PATCH'] and request.path.startswith('/api/'):
            content_type = request.headers.get('Content-Type', '')
            if not content_type.startswith('application/json'):
                logger.warning(f"Invalid Content-Type: {content_type} from IP: {self._get_client_ip()}")
        
        # User-Agent チェック（botやスクレイパーの検出）
        user_agent = request.headers.get('User-Agent', '')
        suspicious_patterns = ['bot', 'crawler', 'spider', 'scraper', 'python-requests']
        if any(pattern in user_agent.lower() for pattern in suspicious_patterns):
            logger.info(f"Suspicious User-Agent detected: {user_agent} from IP: {self._get_client_ip()}")
    
    def _detect_suspicious_patterns(self):
        """怪しいリクエストパターンの検出"""
        # 大量のパラメータ（Parameter Pollution攻撃）
        if len(request.args) > 20:
            logger.warning(f"Too many query parameters ({len(request.args)}) from IP: {self._get_client_ip()}")
        
        # 異常に大きなリクエストボディ
        if request.content_length and request.content_length > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"Large request body ({request.content_length} bytes) from IP: {self._get_client_ip()}")
        
        # SQLインジェクション試行の検出
        suspicious_sql_patterns = ['union select', 'drop table', 'insert into', '1=1', 'or 1=1']
        query_string = request.query_string.decode('utf-8', errors='ignore').lower()
        for pattern in suspicious_sql_patterns:
            if pattern in query_string:
                logger.warning(f"Potential SQL injection attempt: {pattern} from IP: {self._get_client_ip()}")
                break
    
    def _add_security_headers(self, response):
        """セキュリティヘッダーを追加"""
        # XSS保護
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # HTTPS強制（本番環境のみ）
        env = os.getenv('FLASK_ENV', 'production')
        if env.lower() == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # CSP設定（Content Security Policy）
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://maps.googleapis.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://maps.googleapis.com https://maps.gstatic.com; "
            "connect-src 'self' https://maps.googleapis.com; "
            "frame-src 'none'"
        )
        response.headers['Content-Security-Policy'] = csp_policy
        
        # リファラーポリシー
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # 権限ポリシー
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response
    
    def _log_request(self):
        """リクエストログの記録"""
        request_time = time.time() - g.get('request_start_time', time.time())
        
        # セキュリティ関連の情報をログに記録
        log_data = {
            'ip': self._get_client_ip(),
            'method': request.method,
            'path': request.path,
            'user_agent': request.headers.get('User-Agent', ''),
            'response_time': f"{request_time:.3f}s",
            'status': getattr(g, 'response_status', 'unknown')
        }
        
        # 認証情報が存在する場合は追加
        if hasattr(g, 'current_user_id'):
            log_data['user_id'] = g.current_user_id
        
        logger.info(f"Request: {log_data}")


def rate_limit(requests_per_minute=60):
    """
    レート制限デコレータ
    
    Args:
        requests_per_minute: 1分間あたりの許可リクエスト数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            key = f"rate_limit:{client_ip}:{f.__name__}"
            current_time = time.time()
            
            # 簡易的なレート制限実装（本番ではRedis推奨）
            if not hasattr(g, 'rate_limits'):
                g.rate_limits = {}
            
            if key not in g.rate_limits:
                g.rate_limits[key] = deque()
            
            requests = g.rate_limits[key]
            
            # 1分以内のリクエストのみ保持
            while requests and requests[0] <= current_time - 60:
                requests.popleft()
            
            if len(requests) >= requests_per_minute:
                logger.warning(f"Rate limit exceeded for function {f.__name__} from IP: {client_ip}")
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            requests.append(current_time)
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def security_log(event_type, details=None):
    """
    セキュリティイベントのログ記録
    
    Args:
        event_type: イベントタイプ（例: 'auth_failure', 'suspicious_request'）
        details: 追加詳細情報
    """
    log_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_type': event_type,
        'ip': request.headers.get('X-Forwarded-For', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', ''),
        'path': request.path,
        'method': request.method,
        'security_event': True  # セキュリティログの識別用
    }
    
    if details:
        log_entry['details'] = details
    
    logger.warning(f"Security Event: {log_entry}")


# Flask-JWT-Extendedの代替となる軽量JWT実装
def jwt_required(optional=False):
    """
    JWT認証が必要なエンドポイント用デコレータ
    
    Args:
        optional: Trueの場合、認証は任意（ログイン状況の確認のみ）
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            
            if not auth_header.startswith('Bearer '):
                if optional:
                    g.current_user_id = None
                    return f(*args, **kwargs)
                
                security_log('auth_missing', {'endpoint': f.__name__})
                return jsonify({'error': 'Missing authorization header'}), 401
            
            token = auth_header.split(' ', 1)[1]
            
            try:
                # JWT検証ロジックは既存のverify_jwt関数を使用
                from app import verify_jwt
                payload = verify_jwt(token)
                
                if not payload:
                    raise jwt.InvalidTokenError("Invalid token")
                
                g.current_user_id = payload.get('sub')
                return f(*args, **kwargs)
                
            except jwt.ExpiredSignatureError:
                security_log('auth_expired', {'endpoint': f.__name__})
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                security_log('auth_invalid', {'endpoint': f.__name__})
                return jsonify({'error': 'Invalid token'}), 401
            except Exception as e:
                logger.error(f"JWT verification error: {e}")
                security_log('auth_error', {'endpoint': f.__name__, 'error': str(e)})
                return jsonify({'error': 'Authentication error'}), 401
        
        return decorated_function
    return decorator