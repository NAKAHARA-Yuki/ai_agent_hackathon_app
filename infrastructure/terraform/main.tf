# 旅行アプリ - インフラセキュリティ強化
# VPC、認証、セキュリティポリシーの設定

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Default region for resources"
  type        = string
  default     = "asia-northeast1"
}

variable "environment" {
  description = "Environment (dev/prod)"
  type        = string
  default     = "prod"
}

# Provider configuration
provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudsecurity.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ])

  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy         = false
}

# VPC Network
resource "google_compute_network" "travel_app_vpc" {
  name                    = "travel-app-vpc-${var.environment}"
  auto_create_subnetworks = false
  routing_mode           = "GLOBAL"
  
  depends_on = [google_project_service.apis]
}

# Private subnet for Cloud Run services
resource "google_compute_subnetwork" "private_subnet" {
  name          = "travel-app-private-${var.environment}"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.travel_app_vpc.id

  # Enable private Google access for services without external IPs
  private_ip_google_access = true

  # Secondary range for services
  secondary_ip_range {
    range_name    = "services-range"
    ip_cidr_range = "10.1.0.0/16"
  }
}

# Cloud NAT for outbound internet access from private resources
resource "google_compute_router" "nat_router" {
  name    = "travel-app-nat-router-${var.environment}"
  region  = var.region
  network = google_compute_network.travel_app_vpc.id
}

resource "google_compute_router_nat" "nat_gateway" {
  name                               = "travel-app-nat-${var.environment}"
  router                            = google_compute_router.nat_router.name
  region                            = google_compute_router.nat_router.region
  nat_ip_allocate_option            = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# VPC Access Connector for Cloud Run
resource "google_vpc_access_connector" "connector" {
  name          = "travel-app-connector-${var.environment}"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.travel_app_vpc.name
  
  depends_on = [google_project_service.apis]
}

# Firewall rules for secure communication
resource "google_compute_firewall" "allow_internal" {
  name    = "travel-app-allow-internal-${var.environment}"
  network = google_compute_network.travel_app_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8080", "3000"]
  }

  source_ranges = ["10.0.0.0/8"]
  target_tags   = ["travel-app-service"]
}

resource "google_compute_firewall" "allow_health_check" {
  name    = "travel-app-allow-health-check-${var.environment}"
  network = google_compute_network.travel_app_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  # Google Cloud health check ranges
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = ["travel-app-service"]
}

# Deny all other inbound traffic
resource "google_compute_firewall" "deny_all" {
  name    = "travel-app-deny-all-${var.environment}"
  network = google_compute_network.travel_app_vpc.name
  
  priority = 1000

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["travel-app-service"]
}