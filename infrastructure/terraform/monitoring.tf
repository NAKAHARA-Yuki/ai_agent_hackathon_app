# セキュリティ監視とアラート設定
# ログ分析、メトリクス、セキュリティアラート

# Cloud Security Command Center 設定
resource "google_security_center_source" "travel_app_source" {
  display_name = "Travel App Security Source (${var.environment})"
  description  = "Custom security findings for travel application"
}

# ログシンク設定 - セキュリティ関連ログの収集
resource "google_logging_project_sink" "security_sink" {
  name        = "travel-app-security-sink-${var.environment}"
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/security_logs_${var.environment}"

  # セキュリティ関連ログのフィルタ
  filter = <<-EOT
    (protoPayload.methodName="google.iam.v1.IAMPolicy.SetIamPolicy" OR
     protoPayload.methodName="google.iam.v1.IAMPolicy.GetIamPolicy" OR
     protoPayload.serviceName="run.googleapis.com" OR
     protoPayload.serviceName="secretmanager.googleapis.com" OR
     severity>=ERROR OR
     jsonPayload.security_event=true OR
     labels."compute.googleapis.com/resource_name"=~"travel-.*${var.environment}")
  EOT

  unique_writer_identity = true
}

# BigQuery データセット作成 (ログシンク用)
resource "google_bigquery_dataset" "security_logs" {
  dataset_id  = "security_logs_${var.environment}"
  description = "Security logs dataset for travel app (${var.environment})"
  location    = var.region

  labels = {
    environment = var.environment
    purpose     = "security-monitoring"
  }

  # 30日間の保持期間
  default_table_expiration_ms = 2592000000  # 30 days in milliseconds
}

# ログシンク用サービスアカウントに BigQuery 書き込み権限を付与
resource "google_bigquery_dataset_iam_member" "security_sink_writer" {
  dataset_id = google_bigquery_dataset.security_logs.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.security_sink.writer_identity
}

# Cloud Monitoring アラートポリシー - 認証失敗の監視
resource "google_monitoring_alert_policy" "auth_failures" {
  display_name = "Travel App Auth Failures (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "High authentication failure rate"

    condition_threshold {
      filter         = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"travel-.*${var.environment}\" AND jsonPayload.message=~\".*unauthorized.*\""
      duration       = "300s"
      comparison     = "COMPARISON_GREATER_THAN"
      threshold_value = 10

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.security_email.name]
  
  alert_strategy {
    auto_close = "86400s"  # 24 hours
  }
}

# Cloud Monitoring アラートポリシー - 異常なリクエスト量
resource "google_monitoring_alert_policy" "high_request_rate" {
  display_name = "Travel App High Request Rate (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "Unusually high request rate"

    condition_threshold {
      filter         = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"travel-.*${var.environment}\""
      duration       = "300s"
      comparison     = "COMPARISON_GREATER_THAN"
      threshold_value = var.environment == "prod" ? 1000 : 100

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.security_email.name]
}

# Cloud Monitoring アラートポリシー - エラー率の監視
resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "Travel App High Error Rate (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "High error rate detected"

    condition_threshold {
      filter         = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"travel-.*${var.environment}\" AND severity>=ERROR"
      duration       = "600s"
      comparison     = "COMPARISON_GREATER_THAN"
      threshold_value = 5

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.security_email.name]
}

# 通知チャンネル設定 (メール)
resource "google_monitoring_notification_channel" "security_email" {
  display_name = "Travel App Security Notifications (${var.environment})"
  type         = "email"
  
  labels = {
    email_address = var.security_notification_email
  }
}

# セキュリティダッシュボード作成
resource "google_monitoring_dashboard" "security_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Travel App Security Dashboard (${var.environment})"
    
    mosaicLayout = {
      tiles = [
        {
          width = 6
          height = 4
          widget = {
            title = "Authentication Failures"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"travel-.*${var.environment}\" AND jsonPayload.message=~\".*unauthorized.*\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 6
          height = 4
          widget = {
            title = "Request Rate by Service"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"travel-.*${var.environment}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields = ["resource.labels.service_name"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          width = 12
          height = 4
          widget = {
            title = "Error Logs"
            logPanel = {
              filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"travel-.*${var.environment}\" AND severity>=ERROR"
            }
          }
        }
      ]
    }
  })
}

# セキュリティ監視用の追加変数
variable "security_notification_email" {
  description = "Email address for security notifications"
  type        = string
  default     = "security@example.com"  # 実際のメールアドレスに変更してください
}