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
            logger.error(f"Gemini API Core Failure: {e}", exc_info=True)
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
            raise LLMClientError(f"AI Core Engine Error ({provider}): {str(exc)}")
    
    async def generate_image(self, prompt: str) -> Optional[str]:
        """Asynchronously generates an image using the Gemini Developer API."""
        provider = (self.provider or "gemini").strip().lower()
        logger.info(f"🔍 [CLIENT TRACE] generate_image initialized. Provider: {provider}")
        
        if provider != "gemini":
            logger.warning("⚠️ [CLIENT TRACE] Image generation bypassed. Only supported via Gemini SDK.")
            return None
            
        api_key = self._resolve_api_key(provider)
        logger.info("🔑 [CLIENT TRACE] API key resolved successfully.")
        
        try:
            from google import genai
            from google.genai import types
            import base64
        except ModuleNotFoundError:
            logger.critical("🚨 [CLIENT TRACE] google-genai module missing!")
            raise LLMClientError("Missing dependency: pip install google-genai")

        client = genai.Client(api_key=api_key)

        try:
            target_model = 'gemini-2.5-flash-image'
            logger.info(f"🚀 [CLIENT TRACE] Dispatching to {target_model} with prompt length: {len(prompt)}")
            
            response = await client.aio.models.generate_content(
                model=target_model, 
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9" 
                    )
                )
            )
            
            logger.info("✅ [CLIENT TRACE] Google API responded. Analyzing payload...")
            
            if response.parts:
                logger.info(f"📦 [CLIENT TRACE] Payload contains {len(response.parts)} parts.")
                for idx, part in enumerate(response.parts):
                    if part.inline_data:
                        logger.info(f"🖼️ [CLIENT TRACE] Part {idx} contains inline_data. Extracting bytes...")
                        image_bytes = part.inline_data.data
                        base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
                        mime_type = getattr(part.inline_data, 'mime_type', 'image/jpeg')
                        
                        logger.info("✨ [CLIENT TRACE] Extraction and Base64 encoding complete!")
                        return f"data:{mime_type};base64,{base64_encoded}"
                    else:
                        logger.warning(f"⚠️ [CLIENT TRACE] Part {idx} exists but has NO inline_data. Content: {part}")
            else:
                logger.warning("⚠️ [CLIENT TRACE] response.parts is entirely empty or None!")
            
            logger.error("❌ [CLIENT TRACE] End of function reached. API succeeded but no valid image data was parsed.")
            return None
                
        except Exception as e:
            # exc_info=True dumps the full stack trace to the terminal
            logger.error(f"❌ [CLIENT TRACE] CRITICAL FAILURE during image generation: {e}", exc_info=True)
            return None
        
    from fastapi import WebSocket, WebSocketDisconnect
    
@router.websocket("/live-voice/{session_id}")
async def tutor_voice_stream(
    websocket: WebSocket,
    session_id: UUID,
    subject: str,
    model_tier: str = "flash", # 'pro' or 'flash'
    db: Session = Depends(get_db),
):
    await websocket.accept()
    
    voice_config = get_subject_voice_config(subject)
    client = _service().llm_client 
    
    # Custom instructions for Gemini 3's advanced reasoning
    system_instruction = (
        f"{voice_config['style']} "
        "You are an expert SSS teacher. Use Socratic questioning. "
        "If the student sounds confused, simplify your language. "
        "Ground every response in the provided curriculum metadata."
    )

    try:
        # We pass the 'model_tier' (pro/flash) directly to our new client method
        async with await client.connect_live(
            model_type=model_tier,
            system_instruction=system_instruction,
            voice_name=voice_config["voice"]
        ) as session:
            
            async def receive_from_student():
                async for message in websocket.iter_bytes():
                    # Sending raw audio bytes to Gemini 3
                    await session.send(input=message, end_of_turn=True)

            async def send_to_student():
                async for response in session.receive():
                    if response.audio:
                        await websocket.send_bytes(response.audio)
                    if response.text:
                        # Real-time transcription for the UI
                        await websocket.send_json({"text": response.text})

            await asyncio.gather(receive_from_student(), send_to_student())

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} ended.")
    except Exception as e:
        logger.error(f"Multimodal Live Error: {e}")
        await websocket.close(code=1011)