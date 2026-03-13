output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.voice_agent.uri
}

output "service_account_email" {
  description = "Cloud Run service account email"
  value       = google_service_account.voice_agent.email
}

output "artifact_registry" {
  description = "Artifact Registry repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "image" {
  description = "Full container image path"
  value       = local.image
}
