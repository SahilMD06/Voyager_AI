"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central settings object. Every secret comes from the environment."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Blank lines such as "LLM_MODEL=" fall back to the defaults below.
        env_ignore_empty=True,
    )

    # --- LLM -------------------------------------------------------------
    llm_provider: str = Field(
        default="gemini", description="gemini | openai | groq"
    )
    llm_model: str | None = Field(
        default=None, description="Override the provider's default model"
    )
    llm_fallback_model: str | None = Field(
        default=None,
        description="Model retried once if the main one fails (e.g. rate "
        "limit). Empty = provider default; 'none' disables the retry.",
    )
    llm_temperature: float | None = Field(
        default=None,
        description="Leave empty to use the provider default (Gemini 3 "
        "models are tuned for their default temperature)",
    )
    llm_timeout_seconds: int = 90
    google_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    groq_api_key: str | None = None

    # --- Data ------------------------------------------------------------
    data_dir: Path = BACKEND_DIR / "data"

    # --- External APIs ---------------------------------------------------
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_historical_forecast_url: str = (
        "https://historical-forecast-api.open-meteo.com/v1/forecast"
    )
    # Keyless fallback forecast used only when Open-Meteo refuses (e.g. a
    # shared cloud IP has exhausted its daily free quota).
    met_norway_url: str = (
        "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    )
    open_meteo_geocoding_url: str = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )
    wikipedia_summary_url: str = (
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
    )
    http_timeout_seconds: float = 12.0
    # Wikimedia rejects clients without a contact link in the User-Agent.
    http_user_agent: str = (
        "VoyagerAI-TravelPlanner/1.0 (https://github.com/SahilMD06; "
        "student project)"
    )
    http_max_retries: int = 3

    # --- Budget estimation assumptions (INR) -----------------------------
    # These are ESTIMATES, not dataset prices, and are labelled as such.
    food_per_person_per_day_budget: int = 700
    food_per_person_per_day_mid: int = 1200
    food_per_person_per_day_luxury: int = 2200
    local_transport_per_vehicle_per_day: int = 900
    travelers_per_vehicle: int = 4
    travelers_per_room: int = 2

    # --- Server ----------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional regex, e.g. https://voyager-ai.*\.vercel\.app for preview URLs
    cors_origin_regex: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list.

        Tolerates common copy-paste slips: surrounding quotes, spaces,
        semicolons and trailing slashes ("https://x.vercel.app/").
        """
        raw = self.cors_origins.replace(";", ",")
        origins = []
        for item in raw.split(","):
            origin = item.strip().strip("\"'").strip().rstrip("/")
            if origin:
                origins.append(origin)
        return origins

    @property
    def resolved_model(self) -> str:
        """Model name, falling back to a sensible default per provider."""
        if self.llm_model:
            return self.llm_model
        defaults = {
            "gemini": "gemini-3.5-flash",
            "openai": "gpt-4o-mini",
            "groq": "llama-3.3-70b-versatile",
        }
        return defaults.get(self.llm_provider.lower(), "gemini-3.5-flash")

    @property
    def resolved_fallback_model(self) -> str | None:
        """Second model to try when the main one errors, or None."""
        if self.llm_fallback_model:
            value = self.llm_fallback_model.strip()
            return None if value.lower() == "none" else value
        defaults = {
            "gemini": "gemini-3.5-flash-lite",
            "groq": "llama-3.1-8b-instant",
        }
        fallback = defaults.get(self.llm_provider.lower())
        return fallback if fallback != self.resolved_model else None

    @property
    def llm_api_key(self) -> str | None:
        """API key for the configured provider, if one is set."""
        keys = {
            "gemini": self.google_api_key,
            "openai": self.openai_api_key,
            "groq": self.groq_api_key,
        }
        key = keys.get(self.llm_provider.lower())
        return key.strip() if key and key.strip() else None


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
