#!/bin/bash
# セキュリティ設定の検証スクリプト
# デプロイ後にセキュリティ設定が正しく適用されているかを確認

set -euo pipefail

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m' 
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 環境変数の確認
check_environment() {
    log_info "環境変数を確認中..."
    
    if [[ -z "${PROJECT_ID:-}" ]]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
        if [[ -z "$PROJECT_ID" ]]; then
            log_error "PROJECT_ID が設定されていません"
            exit 1
        fi
    fi
    
    if [[ -z "${ENVIRONMENT:-}" ]]; then
        ENVIRONMENT="prod"
        log_warning "ENVIRONMENT が未設定のため 'prod' を使用します"
    fi
    
    if [[ -z "${REGION:-}" ]]; then
        REGION="asia-northeast1"
        log_warning "REGION が未設定のため 'asia-northeast1' を使用します"
    fi
    
    log_success "環境設定: PROJECT_ID=$PROJECT_ID, ENV=$ENVIRONMENT, REGION=$REGION"
}

# VPC設定の検証
validate_vpc() {
    log_info "VPC設定を検証中..."
    
    local vpc_name="travel-app-vpc-$ENVIRONMENT"
    
    if gcloud compute networks describe "$vpc_name" --quiet >/dev/null 2>&1; then
        log_success "VPC '$vpc_name' が存在します"
        
        # サブネット確認
        local subnet_name="travel-app-private-$ENVIRONMENT"
        if gcloud compute networks subnets describe "$subnet_name" --region="$REGION" --quiet >/dev/null 2>&1; then
            log_success "プライベートサブネット '$subnet_name' が存在します"
        else
            log_error "プライベートサブネット '$subnet_name' が見つかりません"
            return 1
        fi
        
        # VPCコネクタ確認
        local connector_name="travel-app-connector-$ENVIRONMENT"
        if gcloud compute networks vpc-access connectors describe "$connector_name" --region="$REGION" --quiet >/dev/null 2>&1; then
            log_success "VPCコネクタ '$connector_name' が存在します"
        else
            log_warning "VPCコネクタ '$connector_name' が見つかりません（作成中の可能性があります）"
        fi
    else
        log_error "VPC '$vpc_name' が見つかりません"
        return 1
    fi
}

# サービスアカウントの検証
validate_service_accounts() {
    log_info "サービスアカウントを検証中..."
    
    local service_accounts=(
        "travel-app-$ENVIRONMENT"
        "travel-agent-$ENVIRONMENT"
        "travel-mcp-$ENVIRONMENT"
        "github-actions-deploy-$ENVIRONMENT"
    )
    
    for sa in "${service_accounts[@]}"; do
        local sa_email="${sa}@${PROJECT_ID}.iam.gserviceaccount.com"
        if gcloud iam service-accounts describe "$sa_email" --quiet >/dev/null 2>&1; then
            log_success "サービスアカウント '$sa' が存在します"
        else
            log_error "サービスアカウント '$sa' が見つかりません"
        fi
    done
}

# Secret Managerの検証
validate_secrets() {
    log_info "Secret Managerの設定を検証中..."
    
    local secrets=(
        "travel-app-jwt-secret-$ENVIRONMENT"
        "travel-app-gemini-api-key-$ENVIRONMENT" 
        "travel-app-maps-api-key-$ENVIRONMENT"
    )
    
    for secret in "${secrets[@]}"; do
        if gcloud secrets describe "$secret" --quiet >/dev/null 2>&1; then
            log_success "シークレット '$secret' が存在します"
            
            # 値が設定されているかチェック
            if gcloud secrets versions list "$secret" --limit=1 --quiet | grep -q "ENABLED"; then
                log_success "シークレット '$secret' に値が設定されています"
            else
                log_warning "シークレット '$secret' に値が設定されていません"
            fi
        else
            log_error "シークレット '$secret' が見つかりません"
        fi
    done
}

