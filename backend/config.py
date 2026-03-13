"""Environment variable loader for Cloudboosta Voice Agent."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


@dataclass
class Config:
    # Google Cloud
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "vision-gridai")
    gcp_region: str = os.getenv("GCP_REGION", "europe-west1")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-live-001")
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "secrets/openclaw-key-google.json")

    def __post_init__(self):
        """Resolve credentials path relative to project root."""
        import os
        from pathlib import Path
        cred_path = Path(self.google_application_credentials)
        if not cred_path.is_absolute() and not cred_path.exists():
            # Try relative to project root (one level up from backend/)
            project_root = Path(__file__).resolve().parent.parent
            resolved = project_root / cred_path
            if resolved.exists():
                self.google_application_credentials = str(resolved)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved)

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
            "GOOGLE_APPLICATION_CREDENTIALS": self.google_application_credentials,
            "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
            "TWILIO_PHONE_NUMBER": self.twilio_phone_number,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SERVICE_KEY": self.supabase_service_key,
        }
        return [k for k, v in required.items() if not v]


config = Config()
