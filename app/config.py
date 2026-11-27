from functools import lru_cache
import re
from urllib.parse import urlsplit
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Scorpions AI"
    app_env: str = "development"
    app_secret_key: str = ""
    database_url: str = "sqlite:///./storage/scorpions.db"
    frontend_origin: str = ""
    llm_provider: str = "demo"
    groq_api_key: str = ""
    groq_model_id: str = ""
    groq_free_tier_confirmed: bool = False
    gemini_api_key: str = ""
    gemini_model_id: str = ""
    web_search_provider: str = ""
    web_search_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/api/integrations/google/callback"
    token_encryption_key: str = ""
    upload_dir: str = "storage/uploads"
    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_storage_bucket: str = "scorpions-documents"
    max_upload_size_mb: int = 20
    max_agent_steps: int = 6
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    def startup_issues(self) -> list[str]:
        issues=[]
        if self.app_env == "production":
            if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", self.supabase_url):
                issues.append("Set SUPABASE_URL to the HTTPS project URL from the Supabase Connect dialog.")
            if not self.supabase_secret_key:
                issues.append("Set SUPABASE_SECRET_KEY from Supabase Settings > API Keys on the backend.")
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", self.supabase_storage_bucket):
                issues.append("Set SUPABASE_STORAGE_BUCKET to a private bucket name using lowercase letters, numbers or hyphens.")
            if not self.database_url.startswith(("postgres://", "postgresql://")):
                issues.append("Set DATABASE_URL to a persistent PostgreSQL connection URI.")
            origin = urlsplit(self.frontend_origin)
            if self.frontend_origin and (origin.scheme != "https" or not origin.hostname or origin.username or
                    origin.password or origin.path or origin.query or origin.fragment or
                    "*" in self.frontend_origin):
                issues.append("Set FRONTEND_ORIGIN to the single approved HTTPS origin without a trailing slash.")
        if self.app_env == "production" and (not self.app_secret_key or len(self.app_secret_key) < 32):
            issues.append("APP_SECRET_KEY must be set to a random value of at least 32 characters in production.")
        if self.llm_provider == "groq" and not (self.groq_api_key and self.groq_model_id):
            issues.append("Groq is selected but GROQ_API_KEY or GROQ_MODEL_ID is missing. Create a key in the Groq console and set both in the hosting secrets or local .env.")
        if self.llm_provider == 'groq' and not self.groq_free_tier_confirmed:
            issues.append('Confirm Groq Free plan with no usage-based billing before setting GROQ_FREE_TIER_CONFIRMED=true.')
        if self.llm_provider == "gemini" and not (self.gemini_api_key and self.gemini_model_id):
            issues.append("Gemini is selected but GEMINI_API_KEY or GEMINI_MODEL_ID is missing. Obtain a no-billing key from Google AI Studio and set both in secrets or .env.")
        return issues

@lru_cache
def get_settings() -> Settings:
    return Settings()
