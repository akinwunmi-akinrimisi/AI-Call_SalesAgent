# --- Secret Manager secrets ---

resource "google_secret_manager_secret" "google_api_key" {
  secret_id = "${var.service_name}-google-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "google_api_key" {
  secret      = google_secret_manager_secret.google_api_key.id
  secret_data = var.google_api_key
}

resource "google_secret_manager_secret" "supabase_url" {
  secret_id = "${var.service_name}-supabase-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "supabase_url" {
  secret      = google_secret_manager_secret.supabase_url.id
  secret_data = var.supabase_url
}

resource "google_secret_manager_secret" "supabase_service_key" {
  secret_id = "${var.service_name}-supabase-service-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "supabase_service_key" {
  secret      = google_secret_manager_secret.supabase_service_key.id
  secret_data = var.supabase_service_key
}
