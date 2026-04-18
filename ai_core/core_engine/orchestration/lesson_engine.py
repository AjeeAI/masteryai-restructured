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
# 1. EXTERNAL SERVICES CONFIGURATION
# ---------------------------------------------------------

# Cloudinary for hosting generated visuals
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# Primary Lesson Model: Gemini 2.5 Flash
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "gemini"),
    model=os.getenv("LESSON_LLM_MODEL", "gemini-2.5-flash")
)

# ---------------------------------------------------------
# 2. UTILITY FUNCTIONS
# ---------------------------------------------------------

def _extract_json(text: str) -> dict:
    """
    Safely extract and parse JSON from the LLM's raw response.
    """
    text = re.sub(r"```json\s?|\s?```", "", text).strip()
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        logger.error(f"RAW LLM OUTPUT (No JSON): {text[:500]}...")
        raise ValueError("No valid JSON found in LLM response.")
    
    json_str = match.group(0)
    json_str = json_str.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    
    try:
        return json.loads(json_str, strict=False)
    except json.JSONDecodeError as e:
        logger.error(f"DECODE ERROR: {e}\nSnippet: {json_str[max(0, e.pos-50):e.pos+50]}")
        raise

# ---------------------------------------------------------
# 3. CORE LESSON ENGINE
# ---------------------------------------------------------

