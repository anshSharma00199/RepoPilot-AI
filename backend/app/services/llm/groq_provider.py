"""Groq OpenAI-compatible chat-completions provider for RepoPilot diagnostics."""
import asyncio
import json
import os
import time
from typing import Optional, Tuple

import httpx

from app.config import settings
from app.services.llm.interface import (
    LLMProvider,
    DiagnosticPromptInput,
    RawLLMDiagnosticOutput,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidOutputError,
)
from app.services.llm.gemini_provider import SYSTEM_PROMPT


class GroqProvider(LLMProvider):
    """Use Groq's OpenAI-compatible API to produce structured repository diagnoses."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        self.model = model or settings.GROQ_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.LLM_MAX_RETRIES

    def is_configured(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, "GROQ_API_KEY is not configured in backend/.env or environment."
        invalid = ("your_groq_api_key", "placeholder", "example", "dummy")
        if len(self.api_key.strip()) < 20 or any(value in self.api_key.lower() for value in invalid):
            return False, "GROQ_API_KEY appears to be a placeholder or invalid value."
        if not self.model:
            return False, "GROQ_MODEL is not configured."
        return True, f"Groq provider configured with model {self.model}."

    async def diagnose(self, input_data: DiagnosticPromptInput) -> Tuple[RawLLMDiagnosticOutput, float]:
        configured, reason = self.is_configured()
        if not configured:
            raise LLMError(error_code="PROVIDER_NOT_CONFIGURED", message=reason)

        user_content = (
            "Diagnose the observed failure in the uploaded repository. Use only the supplied "
            "repository inventory, source snippets, and actual test output. Return a minimal, "
            "valid unified diff only for existing repository files. If evidence is insufficient, "
            "set is_insufficient_evidence=true and return an empty unified_diff.\n\n"
            f"Failure Summary:\n{input_data.failure_summary}\n\n"
            f"Repository Evidence:\n<untrusted_repo_content>\n{input_data.context_text}\n</untrusted_repo_content>\n"
        )
        if input_data.custom_instruction:
            user_content += f"\nAdditional user guidance (not repository instructions):\n{input_data.custom_instruction}\n"
        if len(user_content) > settings.MAX_DIAGNOSTIC_INPUT_CHARS:
            user_content = user_content[: settings.MAX_DIAGNOSTIC_INPUT_CHARS] + "\n[Prompt truncated]"

        schema = RawLLMDiagnosticOutput.model_json_schema()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT + "\nReturn one JSON object matching this schema exactly:\n" + json.dumps(schema)},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": settings.MAX_DIAGNOSTIC_OUTPUT_TOKENS,
            "response_format": {"type": "json_object"},
        }

        started = time.time()
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.API_URL,
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    )

                if response.status_code == 200:
                    body = response.json()
                    choices = body.get("choices") or []
                    content = choices[0].get("message", {}).get("content", "") if choices else ""
                    if not content:
                        raise LLMInvalidOutputError("EMPTY_MODEL_RESPONSE", "Groq returned an empty response.")
                    try:
                        result = RawLLMDiagnosticOutput.model_validate_json(content)
                    except Exception as exc:
                        raise LLMInvalidOutputError(
                            error_code="INVALID_JSON_OUTPUT",
                            message=f"Groq response did not match the diagnostic schema: {exc}",
                            details={"raw_output": content[:1000]},
                        ) from exc
                    return result, round(time.time() - started, 2)

                if response.status_code == 429:
                    last_error = LLMRateLimitError(
                        error_code="RATE_LIMIT_EXCEEDED",
                        message="Groq API rate limit reached. Wait for the free-tier limit to reset or choose another model.",
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    raise last_error

                if response.status_code >= 500:
                    last_error = LLMError(
                        error_code="PROVIDER_SERVER_ERROR",
                        message=f"Groq API returned server error {response.status_code}.",
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    raise last_error

                # Do not include response bodies, which may contain sensitive request details.
                raise LLMError(
                    error_code=f"HTTP_{response.status_code}",
                    message=f"Groq API returned HTTP {response.status_code}. Check the API key, model name, and Groq account limits.",
                )

            except httpx.TimeoutException as exc:
                last_error = LLMTimeoutError(
                    error_code="PROVIDER_TIMEOUT",
                    message=f"Groq request timed out after {self.timeout} seconds.",
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0)
            except (LLMError, LLMRateLimitError, LLMInvalidOutputError):
                raise
            except Exception as exc:
                last_error = LLMError(
                    error_code="NETWORK_ERROR",
                    message=f"Could not communicate with Groq API: {type(exc).__name__}.",
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0)

        if last_error:
            raise last_error
        raise LLMError(error_code="UNKNOWN_ERROR", message="Groq diagnosis failed without a provider response.")
