"""LLM client supporting Groq/OpenAI compatible chat completion APIs."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    pass


def _is_truthy_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_retryable_provider_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "rate limit",
        "rate_limit_exceeded",
        "insufficient_quota",
        "quota",
        "429",
        "too many requests",
        "service unavailable",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "connection error",
    )
    return any(marker in text for marker in markers)


@dataclass(frozen=True)
class _ProviderAttempt:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None


@dataclass
class LLMClient:
    provider: str
    model: str
    api_key: Optional[str] = None

    def _resolve_api_key(self, provider: str) -> str:
        normalized = provider.lower()
        if normalized == "groq":
            key = os.getenv("GROQ_API_KEY")
            if key:
                return key
        key = self.api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if key:
            return key
        raise LLMClientError("No LLM API key configured. Set GROQ_API_KEY, LLM_API_KEY, or OPENAI_API_KEY.")

    def _candidate_attempts(self) -> list[_ProviderAttempt]:
        provider = (self.provider or "groq").strip().lower()
        model = (self.model or "").strip()
        if not model:
            raise LLMClientError("No LLM model configured.")

        attempts = [
            _ProviderAttempt(
                provider=provider,
                model=model,
                api_key=self._resolve_api_key(provider),
                base_url=(
                    os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
                    if provider == "groq"
                    else None
                ),
            )
        ]

        fallback_enabled = _is_truthy_env(os.getenv("LLM_OPENAI_FALLBACK_ENABLED"), default=True)
        fallback_key = (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
        fallback_model = (os.getenv("OPENAI_LLM_MODEL") or "gpt-4o-mini").strip()
        if fallback_enabled and provider != "openai" and fallback_key and fallback_model:
            attempts.append(
                _ProviderAttempt(
                    provider="openai",
                    model=fallback_model,
                    api_key=fallback_key,
                    base_url=None,
                )
            )
        return attempts

    def _client(self, attempt: _ProviderAttempt):
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise LLMClientError("openai dependency is required for LLM calls.") from exc

        api_key = attempt.api_key
        provider = attempt.provider.lower()
        if provider == "groq":
            return OpenAI(api_key=api_key, base_url=attempt.base_url or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"))
        if provider in {"openai", ""}:
            return OpenAI(api_key=api_key)
        raise LLMClientError(f"Unsupported LLM provider: {self.provider}")

    def generate(self, prompt: str) -> str:
        """Generate a completion from configured provider."""
        errors: list[str] = []
        attempts = self._candidate_attempts()
        for index, attempt in enumerate(attempts):
            client = self._client(attempt)
            try:
                response = client.chat.completions.create(
                    model=attempt.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                content = response.choices[0].message.content if response.choices else None
                if not content:
                    raise LLMClientError("LLM returned empty content.")
                logger.info(
                    "llm.generate success provider=%s model=%s fallback_used=%s attempt_index=%s",
                    attempt.provider,
                    attempt.model,
                    index > 0,
                    index,
                )
                return str(content).strip()
            except Exception as exc:
                errors.append(f"{attempt.provider}:{attempt.model}: {exc}")
                has_more_attempts = index < len(attempts) - 1
                logger.warning(
                    "llm.generate failed provider=%s model=%s attempt_index=%s retryable=%s error=%s",
                    attempt.provider,
                    attempt.model,
                    index,
                    has_more_attempts and _is_retryable_provider_error(exc),
                    exc,
                )
                if has_more_attempts and _is_retryable_provider_error(exc):
                    continue
                raise LLMClientError(f"LLM generation failed: {exc}") from exc

        raise LLMClientError("LLM generation failed: " + " | ".join(errors[:2]))
