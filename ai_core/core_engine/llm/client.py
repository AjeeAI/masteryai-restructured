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

    def _primary_attempt(self) -> _ProviderAttempt:
        """Configures the single primary attempt. No safety net logic."""
        provider = (self.provider or "groq").strip().lower()
        model = (self.model or "").strip()
        if not model:
            raise LLMClientError("No LLM model configured.")

        return _ProviderAttempt(
            provider=provider,
            model=model,
            api_key=self._resolve_api_key(provider),
            base_url=(
                os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
                if provider == "groq"
                else None
            ),
        )

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
        """Generate a completion. NO FALLBACKS. If it fails, it explodes loudly."""
        attempt = self._primary_attempt()
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
                "llm.generate success provider=%s model=%s",
                attempt.provider,
                attempt.model,
            )
            return str(content).strip()
            
        except Exception as exc:
            # LOUD ERROR: Log the full context so we can debug on Render.
            logger.error(f"LLM CRASH: provider={attempt.provider} model={attempt.model} error={exc}")
            raise LLMClientError(f"LLM Engine Failure ({attempt.provider}/{attempt.model}): {str(exc)}")