import json
import logging
import os
import re
from uuid import uuid4
from core_engine.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Initialize client (Updated defaults to Gemini 3 Flash)
llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "gemini"),
    model=os.getenv("DIAGNOSTIC_LLM_MODEL", "gemini-2.5-flash")
)

def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise

async def generate_pedagogical_questions(subject: str, level: str, concepts: list) -> list:
    """Uses LLMClient to generate high-quality Nigerian curriculum questions."""
    
    concept_str = "\n".join([f"- {c.label} (Topic: {c.topic_title})" for c in concepts])

    prompt = f"""
    You are a Senior Examiner for the Nigerian {subject} curriculum ({level}).
    Write ONE multiple choice question for EACH concept:
    {concept_str}
    
    RULES:
    1. Test understanding, not just definitions.
    2. Distractors must be plausible.
    3. Return ONLY JSON.
    
    FORMAT:
    {{ "questions": [ {{ "concept_id": "...", "prompt": "...", "options": ["A", "B", "C", "D"], "correct_answer": "A" }} ] }}
    """

    try:
        # THE FIX: Added 'await' here to wait for Gemini to finish generating!
        raw_response = await llm_client.generate(prompt)
        data = _extract_json(raw_response)
        
        final_questions = []
        concept_map = {c.concept_id: c for c in concepts}
        
        for q in data["questions"]:
            c = concept_map.get(q["concept_id"])
            final_questions.append({
                "question_id": str(uuid4()),
                "concept_id": q["concept_id"],
                "topic_id": getattr(c, 'topic_id', 'diagnostic'),
                "topic_title": getattr(c, 'topic_title', 'General'),
                "prompt": q["prompt"],
                "options": q["options"],
                "correct_answer": q["correct_answer"]
            })
        return final_questions
    except Exception as e:
        logger.error(f"Diagnostic generation failed: {e}")
        raise