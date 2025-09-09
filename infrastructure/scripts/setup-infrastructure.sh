#!/bin/bash
# 旅行アプリ - インフラセキュリティ設定スクリプト
# VPC、認証、セキュリティポリシーの一括セットアップ

set -euo pipefail

# カラー出力設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 必要なツールの確認
check_prerequisites() {
    log_info "前提条件をチェック中..."
    
    # gcloud CLI の確認
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI が見つかりません。Google Cloud SDK をインストールしてください。"
        exit 1
    fi
    
    # terraform の確認
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform が見つかりません。Terraform をインストールしてください。"
        exit 1
    fi
    
    # jq の確認
    if ! command -v jq &> /dev/null; then
        log_warning "jq が見つかりません。一部の機能が制限される可能性があります。"
    fi
    
    log_success "前提条件チェック完了"
}

# Google Cloud プロジェクト設定の確認
check_gcloud_auth() {
    log_info "Google Cloud 認証状態をチェック中..."
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
        log_error "Google Cloud にログインしていません。'gcloud auth login' を実行してください。"
        exit 1
    fi
    
    local current_project
    current_project=$(gcloud config get-value project 2>/dev/null || echo "")
    
    if [[ -z "$current_project" ]]; then
        log_error "Google Cloud プロジェクトが設定されていません。'gcloud config set project PROJECT_ID' を実行してください。"
        exit 1
    fi
    
    log_success "Google Cloud 認証済み (プロジェクト: $current_project)"
    export PROJECT_ID="$current_project"
}

# パラメータの設定
setup_parameters() {
    log_info "デプロイメントパラメータを設定中..."
    
    # 環境の確認
    if [[ -z "${ENVIRONMENT:-}" ]]; then
        log_warning "ENVIRONMENT 変数が設定されていません。デフォルトで 'prod' を使用します。"
        export ENVIRONMENT="prod"
    fi
    
    # リージョンの確認
    if [[ -z "${REGION:-}" ]]; then
        export REGION="asia-northeast1"
        log_info "デフォルトリージョンを使用: $REGION"
    fi
    
    # セキュリティ通知メールの確認
    if [[ -z "${SECURITY_EMAIL:-}" ]]; then
        log_warning "SECURITY_EMAIL が設定されていません。デフォルト値を使用します。"
        export SECURITY_EMAIL="security@example.com"
    fi
    
    log_success "パラメータ設定完了"
    log_info "プロジェクト: $PROJECT_ID"
    log_info "環境: $ENVIRONMENT"
    log_info "リージョン: $REGION"
    log_info "セキュリティメール: $SECURITY_EMAIL"
}

# Google Cloud APIs の有効化
enable_apis() {
    log_info "必要なGoogle Cloud APIs を有効化中..."
    
    local apis=(
        "compute.googleapis.com"
        "run.googleapis.com"
        "vpcaccess.googleapis.com"
        "servicenetworking.googleapis.com"
        "firestore.googleapis.com"
        "secretmanager.googleapis.com"
        "cloudsecurity.googleapis.com"
        "logging.googleapis.com"
        "monitoring.googleapis.com"
        "artifactregistry.googleapis.com"
        "cloudbuild.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        log_info "API有効化中: $api"
        gcloud services enable "$api" --quiet
    done
    
    log_success "APIs 有効化完了"
}

# Terraform 初期化と実行
deploy_terraform() {
    log_info "Terraform でインフラをデプロイ中..."
    
    local terraform_dir="$(dirname "$0")/../terraform"
    cd "$terraform_dir"
    
    # Terraform 初期化
    log_info "Terraform を初期化中..."
    terraform init
    
    # Terraform プラン作成
    log_info "Terraform プランを作成中..."
    terraform plan \
        -var="project_id=$PROJECT_ID" \
        -var="environment=$ENVIRONMENT" \
        -var="region=$REGION" \
        -var="security_notification_email=$SECURITY_EMAIL" \
        -out=tfplan
    
    # デプロイの確認
    if [[ "${AUTO_APPROVE:-false}" == "true" ]]; then
        log_warning "AUTO_APPROVE が設定されています。自動でデプロイします。"
        terraform apply -auto-approve tfplan
    else
        echo
        log_warning "上記のプランでデプロイを続行しますか？"
        read -p "続行するには 'yes' を入力してください: " response
        
        if [[ "$response" == "yes" ]]; then
            terraform apply tfplan
        else
            log_error "デプロイがキャンセルされました。"
            exit 1
        fi
    fi
    
    log_success "Terraform デプロイ完了"
}

# シークレットの設定
setup_secrets() {
    log_info "Secret Manager にシークレットを設定中..."
    
    local secret_names=(
        "travel-app-jwt-secret-$ENVIRONMENT"
        "travel-app-gemini-api-key-$ENVIRONMENT"
        "travel-app-maps-api-key-$ENVIRONMENT"
    )
    
    for secret_name in "${secret_names[@]}"; do
        if gcloud secrets describe "$secret_name" --quiet >/dev/null 2>&1; then
            log_info "シークレット '$secret_name' は既に存在します。"
        else
            log_warning "シークレット '$secret_name' が存在しません。手動で設定してください。"
            echo "  gcloud secrets create $secret_name --data-file=-"
        fi
    done
    
    log_warning "シークレットの値は手動で設定する必要があります:"
    echo "  1. JWT_SECRET: ランダムな強力な文字列を生成して設定"
    echo "  2. GEMINI_API_KEY: Google AI Studio から取得したAPIキー"
    echo "  3. GOOGLE_MAPS_API_KEY: Google Maps Platform から取得したAPIキー"
}

# デプロイ後の検証
verify_deployment() {
    log_info "デプロイメントを検証中..."
    
    # VPC の確認
    local vpc_name="travel-app-vpc-$ENVIRONMENT"
    if gcloud compute networks describe "$vpc_name" --quiet >/dev/null 2>&1; then
        log_success "VPC '$vpc_name' が正常に作成されました。"
    else
        log_error "VPC '$vpc_name' が見つかりません。"
        return 1
    fi
    
    # サービスアカウントの確認
    local sa_app="travel-app-$ENVIRONMENT@$PROJECT_ID.iam.gserviceaccount.com"
    if gcloud iam service-accounts describe "$sa_app" --quiet >/dev/null 2>&1; then
        log_success "サービスアカウント '$sa_app' が正常に作成されました。"
    else
        log_error "サービスアカウント '$sa_app' が見つかりません。"
        return 1
    fi
    
    log_success "デプロイメント検証完了"
}

# メイン実行関数
main() {
    echo "============================================"
    echo "旅行アプリ - インフラセキュリティ設定"
    echo "============================================"
    echo
    
    check_prerequisites
    check_gcloud_auth
    setup_parameters
    enable_apis
    deploy_terraform
    setup_secrets
    verify_deployment
    
    echo
    log_success "🎉 インフラセキュリティ設定が完了しました！"
    echo
    log_info "次の手順:"
    echo "  1. Secret Manager でAPIキーを設定"
    echo "  2. GitHub Actions ワークフローでWorkload Identityプロバイダーを設定"
    echo "  3. セキュリティダッシュボードで監視設定を確認"
    echo
    log_info "セキュリティダッシュボード: https://console.cloud.google.com/monitoring/dashboards"
    log_info "Secret Manager: https://console.cloud.google.com/security/secret-manager"
}

# スクリプトが直接実行された場合のみmainを実行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi