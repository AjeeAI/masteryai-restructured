import json
import logging
import os
import re
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Initialize the client
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "gemini"),
    model=os.getenv("LESSON_LLM_MODEL", "gemini-3-flash-preview")
)

def _extract_json(text: str) -> dict:
    """
    Simplified JSON extractor. 
    Trusts Gemini's native 'application/json' mode while handling code blocks.
    """
    # 1. Strip markdown code blocks if present
    text = re.sub(r"```json\s?|\s?```", "", text).strip()
    
    # 2. Isolate the JSON object
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        logger.error(f"RAW LLM OUTPUT (No JSON): {text[:500]}...")
        raise ValueError("No valid JSON found in LLM response.")
    
    json_str = match.group(0)

    # 3. Simple character cleaning (No aggressive backslash regex)
    # We only replace literal newlines that might be inside strings
    # and clean up smart quotes.
    json_str = json_str.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: if there are literal newlines inside the JSON string, 
        # escape them and try one last time.
        try:
            fixed_str = json_str.replace('\n', '\\n').replace('\r', '\\r')
            return json.loads(fixed_str)
        except Exception as e:
            logger.error(f"FATAL DECODE ERROR: {e}\nString: {json_str[:300]}...")
            raise

async def generate_lesson_content(data: dict):
    """Generates lesson content with the EXACT schema the backend requires."""
    
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a high-quality personalized lesson.
    
    OUTPUT FORMAT (EXACT JSON SCHEMA REQUIRED):
    {{
      "title": "{data['topic_title']}",
      "summary": "A 2-sentence overview of what the student will learn.",
      "estimated_duration_minutes": 15,
      "content_blocks": [
        {{ "type": "text", "content": "..." }},
        {{ "type": "example", "content": "..." }},
        {{ "type": "exercise", "content": "..." }}
      ]
    }}

    CRITICAL RULES:
    1. Use LaTeX ($...$) for ALL math/science symbols (e.g. $U_n = a + (n-1)d$).
    2. Ensure every block has a "type" and "content" key.
    3. Return ONLY the JSON object.
    """
    
    try:
        raw_response = await llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        # Normalize the blocks to ensure they match our Pydantic allowed_types
        allowed_types = {"text", "video", "image", "example", "exercise"}
        blocks = parsed.get("content_blocks", [])
        
        final_blocks = []
        for block in blocks:
            if block.get("type") not in allowed_types:
                block["type"] = "text"
            if "content" not in block:
                block["content"] = block.get("body") or block.get("text") or "..."
            final_blocks.append(block)

        # Return the exact keys the validator is looking for
        return {
            "title": parsed.get("title") or data['topic_title'],
            "summary": parsed.get("summary") or f"A lesson on {data['topic_title']}",
            "estimated_duration_minutes": parsed.get("estimated_duration_minutes") or 15,
            "content_blocks": final_blocks,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v3_gemini_schema_perfect"
            }
        }

    except Exception as e:
        logger.error(f"Lesson Engine Crash: {str(e)}", exc_info=True)
        raise