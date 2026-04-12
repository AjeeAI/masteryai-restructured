import json
import logging
import os
import re
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Initialize the client using the current Llama 3.3 versatile model
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "groq"),
    model=os.getenv("LESSON_LLM_MODEL", "llama-3.3-70b-versatile")
)

def _extract_json(text: str) -> dict:
    """Robust helper to extract JSON from LLM output using Regex."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # If the LLM includes markdown backticks or conversational chatter
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("No valid JSON found in LLM response.")

async def generate_lesson_content(data: dict):
    """
    Generates personalized lesson content.
    Enforces strict block types to satisfy Backend Pydantic models.
    """
    
    # 1. THE PROMPT
    # We explicitly list the allowed types to guide the LLM
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a personalized lesson with high-quality content.
    
    CRITICAL SCHEMA RULES:
    1. Each block in 'content_blocks' MUST have a 'type' and 'content' key.
    2. The 'type' MUST be exactly one of: "text", "video", "image", "example", or "exercise".
    3. DO NOT hallucinate types. Use "text" for introductions, rules, and conclusions.
    4. Use LaTeX for math ($...$ for inline, $$...$$ for blocks).
    5. Use local Nigerian names and relatable contexts.

    Return ONLY a JSON object with keys: title, summary, estimated_duration_minutes, content_blocks.
    """
    
    try:
        # Call the synchronous generate method from client.py
        raw_response = llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        # 2. THE SANITY MAPPER (The Pydantic Fix)
        # These are the ONLY types your backend allows
        allowed_types = {"text", "video", "image", "example", "exercise"}
        
        if "content_blocks" in parsed and isinstance(parsed["content_blocks"], list):
            for block in parsed["content_blocks"]:
                # Fix hallucinated types (e.g., 'introduction' -> 'text')
                if block.get("type") not in allowed_types:
                    block["type"] = "text"
                
                # Defensive check for the 'content' key
                # If the LLM used 'body' or 'text' as a key instead of 'content'
                if "content" not in block:
                    block["content"] = block.get("body") or block.get("text") or "Content missing."

        # 3. RETURN WITH METADATA
        return {
            **parsed,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v2_fixed_pydantic_safe"
            }
        }

    except Exception as e:
        logger.error(f"Lesson generation failed internally: {str(e)}", exc_info=True)
        # Raising the error here ensures main.py catches it and returns a 500
        raise