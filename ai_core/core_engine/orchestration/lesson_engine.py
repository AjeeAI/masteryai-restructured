import json
import logging
import os
import re
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Initialize the client using the current Gemini 3 model defaults
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "gemini"),
    model=os.getenv("LESSON_LLM_MODEL", "gemini-3-flash-preview")
)

def _extract_json(text: str) -> dict:
    """
    Maximum-security JSON extractor. 
    Cleans LaTeX backslashes, raw newlines, and smart quotes.
    """
    # 1. Isolate the JSON object from LLM chatter
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        logger.error(f"RAW LLM OUTPUT (No JSON): {text[:500]}...")
        raise ValueError("No valid JSON found in LLM response.")
    
    json_str = match.group(0)

    # 2. THE X-RAY LOG: If it crashes, character 2556 will be in this log line
    logger.info(f"AI_CORE_CLEANING_TARGET (RAW): {json_str}")

    # 3. THE LATEX/ESCAPE FIX: Double-escape backslashes that aren't valid JSON escapes
    # This turns \sigma into \\sigma but leaves \n, \t, etc. alone
    json_str = re.sub(r'\\(?![/bfnrt\\"]|u[0-9a-fA-F]{4})', r'\\\\', json_str)
    
    # 4. THE SMART-QUOTE FIX: Replace curly quotes with standard ones
    json_str = json_str.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")

    # 5. THE CONTROL CHAR STRIP: Remove non-printable characters that break JSON
    # This leaves newlines, tabs, and standard characters.
    json_str = "".join(c for c in json_str if ord(c) >= 32 or c in "\n\r\t")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Standard JSON load failed: {e}. Attempting raw-newline replacement.")
        # Llama 3.3/Gemini sometimes puts literal line breaks inside strings
        # We replace them with the escaped \n version
        json_str_fixed = json_str.replace('\n', '\\n').replace('\r', '\\r')
        try:
            return json.loads(json_str_fixed)
        except Exception as final_err:
            logger.error(f"FATAL DECODE ERROR: {final_err}\nFailed String: {json_str[:500]}...")
            raise

async def generate_lesson_content(data: dict):
    """Generates lesson content with forced type-mapping for Pydantic safety."""
    
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a personalized lesson with high-quality content.
    CRITICAL RULES:
    1. Types allowed: "text", "video", "image", "example", "exercise".
    2. Map intro/conclusion/rules to "text".
    3. Use LaTeX ($...$) for all math/science.
    """
    
    try:
        # THE FIX: Added 'await' here so Python waits for the actual text!
        raw_response = await llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        # 2. THE SANITY MAPPER (Pydantic Fix)
        allowed_types = {"text", "video", "image", "example", "exercise"}
        
        if "content_blocks" in parsed and isinstance(parsed["content_blocks"], list):
            for block in parsed["content_blocks"]:
                # Force types to match literal schema
                if block.get("type") not in allowed_types:
                    block["type"] = "text"
                
                # Ensure the 'content' key is present
                if "content" not in block:
                    block["content"] = block.get("body") or block.get("text") or "..."

        # Final metadata stamp
        return {
            **parsed,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v2_fixed_pydantic_latex_safe"
            }
        }

    except Exception as e:
        logger.error(f"Lesson Engine Crash: {str(e)}", exc_info=True)
        raise