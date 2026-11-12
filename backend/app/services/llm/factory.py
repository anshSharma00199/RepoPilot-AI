import os
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
    Factory function returning configured LLMProvider.
    Supports 'groq', 'gemini', 'fake', or 'auto'.
    """
    provider_type = (force_provider or settings.LLM_PROVIDER).lower()

    if provider_type == "fake":
        return FakeLLMProvider()

    if provider_type == "gemini":
        return GeminiProvider()

    if provider_type == "groq":
        return GroqProvider()

    # 'auto' mode: prefer Groq when configured, then Gemini.
    groq = GroqProvider()
    groq_configured, groq_reason = groq.is_configured()
    if groq_configured:
        return groq

    gemini = GeminiProvider()
    configured, reason = gemini.is_configured()
    if configured:
        return gemini

    # Never silently replace a requested real diagnosis with a simulated answer.
    # This previously allowed canned fixture output to be mistaken for analysis of
    # an uploaded external repository. Fake mode must be explicitly selected.
    logger.error("No real LLM provider is configured: %s", reason)
    raise LLMError(
        error_code="PROVIDER_NOT_CONFIGURED",
        message=(
            f"Real AI diagnosis is not configured: {groq_reason}; {reason} "
            "Set GROQ_API_KEY and LLM_PROVIDER=groq (or auto), or set GEMINI_API_KEY and use gemini. "
            "Use LLM_PROVIDER=fake only for deterministic demo/testing scenarios."
        ),
    )
