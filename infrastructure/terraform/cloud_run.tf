# セキュアなCloud Run設定
# VPC接続、認証、最小権限でのデプロイ

# Main App Service (Flask Backend + Vue Frontend)
resource "google_cloud_run_service" "travel_app" {
  name     = "travel-quiz-app-${var.environment}"
  location = var.region

  template {
    metadata {
      annotations = {
        # VPC Connector を使用してプライベートネットワーク接続
        "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.connector.name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
        
        # セキュリティ設定
        "run.googleapis.com/execution-environment" = "gen2"
        "run.googleapis.com/network-tags"         = "travel-app-service"
        
        # リソース制限
        "autoscaling.knative.dev/maxScale" = var.environment == "prod" ? "10" : "3"
        "autoscaling.knative.dev/minScale" = var.environment == "prod" ? "1" : "0"
      }
    }

    spec {
      # 専用サービスアカウント使用
      service_account_name = google_service_account.app_service_account.email
      
      # コンテナの並行処理設定
      container_concurrency = var.environment == "prod" ? 100 : 50
      
      containers {
        image = "gcr.io/${var.project_id}/travel-quiz-app:latest"
        
        ports {
          container_port = 8080
        }

        # リソース制限
        resources {
          limits = {
            cpu    = var.environment == "prod" ? "2" : "1"
            memory = var.environment == "prod" ? "2Gi" : "1Gi"
          }
          requests = {
            cpu    = var.environment == "prod" ? "1" : "0.5"
            memory = var.environment == "prod" ? "1Gi" : "512Mi"
          }
        }

        # 環境変数 (シークレット以外)
        env {
          name  = "FLASK_ENV"
          value = var.environment == "prod" ? "production" : "development"
        }
        
        env {
          name  = "ENV"
          value = var.environment
        }
        
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        
        env {
          name  = "FIRESTORE_DATABASE"
          value = var.environment == "prod" ? "(default)" : "izatabi-dev"
        }
        
        env {
          name  = "AGENT_BASE_URL"
          value = "https://travel-agent-service-${var.environment}-${random_string.service_suffix.result}.${var.region}.run.app"
        }

        # Secret Manager からシークレットを環境変数として注入
        env {
          name = "JWT_SECRET"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.jwt_secret.secret_id
              key  = "latest"
            }
          }
        }
        
        env {
          name = "GOOGLE_MAPS_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.google_maps_api_key.secret_id
              key  = "latest"
            }
          }
        }

        # セキュリティコンテキスト
        security_context {
          run_as_user = 1000  # 非rootユーザーで実行
        }

        # ヘルスチェック設定
        startup_probe {
          initial_delay_seconds = 10
          timeout_seconds       = 5
          period_seconds       = 10
          failure_threshold    = 3
          http_get {
            path = "/api/health"
            port = 8080
          }
        }

        liveness_probe {
          initial_delay_seconds = 30
          timeout_seconds       = 5
          period_seconds       = 30
          failure_threshold    = 3
          http_get {
            path = "/api/health"
            port = 8080
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_service.apis,
    google_vpc_access_connector.connector
  ]
}

# AI Agent Service
resource "google_cloud_run_service" "travel_agent" {
  name     = "travel-agent-service-${var.environment}"
  location = var.region

  template {
    metadata {
      annotations = {
        "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.connector.name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
        "run.googleapis.com/execution-environment" = "gen2"
        "run.googleapis.com/network-tags"         = "travel-app-service"
        "autoscaling.knative.dev/maxScale"        = "5"
        "autoscaling.knative.dev/minScale"        = "0"
      }
    }

    spec {
      service_account_name  = google_service_account.agent_service_account.email
      container_concurrency = 10  # AI処理のため低めに設定

      containers {
        image = "gcr.io/${var.project_id}/travel-agent-service:latest"
        
        ports {
          container_port = 8080
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
          requests = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        env {
          name  = "APP_ENV"
          value = var.environment
        }
        
        env {
          name  = "GEMINI_MODEL"
          value = "gemini-2.5-pro"
        }
        
        env {
          name  = "MAPS_MCP_ENDPOINT_URL"
          value = "https://maps-mcp-service-${var.environment}-${random_string.service_suffix.result}.${var.region}.run.app/tools/retrieve-google-maps-platform-docs"
        }

        env {
          name = "GEMINI_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.gemini_api_key.secret_id
              key  = "latest"
            }
          }
        }

        security_context {
          run_as_user = 1000
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# MCP Service
resource "google_cloud_run_service" "maps_mcp" {
  name     = "maps-mcp-service-${var.environment}"
  location = var.region

  template {
    metadata {
      annotations = {
        "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.connector.name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
        "run.googleapis.com/execution-environment" = "gen2"
        "run.googleapis.com/network-tags"         = "travel-app-service"
        "autoscaling.knative.dev/maxScale"        = "3"
        "autoscaling.knative.dev/minScale"        = "0"
      }
    }

    spec {
      service_account_name  = google_service_account.mcp_service_account.email
      container_concurrency = 50

      containers {
        image = "gcr.io/${var.project_id}/maps-mcp-service:latest"
        
        ports {
          container_port = 3000
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
          requests = {
            cpu    = "0.5"
            memory = "256Mi"
          }
        }

        env {
          name  = "APP_ENV"
          value = var.environment
        }

        security_context {
          run_as_user = 1000
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# IAM Policy - Main App へのパブリックアクセス許可（認証はアプリレベルで制御）
resource "google_cloud_run_service_iam_member" "travel_app_public" {
  location = google_cloud_run_service.travel_app.location
  project  = google_cloud_run_service.travel_app.project
  service  = google_cloud_run_service.travel_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# IAM Policy - Agent Service への App Service からのアクセス許可
resource "google_cloud_run_service_iam_member" "agent_app_access" {
  location = google_cloud_run_service.travel_agent.location
  project  = google_cloud_run_service.travel_agent.project
  service  = google_cloud_run_service.travel_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.app_service_account.email}"
}

# IAM Policy - MCP Service への Agent Service からのアクセス許可
resource "google_cloud_run_service_iam_member" "mcp_agent_access" {
  location = google_cloud_run_service.maps_mcp.location
  project  = google_cloud_run_service.maps_mcp.project
  service  = google_cloud_run_service.maps_mcp.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agent_service_account.email}"
}

# サービス間通信の一意性を確保するためのランダム文字列
resource "random_string" "service_suffix" {
  length  = 8
  special = false
  upper   = false
}