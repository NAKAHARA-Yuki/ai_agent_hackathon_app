# Secrets Manager設定
# APIキーやシークレット情報の安全な管理

# JWT Secret
resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "travel-app-jwt-secret-${var.environment}"
  
  labels = {
    environment = var.environment
    service     = "travel-app"
    type        = "jwt"
  }

  replication {
    auto {}
  }
}

# Gemini API Key
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "travel-app-gemini-api-key-${var.environment}"
  
  labels = {
    environment = var.environment
    service     = "travel-app"
    type        = "api-key"
  }

  replication {
    auto {}
  }
}

# Google Maps API Key
resource "google_secret_manager_secret" "google_maps_api_key" {
  secret_id = "travel-app-maps-api-key-${var.environment}"
  
  labels = {
    environment = var.environment
    service     = "travel-app"
    type        = "api-key"
  }

  replication {
    auto {}
  }
}

# Database Connection String (if needed)
resource "google_secret_manager_secret" "db_connection" {
  secret_id = "travel-app-db-connection-${var.environment}"
  
  labels = {
    environment = var.environment
    service     = "travel-app"
    type        = "database"
  }

  replication {
    auto {}
  }
}

# Secret versions (これらは手動で設定するか、別途スクリプトで設定)
# 注: Terraform で実際の値を設定するのはセキュリティ上推奨されない
# これらは参照用のプレースホルダー

# App Service が JWT Secret にアクセスできるよう権限設定
resource "google_secret_manager_secret_iam_member" "app_jwt_secret_access" {
  secret_id = google_secret_manager_secret.jwt_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app_service_account.email}"
}

# App Service が Maps API Key にアクセスできるよう権限設定
resource "google_secret_manager_secret_iam_member" "app_maps_secret_access" {
  secret_id = google_secret_manager_secret.google_maps_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Agent Service が Gemini API Key にアクセスできるよう権限設定
resource "google_secret_manager_secret_iam_member" "agent_gemini_secret_access" {
  secret_id = google_secret_manager_secret.gemini_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_service_account.email}"
}

# GitHub Actions SA がデプロイ時にシークレットを更新できるよう権限設定
resource "google_secret_manager_secret_iam_member" "github_secret_admin" {
  for_each = toset([
    google_secret_manager_secret.jwt_secret.secret_id,
    google_secret_manager_secret.gemini_api_key.secret_id,
    google_secret_manager_secret.google_maps_api_key.secret_id,
    google_secret_manager_secret.db_connection.secret_id
  ])
  
  secret_id = each.key
  role      = "roles/secretmanager.admin"
  member    = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

# Cloud Run サービスでシークレットをマウントするための設定例
# (実際のCloud Run設定は cloud_run.tf で行う)
output "secret_names" {
  description = "Secret names for Cloud Run service configuration"
  value = {
    jwt_secret         = google_secret_manager_secret.jwt_secret.secret_id
    gemini_api_key     = google_secret_manager_secret.gemini_api_key.secret_id
    google_maps_api_key = google_secret_manager_secret.google_maps_api_key.secret_id
    db_connection      = google_secret_manager_secret.db_connection.secret_id
  }
}