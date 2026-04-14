import json
import logging
import os
import re
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Initialize the client
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "gemini"),
    model=os.getenv("LESSON_LLM_MODEL", "gemini-2.5-flash")
)

def _extract_json(text: str) -> dict:
    """
    Safely extract and parse JSON.
    Trusts the modern SDK's application/json mime type.
    """
    # 1. Strip markdown code blocks if present
    text = re.sub(r"```json\s?|\s?```", "", text).strip()
    
    # 2. Isolate the JSON object
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        logger.error(f"RAW LLM OUTPUT (No JSON): {text[:500]}...")
        raise ValueError("No valid JSON found in LLM response.")
    
    json_str = match.group(0)

    # 3. Simple character cleaning for smart quotes
    json_str = json_str.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    
    try:
        # strict=False allows actual unescaped newlines inside strings without crashing
        return json.loads(json_str, strict=False)
    except json.JSONDecodeError as e:
        logger.error(f"FATAL DECODE ERROR: {e}\nProblematic String snippet:\n{json_str[max(0, e.pos-50):e.pos+50]}")
        raise

async def generate_lesson_content(data: dict):
    """Generates lesson content with the EXACT schema the backend requires."""
    
    subject_lower = str(data.get('subject', '')).lower()
    
    # DYNAMIC RULE: Define which subjects need strict Math escaping
    math_heavy_subjects = ["math", "mathematics", "further math", "physics", "chemistry", "basic science"]
    is_math_subject = any(sub in subject_lower for sub in math_heavy_subjects)

    if is_math_subject:
        formatting_instruction = """
    2. MATH/LATEX ESCAPING: You MUST use LaTeX ($...$) for ALL math/science symbols. Because this is a JSON response, you MUST DOUBLE-ESCAPE all LaTeX backslashes (e.g., write \\\\frac instead of \\frac, and \\\\times instead of \\times). Do NOT use unescaped backslashes.
        """
    else:
        formatting_instruction = """
    2. TEXT FORMATTING: Write clearly and naturally in standard prose. Use standard English punctuation. Do NOT use excessive backslashes or mathematical formatting unless strictly necessary for a specific example.
        """

    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:3])}

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
    1. STRICT LENGTH LIMIT: Return EXACTLY 3 content_blocks. Do not write a long essay. Keep text blocks under 100 words.{formatting_instruction}
    3. Ensure every block has a "type" and "content" key.
    4. Return ONLY the raw JSON object. Do not wrap in markdown blocks.
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