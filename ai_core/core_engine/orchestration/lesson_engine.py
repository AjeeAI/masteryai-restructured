import json
import logging
import os
import re
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "groq"),
    model=os.getenv("LESSON_LLM_MODEL", "llama-3.3-70b-versatile")
)

def _extract_json(text: str) -> dict:
    """Robust helper to extract JSON from LLM output using Regex."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("No valid JSON found in LLM response.")

async def generate_lesson_content(data: dict):
    """Generates personalized lesson content with type enforcement and logging."""
    
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}

    Task: Write a personalized lesson with high-quality content.
    CRITICAL SCHEMA RULES:
    1. Each block in 'content_blocks' MUST have 'type' and 'content' keys.
    2. The 'type' MUST be: "text", "video", "image", "example", or "exercise".
    3. Map any other types (introduction, conclusion, definition) to "text".
    4. Use LaTeX for math ($...$, $$...$$) and local Nigerian contexts.

    Return ONLY a JSON object.
    """
    
    try:
        raw_response = llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        allowed_types = {"text", "video", "image", "example", "exercise"}
        
        if "content_blocks" in parsed and isinstance(parsed["content_blocks"], list):
            for block in parsed["content_blocks"]:
                if block.get("type") not in allowed_types:
                    block["type"] = "text"
                
                if "content" not in block:
                    block["content"] = block.get("body") or block.get("text") or "..."

        # --- LOGGING: See the final outgoing payload in Render logs ---
        logger.info(f"AI_CORE_OUTGOING_PAYLOAD: {json.dumps(parsed)}")
        # --------------------------------------------------------------

        return {
            **parsed,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v2_fixed_logging_enabled"
            }
        }

    except Exception as e:
        logger.error(f"Lesson generation crash: {str(e)}", exc_info=True)
        raise