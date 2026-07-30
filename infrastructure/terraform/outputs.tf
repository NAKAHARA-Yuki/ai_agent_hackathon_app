# Terraform Outputs - デプロイ後の重要な情報

output "project_id" {
  description = "Google Cloud Project ID"
  value       = var.project_id
}

output "region" {
  description = "Deployment region"
  value       = var.region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# Network Configuration
output "vpc_name" {
  description = "VPC network name"
  value       = google_compute_network.travel_app_vpc.name
}

output "vpc_self_link" {
  description = "VPC network self link"
  value       = google_compute_network.travel_app_vpc.self_link
}

output "private_subnet_name" {
  description = "Private subnet name"
  value       = google_compute_subnetwork.private_subnet.name
}

output "vpc_connector_name" {
  description = "VPC Access Connector name"
  value       = google_vpc_access_connector.connector.name
}

# Service Accounts
output "service_accounts" {
  description = "Service account emails by service"
  value = {
    app              = google_service_account.app_service_account.email
    agent            = google_service_account.agent_service_account.email
    mcp              = google_service_account.mcp_service_account.email
    security_monitor = google_service_account.security_monitor_sa.email
    github_actions   = google_service_account.github_actions_sa.email
  }
}

# Cloud Run Services
output "cloud_run_services" {
  description = "Cloud Run service URLs"
  value = {
    app   = google_cloud_run_service.travel_app.status[0].url
    agent = google_cloud_run_service.travel_agent.status[0].url
    mcp   = google_cloud_run_service.maps_mcp.status[0].url
  }
}

# Secrets
output "secret_names" {
  description = "Secret Manager secret names"
  value = {
    jwt_secret         = google_secret_manager_secret.jwt_secret.secret_id
    gemini_api_key     = google_secret_manager_secret.gemini_api_key.secret_id
    google_maps_api_key = google_secret_manager_secret.google_maps_api_key.secret_id
    db_connection      = google_secret_manager_secret.db_connection.secret_id
  }
}

# Workload Identity Configuration
output "workload_identity_provider" {
  description = "Workload Identity Provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

# Security Monitoring
output "security_dashboard_url" {
  description = "Security monitoring dashboard URL"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.security_dashboard.id}"
}

output "bigquery_security_dataset" {
  description = "BigQuery dataset for security logs"
  value       = google_bigquery_dataset.security_logs.dataset_id
}

# Deployment Commands
output "deployment_commands" {
  description = "Commands for manual deployment"
  value = {
    terraform_init  = "terraform init"
    terraform_plan  = "terraform plan -var='project_id=${var.project_id}' -var='environment=${var.environment}'"
    terraform_apply = "terraform apply -var='project_id=${var.project_id}' -var='environment=${var.environment}'"
  }
}

# Security Configuration Status
output "security_features_enabled" {
  description = "Summary of enabled security features"
  value = {
    vpc_network_isolation    = true
    private_service_communication = true
    custom_service_accounts = true
    secret_manager_integration = true
    workload_identity = true
    security_monitoring = true
    firewall_rules = true
    iam_least_privilege = true
  }
}