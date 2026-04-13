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
    Enhanced JSON extractor that handles multiple objects and common LLM quirks.
    """
    # 1. Try to find a single root object or a list
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        logger.error(f"RAW LLM OUTPUT (No JSON): {text[:500]}...")
        raise ValueError("No valid JSON found in LLM response.")
    
    json_str = match.group(0)

    # 2. If the LLM returned multiple objects {}{}, wrap them in a list
    # This fixes the "Extra data" error
    if json_str.count('}\n{') > 0 or json_str.count('}{') > 0:
        logger.warning("Detected multiple JSON objects; attempting to wrap in a list.")
        # Replace the boundary between objects with a comma
        json_str = json_str.replace('}\n{', '},{').replace('}{', '},{')
        json_str = f"[{json_str}]"

    # 3. Clean common breaking characters
    json_str = re.sub(r'\\(?![/bfnrt\\"]|u[0-9a-fA-F]{4})', r'\\\\', json_str)
    json_str = json_str.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    json_str = "".join(c for c in json_str if ord(c) >= 32 or c in "\n\r\t")

    try:
        data = json.loads(json_str)
        # If we had to wrap it in a list, normalize it to the 'content_blocks' format
        if isinstance(data, list):
            return {"content_blocks": data}
        return data
    except json.JSONDecodeError as e:
        logger.error(f"FATAL DECODE ERROR: {e}\nFailed String: {json_str[:500]}...")
        raise

async def generate_lesson_content(data: dict):
    """Generates lesson content with a strict root-object prompt."""
    
    # THE KEY CHANGE: We explicitly define the root key 'content_blocks'
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a high-quality personalized lesson.
    
    OUTPUT FORMAT (MUST BE THIS EXACT JSON SCHEMA):
    {{
      "topic_title": "{data['topic_title']}",
      "content_blocks": [
        {{ "type": "text", "content": "..." }},
        {{ "type": "example", "content": "..." }},
        {{ "type": "exercise", "content": "..." }}
      ]
    }}

    CRITICAL RULES:
    1. Allowed types: "text", "video", "image", "example", "exercise".
    2. Use LaTeX ($...$) for all math formulas or technical symbols.
    3. Return ONLY the JSON. No conversational filler.
    """
    
    try:
        raw_response = await llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        # Ensure we have the list even if the LLM ignored the root key
        blocks = parsed.get("content_blocks") or parsed.get("lessons") or []
        if not blocks and isinstance(parsed, list):
            blocks = parsed

        allowed_types = {"text", "video", "image", "example", "exercise"}
        
        final_blocks = []
        for block in blocks:
            if block.get("type") not in allowed_types:
                block["type"] = "text"
            
            if "content" not in block:
                block["content"] = block.get("body") or block.get("text") or "..."
            final_blocks.append(block)

        return {
            "topic_title": parsed.get("topic_title", data['topic_title']),
            "content_blocks": final_blocks,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v3_gemini_hardened"
            }
        }

    except Exception as e:
        logger.error(f"Lesson Engine Crash: {str(e)}", exc_info=True)
        raise