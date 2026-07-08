"""Environment configuration. Twelve-factor: everything overridable via env vars."""
import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "ListingForge AI"
    env: str = os.getenv("LF_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./listingforge.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    model_reasoning: str = os.getenv("LF_MODEL_REASONING", "claude-sonnet-4-6")
    model_fast: str = os.getenv("LF_MODEL_FAST", "claude-haiku-4-5-20251001")

    storage_dir: str = os.getenv("LF_STORAGE_DIR", "./storage")
    max_upload_mb: int = 15

    # Billing
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    free_tier_listings_per_month: int = int(os.getenv("LF_FREE_LISTINGS", "3"))
    pro_tier_listings_per_month: int = int(os.getenv("LF_PRO_LISTINGS", "100"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
