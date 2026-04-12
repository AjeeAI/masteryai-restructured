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
    """Generates personalized lesson content using the LLMClient."""
    
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a personalized lesson.
    Rules:
    1. Use LaTeX for math ($...$ for inline, $$...$$ for blocks).
    2. Use local Nigerian examples.
    3. Return ONLY a JSON object with keys: title, summary, estimated_duration_minutes, content_blocks.
    """
    
    try:
        # Your client.generate is sync, so we don't 'await' it
        raw_response = llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        return {
            **parsed,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v2"
            }
        }
    except Exception as e:
        logger.error(f"Lesson generation failed: {e}")
        raise