variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "europe-west1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "cloudboosta-voice-agent"
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

# --- Secrets (passed via tfvars or environment) ---

variable "google_api_key" {
  description = "Gemini API key (AI Studio)"
  type        = string
  sensitive   = true
}

variable "supabase_url" {
  description = "Supabase REST API URL"
  type        = string
  sensitive   = true
}

variable "supabase_service_key" {
  description = "Supabase service role key"
  type        = string
  sensitive   = true
}

# --- Optional config ---

variable "gemini_model" {
  description = "Gemini model identifier"
  type        = string
  default     = "gemini-2.5-flash-native-audio-latest"
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 2
}
