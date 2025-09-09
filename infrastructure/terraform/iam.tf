# IAM とサービスアカウント設定
# 最小権限の原則に基づく役割分担

# 共通のローカル値
locals {
  service_accounts = {
    app   = "travel-app-${var.environment}"
    agent = "travel-agent-${var.environment}"
    mcp   = "travel-mcp-${var.environment}"
  }
}

# メインアプリケーション用サービスアカウント
resource "google_service_account" "app_service_account" {
  account_id   = local.service_accounts.app
  display_name = "Travel App Service Account (${var.environment})"
  description  = "Service account for travel app main service with minimal required permissions"
}

# AIエージェント用サービスアカウント
resource "google_service_account" "agent_service_account" {
  account_id   = local.service_accounts.agent
  display_name = "Travel Agent Service Account (${var.environment})"
  description  = "Service account for AI agent service with API access permissions"
}

# MCP サービス用サービスアカウント
resource "google_service_account" "mcp_service_account" {
  account_id   = local.service_accounts.mcp
  display_name = "Travel MCP Service Account (${var.environment})"
  description  = "Service account for Maps Code Assist service"
}

# App Service - Firestore アクセス権限
resource "google_project_iam_member" "app_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# App Service - Secret Manager アクセス権限
resource "google_project_iam_member" "app_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# App Service - Cloud Run Invoker 権限 (エージェントサービス呼び出し用)
resource "google_project_iam_member" "app_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Agent Service - Secret Manager アクセス権限
resource "google_project_iam_member" "agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.agent_service_account.email}"
}

# Agent Service - Cloud Run Invoker 権限 (MCP サービス呼び出し用)
resource "google_project_iam_member" "agent_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.agent_service_account.email}"
}

# Agent Service - AI Platform権限（Gemini API使用）
resource "google_project_iam_member" "agent_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_service_account.email}"
}

# MCP Service - 基本的な実行権限のみ
resource "google_project_iam_member" "mcp_basic" {
  project = var.project_id
  role    = "roles/run.developer"  # 必要最小限
  member  = "serviceAccount:${google_service_account.mcp_service_account.email}"
}

# セキュリティ監視用のカスタムロール作成
resource "google_project_iam_custom_role" "security_monitor" {
  role_id     = "travel_app_security_monitor_${var.environment}"
  title       = "Travel App Security Monitor"
  description = "Custom role for security monitoring of travel app services"
  
  permissions = [
    "logging.logEntries.list",
    "logging.logEntries.create",
    "monitoring.metricDescriptors.list",
    "monitoring.timeSeries.list",
    "securitycenter.findings.list"
  ]
}

# セキュリティ監視サービスアカウント
resource "google_service_account" "security_monitor_sa" {
  account_id   = "travel-security-monitor-${var.environment}"
  display_name = "Travel App Security Monitor (${var.environment})"
  description  = "Service account for security monitoring and alerting"
}

resource "google_project_iam_member" "security_monitor_role" {
  project = var.project_id
  role    = google_project_iam_custom_role.security_monitor.name
  member  = "serviceAccount:${google_service_account.security_monitor_sa.email}"
}

# Workload Identity設定（GitHub Actions用）
resource "google_service_account" "github_actions_sa" {
  account_id   = "github-actions-deploy-${var.environment}"
  display_name = "GitHub Actions Deployment SA (${var.environment})"
  description  = "Service account for GitHub Actions deployments with restricted permissions"
}

# GitHub Actions SA - 必要最小限のデプロイ権限
resource "google_project_iam_member" "github_deploy_permissions" {
  for_each = toset([
    "roles/run.developer",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser"
  ])
  
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

# Workload Identity Pool 設定
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-actions-pool-${var.environment}"
  display_name              = "GitHub Actions Pool (${var.environment})"
  description               = "Workload Identity pool for GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.actor"      = "assertion.actor"
    "attribute.aud"        = "assertion.aud"
  }
  
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# GitHub Actions SA にWorkload Identity User権限を付与
resource "google_service_account_iam_member" "github_workload_identity" {
  service_account_id = google_service_account.github_actions_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/NAKAHARA-Yuki/ai_agent_hackathon_app"
}