"""LLM client supporting Gemini 2.5/3 Series (Modern SDK) and OpenAI."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

# New imports for 503 handling
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.genai.errors import ServerError

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ServerError),
        reraise=True
    )
    async def _generate_gemini(self, attempt: _ProviderAttempt, prompt: str) -> str:
        """Calls Gemini using the modern google-genai SDK with automatic 503 retries."""
        try:
            from google import genai
            from google.genai import types
        except ModuleNotFoundError:
            raise LLMClientError("Missing dependency: pip install google-genai")

        client = genai.Client(api_key=attempt.api_key)
        
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
            response = await client.aio.models.generate_content(
                model=attempt.model,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API Core Failure: {e}")
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
        """Asynchronously generates content. Defaults to Gemini 2.5 Flash."""
        provider = (self.provider or "gemini").strip().lower()
        model = (self.model or "gemini-2.5-flash").strip()
        
        # --- BULLETPROOF OVERRIDE ---
        # If the model name looks like an old preview or wrong provider, fix it.
        if provider == "gemini" and ("openai" in model or "3-flash-preview" in model):
            logger.warning(f"Fixing invalid Gemini model string '{model}' to 'gemini-2.5-flash'")
            model = "gemini-2.5-flash"
        
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
            # We already log specifics in the provider methods; this is the final catch-all.
            raise LLMClientError(f"AI Core Engine Error ({provider}): {str(exc)}")