# セキュリティ実装ガイド

## 🔒 概要

この文書では、旅行アプリケーションに実装されたセキュリティ強化機能について詳しく説明し、導入手順を提供します。

## 📋 実装内容

### 1. インフラストラクチャセキュリティ強化

#### VPCネットワーク分離
```
├── VPC: travel-app-vpc-{environment}
├── Private Subnet: 10.0.0.0/24 
├── Cloud NAT: セキュアな外部アクセス
├── VPC Connector: Cloud Run ⇔ VPC 接続
└── Firewall Rules: 最小権限通信のみ許可
```

#### IAMセキュリティ
```
├── App Service Account: travel-app-{env}@project.iam
├── Agent Service Account: travel-agent-{env}@project.iam  
├── MCP Service Account: travel-mcp-{env}@project.iam
├── Security Monitor SA: セキュリティ監視専用
└── GitHub Actions SA: デプロイ専用（Workload Identity）
```

#### Secret Manager統合
```
├── JWT Secret: travel-app-jwt-secret-{env}
├── Gemini API Key: travel-app-gemini-api-key-{env}
├── Google Maps API Key: travel-app-maps-api-key-{env}
└── DB Connection: travel-app-db-connection-{env}
```

### 2. アプリケーションセキュリティ強化

#### セキュリティミドルウェア
- **レート制限**: IP別リクエスト制限
- **セキュリティヘッダー**: XSS, CSRF, CSP対策
- **怪しいパターン検出**: SQLインジェクション、異常リクエスト
- **詳細ログ記録**: セキュリティイベント追跡

#### 認証強化
- **JWT強化**: より強力なシークレット管理
- **レート制限**: ログイン試行制限
- **セキュリティログ**: 認証失敗の詳細記録

### 3. セキュリティ監視

#### リアルタイム監視
- **セキュリティダッシュボード**: 攻撃パターンの可視化
- **自動アラート**: 異常検出時の即座通知
- **ログ集約**: BigQueryでの長期分析

## 🚀 導入手順

### Phase 1: インフラストラクチャセキュリティ

#### Step 1: 環境準備
```bash
# プロジェクト設定
export PROJECT_ID="your-gcp-project-id"
export ENVIRONMENT="prod"  # または "dev"
export REGION="asia-northeast1"
export SECURITY_EMAIL="security@your-domain.com"

# Google Cloud認証
gcloud auth login
gcloud config set project $PROJECT_ID
```

#### Step 2: セキュリティインフラのデプロイ
```bash
# 自動セットアップ（推奨）
cd infrastructure/scripts
chmod +x setup-infrastructure.sh
./setup-infrastructure.sh

# または手動セットアップ
cd infrastructure/terraform
terraform init
terraform plan -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"
terraform apply
```

#### Step 3: シークレット設定
```bash
# JWT Secret生成・設定
openssl rand -base64 32 | gcloud secrets create travel-app-jwt-secret-$ENVIRONMENT --data-file=-

# API Keys設定（実際の値に置き換え）
echo "YOUR_GEMINI_API_KEY" | gcloud secrets create travel-app-gemini-api-key-$ENVIRONMENT --data-file=-
echo "YOUR_MAPS_API_KEY" | gcloud secrets create travel-app-maps-api-key-$ENVIRONMENT --data-file=-
```

### Phase 2: アプリケーションセキュリティ

#### Step 1: セキュリティミドルウェア統合
```python
# server/app.py に以下を追加

# インポート部分に追加
try:
    from security_middleware import SecurityMiddleware, rate_limit, security_log
    SECURITY_MIDDLEWARE_AVAILABLE = True
except ImportError:
    SECURITY_MIDDLEWARE_AVAILABLE = False
    logging.warning("Security middleware not available")

# app作成後に追加
if SECURITY_MIDDLEWARE_AVAILABLE:
    security = SecurityMiddleware(app)
    logging.info("Security middleware enabled")
```

#### Step 2: 認証エンドポイントのレート制限
```python
# ログイン関数に@rate_limit追加
@app.route('/api/auth/login', methods=['POST'])
@rate_limit(requests_per_minute=10)  # 10回/分に制限
def login():
    # 既存コード...
    
    # 認証失敗時にセキュリティログ追加
    if not user_doc.exists:
        security_log('auth_failure', {'user_id': user_id, 'reason': 'user_not_found'})
        return jsonify({"error": "invalid credentials"}), 401
```

#### Step 3: セキュリティログ統合
```python
# 既存のエラーハンドリングにセキュリティログを追加
def log_security_event(event_type, details=None):
    if SECURITY_MIDDLEWARE_AVAILABLE:
        security_log(event_type, details)
    else:
        logger.warning(f"Security event: {event_type}, {details}")
```

### Phase 3: 監視・アラート設定

#### Step 1: セキュリティダッシュボード確認
```bash
# ダッシュボードURLを取得
terraform output security_dashboard_url

# またはコンソールから確認
# https://console.cloud.google.com/monitoring/dashboards
```

#### Step 2: アラート設定のテスト
```bash
# 認証失敗アラートのテスト
curl -X POST https://your-app-url/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"invalid","password":"invalid"}'
# 10回繰り返してアラート発火確認

# レート制限アラートのテスト  
for i in {1..20}; do
  curl https://your-app-url/api/health
done
```