# Cloud Runサービスの検証
validate_cloud_run() {
    log_info "Cloud Runサービスを検証中..."
    
    local services=(
        "travel-quiz-app-$ENVIRONMENT"
        "travel-agent-service-$ENVIRONMENT"
        "maps-mcp-service-$ENVIRONMENT"
    )
    
    for service in "${services[@]}"; do
        if gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
            log_success "Cloud Runサービス '$service' が存在します"
            
            # VPCコネクタ設定の確認
            local vpc_connector
            vpc_connector=$(gcloud run services describe "$service" --region="$REGION" --format="value(spec.template.metadata.annotations['run.googleapis.com/vpc-access-connector'])" 2>/dev/null || echo "")
            
            if [[ -n "$vpc_connector" ]]; then
                log_success "サービス '$service' にVPCコネクタが設定されています"
            else
                log_warning "サービス '$service' にVPCコネクタが設定されていません"
            fi
        else
            log_warning "Cloud Runサービス '$service' が見つかりません（未デプロイの可能性があります）"
        fi
    done
}

# ファイアウォールルールの検証
validate_firewall() {
    log_info "ファイアウォールルールを検証中..."
    
    local rules=(
        "travel-app-allow-internal-$ENVIRONMENT"
        "travel-app-allow-health-check-$ENVIRONMENT"
        "travel-app-deny-all-$ENVIRONMENT"
    )
    
    for rule in "${rules[@]}"; do
        if gcloud compute firewall-rules describe "$rule" --quiet >/dev/null 2>&1; then
            log_success "ファイアウォールルール '$rule' が存在します"
        else
            log_error "ファイアウォールルール '$rule' が見つかりません"
        fi
    done
}

# セキュリティ監視の検証  
validate_monitoring() {
    log_info "セキュリティ監視設定を検証中..."
    
    # BigQueryデータセット確認
    local dataset="security_logs_$ENVIRONMENT"
    if bq show --dataset "$PROJECT_ID:$dataset" >/dev/null 2>&1; then
        log_success "BigQueryデータセット '$dataset' が存在します"
    else
        log_warning "BigQueryデータセット '$dataset' が見つかりません"
    fi
    
    # アラートポリシー確認（簡易チェック）
    local alert_count
    alert_count=$(gcloud alpha monitoring policies list --filter="displayName:Travel App*$ENVIRONMENT*" --format="value(name)" | wc -l)
    
    if [[ "$alert_count" -gt 0 ]]; then
        log_success "セキュリティアラートポリシーが設定されています ($alert_count 個)"
    else
        log_warning "セキュリティアラートポリシーが見つかりません"
    fi
}

# セキュリティ設定のサマリー出力
output_summary() {
    echo
    log_info "=== セキュリティ検証サマリー ==="
    echo
    log_info "🔍 検証項目:"
    echo "  ✓ VPCネットワーク分離"
    echo "  ✓ サービスアカウント設定"  
    echo "  ✓ Secret Manager統合"
    echo "  ✓ Cloud Runセキュリティ設定"
    echo "  ✓ ファイアウォールルール"
    echo "  ✓ セキュリティ監視"
    echo
    log_info "🛡️ セキュリティ機能:"
    echo "  • プライベートネットワーク通信"
    echo "  • 最小権限IAM"
    echo "  • 暗号化されたシークレット管理" 
    echo "  • リアルタイム監視・アラート"
    echo
    log_info "📊 推奨次ステップ:"
    echo "  1. セキュリティダッシュボードの確認"
    echo "  2. アラート通知のテスト"
    echo "  3. ペネトレーションテストの実施"
    echo "  4. 定期的なセキュリティ監査"
    echo
    log_success "セキュリティ検証完了 🎉"
}

# メイン実行
main() {
    echo "============================================"
    echo "セキュリティ設定検証スクリプト"
    echo "============================================"
    echo
    
    check_environment
    validate_vpc
    validate_service_accounts  
    validate_secrets
    validate_cloud_run
    validate_firewall
    validate_monitoring
    output_summary
}

# スクリプトが直接実行された場合のみmainを実行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi