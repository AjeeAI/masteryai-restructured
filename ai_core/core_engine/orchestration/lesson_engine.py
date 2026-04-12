import json
import logging
import os
import re
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Initialize the client from your client.py
# It will use your env vars (GROQ_API_KEY, etc.) automatically
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "groq"),
    model=os.getenv("LESSON_LLM_MODEL", "llama-3.3-70b-versatile")
)

def _extract_json(text: str) -> dict:
    """Helper to find JSON even if the LLM adds chatter."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise

async def generate_lesson_content(data: dict):
    """Generates personalized lesson content with strict type enforcement."""
    
    # 1. ENHANCED PROMPT: We tell the LLM EXACTLY what types are allowed.
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a personalized lesson.
    
    CRITICAL SCHEMA RULES:
    Each block in 'content_blocks' MUST have a 'type' key.
    The 'type' MUST be exactly one of: "text", "video", "image", "example", or "exercise".
    DO NOT use types like "introduction", "definition", or "conclusion". Map those to "text".
    
    Return ONLY a JSON object with keys: title, summary, estimated_duration_minutes, content_blocks.
    """
    
    try:
        raw_response = llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        # 2. SANITY MAPPER: Defensive fix to prevent the 422 error you just saw.
        # This maps any "hallucinated" types back to "text".
        allowed_types = {"text", "video", "image", "example", "exercise"}
        
        if "content_blocks" in parsed:
            for block in parsed["content_blocks"]:
                if block.get("type") not in allowed_types:
                    # If LLM sent "introduction", change it to "text"
                    block["type"] = "text" 
        
        return {
            **parsed,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v2_fixed"
            }
        }
    except Exception as e:
        logger.error(f"Lesson generation failed: {e}")
        raise