resource "google_artifact_registry_repository" "docker" {
  repository_id = var.service_name
  location      = var.region
  format        = "DOCKER"
  description   = "Docker images for Cloudboosta Voice Agent"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}
