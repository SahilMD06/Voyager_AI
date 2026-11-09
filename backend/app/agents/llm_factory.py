"""Creates the chat model for the configured provider."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings


class LLMNotConfiguredError(RuntimeError):
    """Raised when no API key is configured for the selected provider."""


def llm_status(settings: Settings | None = None) -> dict:
    """Describe the LLM configuration without exposing secrets."""
    settings = settings or get_settings()
    return {
        "provider": settings.llm_provider.lower(),
        "model": settings.resolved_model,
        "configured": settings.llm_api_key is not None,
    }


def create_chat_model(settings: Settings | None = None,
                      model: str | None = None) -> BaseChatModel:
    """Instantiate the chat model for ``settings.llm_provider``.

    ``model`` overrides the configured model (used for the fallback retry).
    """
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    key = settings.llm_api_key
    if not key:
        raise LLMNotConfiguredError(
            f"No API key configured for provider '{provider}'. Set it in "
            "backend/.env (see .env.example)."
        )
    common: dict = {"model": model or settings.resolved_model}
    if settings.llm_temperature is not None:
        common["temperature"] = settings.llm_temperature
    elif provider != "gemini":
        common["temperature"] = 0.3
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            google_api_key=key, timeout=settings.llm_timeout_seconds,
            max_retries=2, **common,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=key, base_url=settings.openai_base_url or None,
            timeout=settings.llm_timeout_seconds, max_retries=2, **common,
        )
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=key, timeout=settings.llm_timeout_seconds,
            max_retries=2, **common,
        )
    raise LLMNotConfiguredError(
        f"Unsupported LLM_PROVIDER '{provider}'. Use gemini, openai or groq."
    )
