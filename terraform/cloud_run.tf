locals {
  image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/${var.service_name}:${var.image_tag}"
}

resource "google_cloud_run_v2_service" "voice_agent" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.voice_agent.email

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    # 900s timeout for WebSocket voice calls (up to 10 min)
    timeout = "900s"

    # Session affinity for WebSocket connections
    session_affinity = true

    containers {
      image = local.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      # --- Environment variables ---
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "false"
      }

      # --- Secrets from Secret Manager ---
      env {
        name = "GOOGLE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.google_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SUPABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.supabase_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SUPABASE_SERVICE_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.supabase_service_key.secret_id
            version = "latest"
          }
        }
      }

      # Health check
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds = 30
      }
    }
  }

  # Allow unauthenticated access (public demo)
  deletion_protection = false

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.google_api_key,
    google_secret_manager_secret_version.supabase_url,
    google_secret_manager_secret_version.supabase_service_key,
  ]
}

# Allow unauthenticated invocations (public demo)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.voice_agent.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
