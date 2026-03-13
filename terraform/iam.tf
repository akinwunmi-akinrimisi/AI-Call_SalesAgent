# Dedicated service account for the Cloud Run service
resource "google_service_account" "voice_agent" {
  account_id   = "${var.service_name}-sa"
  display_name = "Cloudboosta Voice Agent"
  description  = "Service account for the Cloud Run voice agent"
}

# Firestore access (read knowledge base)
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.voice_agent.email}"
}

# Secret Manager access (read secrets)
resource "google_project_iam_member" "secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.voice_agent.email}"
}

# Cloud Logging
resource "google_project_iam_member" "logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.voice_agent.email}"
}
