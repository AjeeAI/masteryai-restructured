"""LLM client supporting Gemini 3 Series (Modern SDK) and OpenAI."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

class LLMClientError(RuntimeError):
    pass

@dataclass(frozen=True)
class _ProviderAttempt:
    provider: str
    model: str
    api_key: str

@dataclass
class LLMClient:
    provider: str  # 'gemini' or 'openai'
    model: str
    api_key: Optional[str] = None

    def _resolve_api_key(self, provider: str) -> str:
        normalized = provider.lower()
        if normalized == "gemini":
            key = os.getenv("GEMINI_API_KEY")
        elif normalized == "openai":
            key = os.getenv("OPENAI_API_KEY")
        else:
            key = None
            
        final_key = key or self.api_key or os.getenv("LLM_API_KEY")
        if not final_key:
            raise LLMClientError(f"No API key found for {provider}. Set GEMINI_API_KEY or OPENAI_API_KEY.")
        return final_key

    async def _generate_gemini(self, attempt: _ProviderAttempt, prompt: str) -> str:
        """Calls Gemini using the modern 2026 google-genai SDK."""
        try:
            from google import genai
            from google.genai import types
        except ModuleNotFoundError:
            raise LLMClientError("Missing dependency: pip install google-genai")

        client = genai.Client(api_key=attempt.api_key)
        
        # 2026 Best Practice: Block nothing for curriculum, enforce JSON mime type
        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ]
        )

        try:
            # Gemini 3 natively handles high-concurrency async calls
            response = await client.models.generate_content(
                model=attempt.model,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini 3 API Failure: {e}")
            raise

    async def _generate_openai(self, attempt: _ProviderAttempt, prompt: str) -> str:
        """Calls OpenAI with modern Async client."""
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=attempt.api_key)
        
        response = await client.chat.completions.create(
            model=attempt.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        return response.choices[0].message.content or ""

    async def generate(self, prompt: str) -> str:
        """Asynchronously generates content. Defaults to Gemini 3 Flash."""
        provider = (self.provider or "gemini").strip().lower()
        # Defaulting to the 2026 '3' series model
        model = (self.model or "gemini-3-flash-preview").strip()
        
        attempt = _ProviderAttempt(
            provider=provider,
            model=model,
            api_key=self._resolve_api_key(provider)
        )

        try:
            if provider == "gemini":
                content = await self._generate_gemini(attempt, prompt)
            elif provider == "openai":
                content = await self._generate_openai(attempt, prompt)
            else:
                raise LLMClientError(f"Unsupported provider: {provider}")

            if not content:
                raise LLMClientError("LLM returned empty content.")

            logger.info(f"llm.generate success | provider={provider} | model={model}")
            return str(content).strip()

        except Exception as exc:
            logger.error(f"LLM FAILURE: {exc}")
            raise LLMClientError(f"AI Core Engine Error ({provider}): {str(exc)}")