async def generate_lesson_content(data: dict):
    """
    Generates a personalized lesson payload.
    Orchestrates Gemini 2.5 Flash (Text) and Gemini Image (Visuals) with retry logic.
    """
    
    subject_lower = str(data.get('subject', '')).lower()
    
    # --- A. Dynamic Formatting Rules (Math/Science) ---
    math_heavy = ["math", "mathematics", "further math", "physics", "chemistry", "basic science"]
    is_math = any(sub in subject_lower for sub in math_heavy)

    if is_math:
        formatting_instruction = """
        2. MATH FORMATTING: Use LaTeX ($...$) for ALL math/science symbols. 
        You MUST DOUBLE-ESCAPE all backslashes (e.g., write \\\\frac instead of \\frac).
        """
    else:
        formatting_instruction = """
        2. TEXT FORMATTING: Use standard English prose and punctuation. 
        Do NOT use mathematical formatting or excessive backslashes.
        """

    # --- B. Multi-Preference Injection ---
    # Pulling the booleans from your updated schema
    prefs = data.get('preferences', {})
    is_visual = prefs.get('visual_learner', False)
    is_practical = prefs.get('practice_heavy', False)
    examples_first = prefs.get('examples_first', False)
    depth = prefs.get('explanation_depth', 'standard')
    
    style_segments = []
    
    if is_visual:
        style_segments.append(
            "USER PREFERENCE - VISUAL: Include exactly ONE block with type 'image'. "
            "The 'content' must be a highly descriptive, literal prompt for an educational illustration. "
            "STRICT RULES FOR IMAGES: If the topic is abstract (like Math), prompt for a specific infographic, chart, or a literal real-world scenario (e.g., 'A scientist measuring a beaker', 'A ruler measuring a block'). "
            "ABSOLUTELY NO fantasy, no metaphors, no fictional book covers, and no abstract art. Keep it strictly academic and realistic."
        )
    
    if is_practical or examples_first:
        style_segments.append(
            f"USER PREFERENCE - {'PRACTICAL' if is_practical else 'EXAMPLE-DRIVEN'}: "
            "Prioritize 'example' and 'exercise' blocks. Keep theory brief and applicable."
        )

    style_instruction = " ".join(style_segments) if style_segments else f"Focus on {depth} theoretical foundations."

    # --- C. The Master Prompt ---
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor.
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    Mastery Gaps: {json.dumps(data.get('mastery_gaps', []))}
    Curriculum context: {" ".join(data.get('curriculum_context', [])[:3])}

    Task: Write a high-quality personalized lesson.
    
    OUTPUT SCHEMA (RAW JSON ONLY):
    {{
      "title": "{data['topic_title']}",
      "summary": "2-sentence overview.",
      "estimated_duration_minutes": 15,
      "content_blocks": [
        {{ "type": "text", "content": "..." }},
        {{ "type": "image", "content": "<WRITE YOUR HIGHLY DESCRIPTIVE IMAGE PROMPT HERE>" }},
        {{ "type": "exercise", "content": "..." }}
      ]
    }}

    CRITICAL RULES:
    1. STRICT LENGTH: Return EXACTLY 3 content_blocks. Keep text blocks under 100 words.
    {formatting_instruction}
    3. PERSONALIZATION: {style_instruction}
    4. VALID TYPES: text, image, video, example, exercise.
    5. Return ONLY the raw JSON object. No markdown wrapping.
    """
    
    try:
        # STEP 1: Generate Text Structure (Gemini 2.5 Flash) WITH RETRY LOGIC
        max_retries = 3
        parsed = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🧠 [ENGINE TRACE] Dispatching to text LLM (Attempt {attempt + 1}/{max_retries})...")
                raw_response = await llm_client.generate(prompt)
                parsed = _extract_json(raw_response)
                break  # Success! Break out of the retry loop
            except Exception as parse_err:
                logger.warning(f"⚠️ [ENGINE TRACE] Output parsing failed on attempt {attempt + 1}: {parse_err}")
                if attempt == max_retries - 1:
                    logger.error("❌ [ENGINE TRACE] Max retries reached for text generation.")
                    raise  # If it fails 3 times, let it crash to trigger the 500
        
        final_blocks = parsed.get("content_blocks", [])
        valid_blocks = [] # Array to hold only successful blocks
        
        # STEP 2: The Multimodal Pipeline (Gemini Developer API + Cloudinary)
        for block in final_blocks:
            if block.get("type") == "image":
                image_prompt = block.get("content")
                
                try:
                    logger.info(f"🚀 [ENGINE TRACE] Starting Image Gen Pipeline for prompt: {image_prompt[:50]}...")
                    
                    # Call Gemini Image API
                    image_data_uri = await llm_client.generate_image(
                        prompt=image_prompt
                    )
                    
                    if not image_data_uri:
                        raise ValueError("LLM returned None for image.")
                    
                    logger.info(f"✅ [ENGINE TRACE] Image Generated Successfully! Data URI length: {len(image_data_uri)}")
                    logger.info("☁️ [ENGINE TRACE] Uploading to Cloudinary...")
                    
                    # Async Upload to Cloudinary
                    upload_res = await asyncio.to_thread(
                        cloudinary.uploader.upload,
                        image_data_uri,
                        folder="masteryai/lesson_visuals",
                        resource_type="image"
                    )
                    
                    # Fetch optimized URL
                    optimized_url, _ = cloudinary.utils.cloudinary_url(
                        upload_res['public_id'], 
                        fetch_format="auto", 
                        quality="auto",
                        secure=True
                    )
                    
                    logger.info(f"✅ [ENGINE TRACE] Cloudinary Success! URL: {optimized_url}")
                    
                    block["url"] = optimized_url
                    block["content"] = "Visual aid for this lesson."
                    valid_blocks.append(block) # Image succeeded, add it to the valid list
                    
                except Exception as img_err:
                    logger.warning(f"⚠️ [ENGINE TRACE] Image generation failed ({img_err}). Silently dropping visual block.")
                    # We simply DO NOT append the block to valid_blocks. 
                    # The loop moves on, and the image vanishes like it never existed.
                    continue 
            else:
                 # If it's a text or exercise block, it's always valid
                 valid_blocks.append(block)

        # STEP 3: Return final sanitized payload using ONLY the valid blocks
        return {
            "title": parsed.get("title") or data['topic_title'],
            "summary": parsed.get("summary") or f"A lesson on {data['topic_title']}",
            "estimated_duration_minutes": parsed.get("estimated_duration_minutes") or 15,
            "content_blocks": valid_blocks, # <-- Return the filtered list here!
            "generation_metadata": {
                "model": llm_client.model,
                "engine": "v3_multimodal_lesson_engine"
            }
        }

    except Exception as e:
        logger.error(f"❌ [ENGINE TRACE] Lesson Engine Crash: {e}", exc_info=True)
        raise