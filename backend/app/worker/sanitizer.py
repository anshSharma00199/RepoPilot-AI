import re
from typing import Tuple, List
from app.config import settings

# Explicit pairs of (regex_pattern, replacement_template)
# Key-value patterns preserve the label key (group 1) and redact the value.
# Standalone token patterns replace the entire matched secret.
SENSITIVE_REPLACEMENTS = [
    # Key-value pairs: retain key label, redact value
    (re.compile(r"((?:password|passwd|pwd)\s*[:=]\s*)['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE), r"\1[REDACTED_SECRET]"),
    (re.compile(r"((?:secret|token|api[\s_-]?key|access[\s_-]?key)\s*[:=]\s*)['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE), r"\1[REDACTED_SECRET]"),
    (re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE), r"\1[REDACTED_SECRET]"),
    (re.compile(r"(basic\s+)([a-zA-Z0-9+/=]{15,})", re.IGNORECASE), r"\1[REDACTED_SECRET]"),

    # Standalone token formats: replace entire token
    (re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"github_pat_[a-zA-Z0-9_]{40,}", re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"glpat-[a-zA-Z0-9\-]{20,}", re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_SECRET]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,45}"), "[REDACTED_SECRET]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),

    # Basic auth embedded in URLs: http(s)://user:password@host
    (re.compile(r"(https?://)([^:\s]+):([^@\s]+)@"), r"\1\2:[REDACTED_SECRET]@"),
]


def sanitize_log_content(text: str) -> str:
    """
    Masks secrets and sensitive credentials from execution logs, tracebacks, and prompts.
    Handles malformed inputs (None, non-string) safely by returning an empty string.
    """
    if not text or not isinstance(text, str):
        return ""

    sanitized = text

    # Redact configured API keys if present in text
    if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 6:
        sanitized = sanitized.replace(settings.GEMINI_API_KEY, "[REDACTED_API_KEY]")
    if settings.OPENAI_API_KEY and len(settings.OPENAI_API_KEY) > 6:
        sanitized = sanitized.replace(settings.OPENAI_API_KEY, "[REDACTED_API_KEY]")

    for pattern, replacement in SENSITIVE_REPLACEMENTS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def bound_log_size(content: str, max_bytes: int = settings.MAX_LOG_OUTPUT_BYTES) -> Tuple[str, bool]:
    """
    Limits log size to max_bytes.
    Preserves both the beginning (setup context) and end (failure tracebacks & summary).
    Handles malformed inputs (None, non-string) safely.
    """
    if not content or not isinstance(content, str):
        return "", False

    encoded = content.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return content, False

    # Keep initial 20% and final 80% of allowed limit
    head_size = int(max_bytes * 0.20)
    tail_size = int(max_bytes * 0.80)

    head_bytes = encoded[:head_size]
    tail_bytes = encoded[-tail_size:]

    truncated_kb = round((len(encoded) - max_bytes) / 1024, 1)
    marker = f"\n\n[... Repopilot Notice: Log truncated. {truncated_kb} KB omitted to enforce memory safety ...]\n\n"

    result = (
        head_bytes.decode("utf-8", errors="replace")
        + marker
        + tail_bytes.decode("utf-8", errors="replace")
    )
    return result, True
