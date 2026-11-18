
import logging
from typing import Optional

from app.config import settings
from app.services.llm.interface import LLMProvider, LLMError
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.fake_provider import FakeLLMProvider

logger = logging.getLogger("repopilot.llm")


def get_llm_provider(force_provider: Optional[str] = None) -> LLMProvider:
    """
    Return a configured LLM provider.

    Supported modes:
    - groq
    - gemini
    - fake
    - auto

    Auto mode never silently falls back to FakeLLMProvider.
    """

    provider_type = (force_provider or settings.LLM_PROVIDER).strip().lower()

    # Explicit fake mode only.
    if provider_type == "fake":
        return FakeLLMProvider()

    if provider_type == "gemini":
        provider = GeminiProvider()
        configured, reason = provider.is_configured()

        if not configured:
            raise LLMError(
                error_code="PROVIDER_NOT_CONFIGURED",
                message=f"Gemini is not configured: {reason}",
            )

        return provider

    if provider_type == "groq":
        provider = GroqProvider()
        configured, reason = provider.is_configured()

        if not configured:
            raise LLMError(
                error_code="PROVIDER_NOT_CONFIGURED",
                message=f"Groq is not configured: {reason}",
            )

        return provider

    if provider_type != "auto":
        raise LLMError(
            error_code="INVALID_PROVIDER",
            message=f"Unsupported LLM provider: {provider_type}",
        )

    # Auto mode: prefer Groq, then Gemini.
    errors = []

    groq = GroqProvider()
    groq_configured, groq_reason = groq.is_configured()

    if groq_configured:
        return groq

    errors.append(f"Groq: {groq_reason}")

    gemini = GeminiProvider()
    gemini_configured, gemini_reason = gemini.is_configured()

    if gemini_configured:
        return gemini

    errors.append(f"Gemini: {gemini_reason}")

    message = (
        "Real AI diagnosis is not configured. "
        + "; ".join(errors)
        + ". Configure GROQ_API_KEY or GEMINI_API_KEY. "
        "Use LLM_PROVIDER=fake only for explicit demo/testing."
    )

    logger.error(message)

    raise LLMError(
        error_code="PROVIDER_NOT_CONFIGURED",
        message=message,
    )
