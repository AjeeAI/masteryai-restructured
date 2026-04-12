import json
from core_engine.llm.client import chat_completion # Assuming your client name

async def generate_lesson_content(data: dict):
    prompt = f"""
    You are an expert Nigerian Secondary School Tutor. 
    Topic: {data['topic_title']} ({data['subject']} - {data['sss_level']})
    
    Mastery Gaps: {json.dumps(data['mastery_gaps'])}
    Curriculum context: {" ".join(data['curriculum_context'][:5])}

    Task: Write a personalized lesson. 
    Rules: 
    1. Use LaTeX for math.
    2. Use local Nigerian context.
    3. Return JSON only.
    """
    
    response = await chat_completion(prompt, response_format={"type": "json_object"})
    parsed = json.loads(response)
    
    return {
        **parsed,
        "generation_metadata": {"model": "gpt-4o", "engine": "v2"}
    }