### Phase 4: GitHub Actions セキュリティ設定

#### Step 1: Workload Identityプロバイダー設定
```bash
# Terraformで作成されたプロバイダーを確認
terraform output workload_identity_provider

# GitHub Secretsに設定
# GCP_WORKLOAD_IDENTITY_PROVIDER: プロバイダーの完全なリソース名
# GCP_SERVICE_ACCOUNT_EMAIL: github-actions-deploy-{env}@project.iam.gserviceaccount.com
```

#### Step 2: セキュアデプロイの有効化
```bash
# 新しいセキュアワークフローを使用
# .github/workflows/deploy-cloud-run-secure.yml が自動的に使用される
# または既存ワークフローを段階的に移行
```

## 🔧 カスタマイズ設定

### レート制限の調整
```python
# security_middleware.py で調整
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))

# または環境変数で設定
export RATE_LIMIT_REQUESTS=200
export RATE_LIMIT_WINDOW=120
```

### セキュリティヘッダーのカスタマイズ
```python
# Content Security Policy の調整
csp_policy = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://maps.googleapis.com; "
    # 必要に応じて追加ドメインを許可
)
```

### 監視閾値の調整
```hcl
# infrastructure/terraform/monitoring.tf で調整
variable "alert_thresholds" {
  default = {
    auth_failures = 10     # 認証失敗回数/5分
    request_rate = 1000    # リクエスト/分
    error_rate = 5         # エラー/10分
  }
}
```

## 🧪 セキュリティテスト

### 1. 脆弱性スキャンテスト
```bash
# Dockerイメージのスキャン
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image your-image:tag

# コードベースのスキャン
docker run --rm -v $(pwd):/app \
  aquasec/trivy fs /app
```

### 2. レート制限テスト
```bash
# 負荷テストツールでレート制限確認
ab -n 200 -c 10 https://your-app-url/api/health

# レスポンス確認（429 Too Many Requests が返ることを確認）
```

### 3. セキュリティヘッダーテスト
```bash
# セキュリティヘッダーの確認
curl -I https://your-app-url/

# 期待されるヘッダー:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Content-Security-Policy: ...
```

### 4. 認証セキュリティテスト
```bash
# 無効なJWTトークンテスト
curl -H "Authorization: Bearer invalid-token" \
  https://your-app-url/api/me

# 期待レスポンス: 401 Unauthorized
```

## 📊 セキュリティメトリクス

### 監視すべき指標
- **認証失敗率**: < 5% が正常
- **レート制限発生率**: < 1% が正常  
- **エラー率**: < 0.1% が正常
- **レスポンス時間**: < 200ms が目標
- **セキュリティイベント数**: 日次で監視

### ダッシュボードでの確認項目
1. **認証成功/失敗の比率**
2. **IP別リクエスト分布** 
3. **エラーログの分析**
4. **怪しいUser-Agentの検出**
5. **SQLインジェクション試行の検出**

## 🚨 インシデント対応手順

### 1. セキュリティアラート検知時
```bash
# 1. サービス状況確認
gcloud run services list --filter="metadata.labels.environment=$ENVIRONMENT"

# 2. 最近のログ確認
gcloud logging read 'resource.type="cloud_run_revision" severity>=ERROR' --limit=50

# 3. 必要に応じてトラフィック制限
gcloud run services update SERVICE_NAME --no-traffic
```

### 2. 攻撃検知時の緊急対応
```bash
# 1. 攻撃IPのブロック（ファイアウォールルール追加）
gcloud compute firewall-rules create block-attack-ip \
  --action=DENY \
  --source-ranges=ATTACKER_IP \
  --priority=100

# 2. 一時的な認証強化
# アプリケーションレベルでレート制限を厳格化
export RATE_LIMIT_REQUESTS=10
export RATE_LIMIT_WINDOW=60

# 3. セキュリティチームへの通知
# 設定済みのアラートが自動送信
```

## 💡 今後の拡張予定

### Phase 2 実装計画
- [ ] **WAF統合**: Cloud Armorとの連携
- [ ] **Redis統合**: スケーラブルなレート制限
- [ ] **OAuth2.0**: 外部プロバイダー認証
- [ ] **API Throttling**: より詳細なAPI制限

### Phase 3 実装計画  
- [ ] **ゼロトラスト**: すべての通信の認証・認可
- [ ] **動的セキュリティ**: AI/MLによる異常検知
- [ ] **コンプライアンス**: SOC2, ISO27001対応
- [ ] **自動復旧**: インシデント自動対応

## 🔗 関連リソース

### ドキュメント
- [SECURITY.md](./SECURITY.md) - 総合セキュリティガイド
- [infrastructure/README.md](./infrastructure/README.md) - インフラ詳細
- [server/security_middleware.py](./server/security_middleware.py) - セキュリティミドルウェア

### モニタリング
- **セキュリティダッシュボード**: Cloud Monitoring Console
- **ログ分析**: Cloud Logging Console
- **脆弱性管理**: Security Command Center

### サポート
- **GitHub Issues**: [セキュリティラベル](https://github.com/NAKAHARA-Yuki/ai_agent_hackathon_app/issues?q=label%3Asecurity)
- **セキュリティ報告**: security@example.com（非公開報告用）

---

**最終更新**: 2024年 - セキュリティは継続的な改善が重要です。定期的な見直しを実施してください。