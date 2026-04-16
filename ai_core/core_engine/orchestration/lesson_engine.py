import json
import logging
import os
import re
import asyncio
import cloudinary
import cloudinary.uploader
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CLOUDINARY CONFIGURATION
# ---------------------------------------------------------
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

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
    
    # ==========================================
    # 1. DYNAMIC MATH/SUBJECT RULE
    # ==========================================
    math_heavy_subjects = ["math", "mathematics", "further math", "physics", "chemistry", "basic science"]
    is_math_subject = any(sub in subject_lower for sub in math_heavy_subjects)

    if is_math_subject:
        formatting_instruction = """
    2. MATH/LATEX ESCAPING: You MUST use LaTeX ($...$) for ALL math/science symbols. Because this is a JSON response, you MUST DOUBLE-ESCAPE all LaTeX backslashes (e.g., write \\\\frac instead of \\frac).
        """
    else:
        formatting_instruction = """
    2. TEXT FORMATTING: Write clearly and naturally in standard prose. Use standard English punctuation. Do NOT use excessive backslashes or mathematical formatting.
        """

    # ==========================================
    # 2. DYNAMIC LEARNING STYLE INJECTION
    # ==========================================
    preferences = data.get('preferences', {})
    learning_style = str(preferences.get('learning_style', '')).lower()
    examples_first = preferences.get('examples_first', False)
    
    if learning_style == 'visual':
        style_instruction = (
            "USER PREFERENCE - VISUAL LEARNER: You MUST prioritize visual learning. "
            "You MUST include exactly ONE block with the type 'image'. "
            "For the 'content' of the image block, write a highly detailed, descriptive prompt "
            "that an AI image generator can use to create a photorealistic educational illustration. "
            "Do not include text overlays in the image prompt."
        )
    elif learning_style == 'practical' or examples_first:
        style_instruction = (
            "USER PREFERENCE - PRACTICAL LEARNER: The user learns best through doing. "
            "You MUST make at least 2 of your 3 content_blocks 'example' or 'exercise' types. "
            "Skip the long theory and get straight into real-world applications."
        )
    else: 
        style_instruction = (
            "USER PREFERENCE - THEORETICAL LEARNER: Provide detailed 'text' blocks focusing "
            "on the foundational rules and concepts before giving examples."
        )

    # ==========================================
    # 3. MASTER PROMPT
    # ==========================================
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data.get('mastery_gaps', []))}
    Curriculum context: {" ".join(data.get('curriculum_context', [])[:3])}

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
    3. PERSONALIZATION: {style_instruction}
    4. Valid block types: text, image, video, example, exercise.
    5. Ensure every block has a "type" and "content" key.
    6. Return ONLY the raw JSON object. Do not wrap in markdown blocks.
    """
    
    try:
        # Step A: Generate Text Structure
        raw_response = await llm_client.generate(prompt)
        parsed = _extract_json(raw_response)
        
        # Normalize blocks
        allowed_types = {"text", "video", "image", "example", "exercise"}
        blocks = parsed.get("content_blocks", [])
        
        final_blocks = []
        for block in blocks:
            if block.get("type") not in allowed_types:
                block["type"] = "text"
            if "content" not in block:
                block["content"] = block.get("body") or block.get("text") or "..."
            final_blocks.append(block)

        # ==========================================
        # 4. IMAGE INTERCEPTOR & CLOUDINARY UPLOAD
        # ==========================================
        for block in final_blocks:
            if block.get("type") == "image":
                image_prompt = block.get("content")
                
                try:
                    logger.info(f"Generating image via Nano Banana 2 for prompt: {image_prompt[:50]}...")
                    
                    # Generate the image bytes
                    image_bytes = await llm_client.generate_image(
                        model="gemini-3-flash-image", 
                        prompt=image_prompt
                    )
                    
                    # Upload to Cloudinary without blocking the async event loop
                    # We request automatic format (f_auto) and quality (q_auto) for fast WebP delivery
                    upload_result = await asyncio.to_thread(
                        cloudinary.uploader.upload,
                        image_bytes,
                        folder="masteryai/lesson_visuals",
                        resource_type="image"
                    )
                    
                    # Construct optimized URL
                    optimized_url, _ = cloudinary.utils.cloudinary_url(
                        upload_result['public_id'], 
                        fetch_format="auto", 
                        quality="auto",
                        secure=True
                    )
                    
                    block["url"] = optimized_url
                    block["content"] = "Visual aid for this lesson."
                    
                except Exception as img_err:
                    logger.warning(f"Image generation/upload failed: {img_err}")
                    # Graceful Fallback
                    block["type"] = "text"
                    block["content"] = f"[Visual Placeholder: {image_prompt}]"

        # Return exact keys validator is looking for
        return {
            "title": parsed.get("title") or data['topic_title'],
            "summary": parsed.get("summary") or f"A lesson on {data['topic_title']}",
            "estimated_duration_minutes": parsed.get("estimated_duration_minutes") or 15,
            "content_blocks": final_blocks,
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v3_gemini_schema_perfect_with_images"
            }
        }

    except Exception as e:
        logger.error(f"Lesson Engine Crash: {str(e)}", exc_info=True)
        raise