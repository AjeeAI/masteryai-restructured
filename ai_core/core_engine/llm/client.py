"""LLM client supporting Gemini (via LangChain) and OpenAI."""

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
    provider: str  # Now expecting 'gemini' or 'openai'
    model: str
    api_key: Optional[str] = None

    def _resolve_api_key(self, provider: str) -> str:
        normalized = provider.lower()
        # Prioritize specific keys, then fall back to a generic LLM_API_KEY
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

    def _get_gemini_engine(self, attempt: _ProviderAttempt):
        """Initializes Gemini via LangChain ChatGoogleGenerativeAI."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
        except ModuleNotFoundError:
            raise LLMClientError("Missing dependencies: pip install langchain-google-genai google-generativeai")

        # Safety settings are mandatory to prevent blocked curriculum blocks
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        return ChatGoogleGenerativeAI(
            model=attempt.model,
            google_api_key=attempt.api_key,
            temperature=0.2,
            safety_settings=safety_settings,
            model_kwargs={"response_mime_type": "application/json"} # Native JSON enforcement
        )

    async def generate(self, prompt: str) -> str:
        """Asynchronously generates content. Defaults to Gemini if not specified."""
        provider = (self.provider or "gemini").strip().lower()
        model = (self.model or "gemini-1.5-flash").strip()
        
        attempt = _ProviderAttempt(
            provider=provider,
            model=model,
            api_key=self._resolve_api_key(provider)
        )

        try:
            if provider == "gemini":
                engine = self._get_gemini_engine(attempt)
                response = await engine.ainvoke(prompt)
                content = response.content
            elif provider == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=attempt.api_key)
                response = await client.chat.completions.create(
                    model=attempt.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
            else:
                raise LLMClientError(f"Unsupported provider: {provider}")

            if not content:
                raise LLMClientError("LLM returned empty content.")

            logger.info(f"llm.generate success | provider={provider} | model={model}")
            return str(content).strip()

        except Exception as exc:
            logger.error(f"LLM FAILURE: {exc}")
            raise LLMClientError(f"AI Core Engine Error ({provider}): {str(exc)}")