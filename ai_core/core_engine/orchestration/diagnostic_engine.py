import json
import logging
from uuid import uuid4
# Assuming you have an LLM wrapper like this in your project
from core_engine.llm.client import chat_completion 

logger = logging.getLogger(__name__)

async def generate_pedagogical_questions(subject: str, level: str, concepts: list) -> list:
    """Uses LLM to generate high-quality Nigerian curriculum questions."""
    
    concept_str = "\n".join([f"- {c.label} (Topic: {c.topic_title})" for c in concepts])

    prompt = f"""
    You are a Senior Examiner for the Nigerian {subject} curriculum ({level}).
    Your task is to create a Baseline Diagnostic Assessment for a new student.
    
    For EACH concept below, write ONE high-quality multiple choice question.
    CONCEPTS:
    {concept_str}
    
    STRICT RULES:
    1. Focus on 'Pedagogical Depth': test if they understand the WHY, not just the definition.
    2. Distractors (wrong answers) must be plausible and based on common student misconceptions.
    3. The language must be appropriate for a Nigerian secondary school student.
    4. Return ONLY a JSON object.
    
    FORMAT:
    {{
      "questions": [
        {{
          "concept_id": "matching_id_from_input",
          "prompt": "The question text...",
          "options": ["Option A", "Option B", "Option C", "Option D"],
          "correct_answer": "A"
        }}
      ]
    }}
    """

    try:
        # Call your existing LLM client
        response = await chat_completion(prompt, response_format={"type": "json_object"})
        data = json.loads(response)
        
        # Add IDs and titles back in
        final_questions = []
        concept_map = {{c.concept_id: c for c in concepts}}
        
        for q in data["questions"]:
            c = concept_map.get(q["concept_id"])
            final_questions.append({{
                "question_id": str(uuid4()),
                "concept_id": q["concept_id"],
                "topic_id": getattr(c, 'topic_id', 'diagnostic'),
                "topic_title": getattr(c, 'topic_title', 'General'),
                "prompt": q["prompt"],
                "options": q["options"],
                "correct_answer": q["correct_answer"]
            }})
        return final_questions
    except Exception as e:
        logger.error(f"LLM Diagnostic Generation failed: {{e}}")
        raise