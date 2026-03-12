"""Environment variable loader for Cloudboosta Voice Agent."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    # Google Cloud
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "cloudboosta-agent")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-live")
    google_gemini_api_key: str = os.getenv("GOOGLE_GEMINI_API_KEY", "")

    # Twilio
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number: str = os.getenv("TWILIO_PHONE_NUMBER", "")

    # Supabase
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # n8n
    n8n_base_url: str = os.getenv("N8N_BASE_URL", "")
    n8n_webhook_secret: str = os.getenv("N8N_WEBHOOK_SECRET", "")

    # Admin
    admin_email: str = os.getenv("ADMIN_EMAIL", "")

    def validate(self) -> list[str]:
        """Return list of missing required env vars."""
        required = {
            "GCP_PROJECT_ID": self.gcp_project_id,
            "GOOGLE_GEMINI_API_KEY": self.google_gemini_api_key,
            "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
            "TWILIO_PHONE_NUMBER": self.twilio_phone_number,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SERVICE_KEY": self.supabase_service_key,
        }
        return [k for k, v in required.items() if not v]


config = Config()
