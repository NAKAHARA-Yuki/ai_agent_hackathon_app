# インフラストラクチャ セキュリティ強化

このディレクトリには、旅行アプリケーションのセキュリティを強化するためのインフラストラクチャ設定が含まれています。

## 📁 構造

```
infrastructure/
├── terraform/              # Terraformによるインフラ定義
│   ├── main.tf             # VPC、ネットワーク設定
│   ├── iam.tf              # IAM、サービスアカウント設定
│   ├── secrets.tf          # Secret Manager設定
│   ├── cloud_run.tf        # セキュアなCloud Run設定
│   ├── monitoring.tf       # セキュリティ監視設定
│   ├── outputs.tf          # 出力値定義
│   └── terraform.tfvars.example  # 設定例
├── scripts/                # デプロイスクリプト
│   └── setup-infrastructure.sh  # 自動セットアップスクリプト
└── README.md               # このファイル
```

## 🚀 クイックスタート

### 1. 前提条件

必要なツールをインストール:
```bash
# Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Terraform
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

### 2. 自動セットアップ（推奨）

```bash
# 環境変数設定
export PROJECT_ID="your-gcp-project-id"
export ENVIRONMENT="prod"  # または "dev"
export REGION="asia-northeast1"
export SECURITY_EMAIL="security@your-domain.com"

# Google Cloudにログイン
gcloud auth login
gcloud config set project $PROJECT_ID

# 自動セットアップ実行
cd infrastructure/scripts
chmod +x setup-infrastructure.sh
./setup-infrastructure.sh
```

### 3. 手動セットアップ

#### Step 1: Terraform設定

```bash
cd infrastructure/terraform

# 設定ファイル作成
cp terraform.tfvars.example terraform.tfvars

# terraform.tfvarsを編集
vim terraform.tfvars
```

#### Step 2: Terraform実行

```bash
# 初期化
terraform init

# プラン確認
terraform plan -var-file="terraform.tfvars"

# 適用
terraform apply -var-file="terraform.tfvars"
```

#### Step 3: シークレット設定

```bash
# JWT Secret
openssl rand -base64 32 | gcloud secrets create travel-app-jwt-secret-prod --data-file=-

# API Keys (実際の値に置き換え)
echo "YOUR_GEMINI_API_KEY" | gcloud secrets create travel-app-gemini-api-key-prod --data-file=-
echo "YOUR_MAPS_API_KEY" | gcloud secrets create travel-app-maps-api-key-prod --data-file=-
```

## 🔒 セキュリティ機能

### ネットワークセキュリティ
- **VPC分離**: 専用VPCでアプリケーションを分離
- **プライベート通信**: サービス間通信をVPC内に限定
- **ファイアウォール**: 必要最小限の通信のみ許可
- **Cloud NAT**: セキュアな外部アクセス

### 認証・認可
- **専用サービスアカウント**: サービスごとに最小権限アカウント
- **Workload Identity**: GitHub Actionsからのセキュアなデプロイ
- **IAM詳細権限**: 必要最小限の権限のみ付与

### シークレット管理
- **Secret Manager**: すべての機密情報を安全に管理
- **アクセス制御**: サービスごとに必要なシークレットのみアクセス可能
- **監査ログ**: シークレットアクセスをすべてログ記録

### 監視・アラート
- **セキュリティダッシュボード**: リアルタイム監視
- **自動アラート**: 異常検出時に即座に通知
- **ログ集約**: セキュリティ関連ログをBigQueryに集約

## 🔧 カスタマイズ

### 環境別設定

```bash
# 開発環境用
export ENVIRONMENT="dev"
terraform workspace new dev
terraform apply -var="environment=dev"

# 本番環境用
export ENVIRONMENT="prod" 
terraform workspace new prod
terraform apply -var="environment=prod"
```

### リージョン変更

```bash
# terraform.tfvars で設定
region = "us-central1"  # または他のリージョン
```

### セキュリティレベル調整

監視閾値の調整:
```hcl
# monitoring.tf で調整
variable "alert_thresholds" {
  type = object({
    auth_failures    = number
    request_rate     = number
    error_rate       = number
  })
  default = {
    auth_failures = 10    # 認証失敗回数
    request_rate  = 1000  # リクエスト/分
    error_rate    = 5     # エラー/分
  }
}
```

## 🚨 トラブルシューティング

### よくある問題

#### 1. API有効化エラー
```bash
# 必要なAPIを手動で有効化
gcloud services enable compute.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable vpcaccess.googleapis.com
```

#### 2. 権限不足エラー
```bash
# 現在の権限確認
gcloud projects get-iam-policy $PROJECT_ID

# 必要な権限を付与（プロジェクトオーナーが実行）
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/editor"
```

#### 3. VPCコネクタ作成失敗
```bash
# サブネット確認
gcloud compute networks subnets list --network=travel-app-vpc-prod

# 手動でコネクタ作成
gcloud compute networks vpc-access connectors create travel-app-connector-prod \
  --region=asia-northeast1 \
  --subnet=travel-app-private-prod \
  --subnet-project=$PROJECT_ID
```

### ログ確認

```bash
# Terraform実行ログ
export TF_LOG=DEBUG
terraform apply

# Cloud Run デプロイログ
gcloud run services describe SERVICE_NAME --region=REGION

# セキュリティ監視ログ
gcloud logging read 'resource.type="cloud_run_revision" severity>=ERROR'
```

## 📚 参考資料

### Google Cloud セキュリティベストプラクティス
- [Cloud Run セキュリティ](https://cloud.google.com/run/docs/security)
- [VPC セキュリティ](https://cloud.google.com/vpc/docs/vpc)
- [IAM ベストプラクティス](https://cloud.google.com/iam/docs/using-iam-securely)
- [Secret Manager](https://cloud.google.com/secret-manager/docs)

### Terraformドキュメント
- [Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Run リソース](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_service)
- [VPC リソース](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_network)

## 💡 次のステップ

1. **セキュリティ監査**: 定期的なセキュリティ設定レビュー
2. **パフォーマンス最適化**: 監視データを基にした最適化
3. **災害復旧**: バックアップとリストア戦略の実装
4. **コンプライアンス**: 規制要件に応じた設定調整

## 🆘 サポート

問題や質問がある場合:
- **GitHub Issues**: [新しいissueを作成](https://github.com/NAKAHARA-Yuki/ai_agent_hackathon_app/issues)
- **セキュリティ問題**: security@example.com へ非公開で報告