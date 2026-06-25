"""
Central configuration for the backend.

All settings come from environment variables (the .env file in local dev,
or the hosting platform's settings in production). We NEVER hardcode secrets
in code. Pydantic reads and validates them for us.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Tell Pydantic to read a file called ".env" sitting next to where we run the app.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # ignore unknown keys instead of crashing
    )

    # --- App basics ---
    PROJECT_NAME: str = "PrimeX AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # --- Database (used in the NEXT prompt, kept empty for now) ---
    DATABASE_URL: str = ""

    # --- Which website origins are allowed to call this API ---
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Turn the comma-separated string into a clean Python list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# One shared settings object the whole app imports.
settings = Settings()