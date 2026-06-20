import os
from google import genai
from dotenv import load_dotenv

# Load your .env file
load_dotenv()

def check_live_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in .env")
        return

    # Use v1beta as the Live API is generally available there
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    print(f"🔍 Fetching models for your API key...")
    models = client.models.list()
    
    found = False
    for m in models:
        # Check if the model supports bidirectional streaming
        if hasattr(m, 'supported_methods') and 'bidiGenerateContent' in m.supported_methods:
            print(f"✨ SUPPORTED LIVE MODEL: {m.name}")
            found = True
            
    if not found:
        print("⚠️ No models found with 'bidiGenerateContent' support.")
        print("   This means your API key does not have access to the Live API.")
        print("   Check your project settings in Google AI Studio.")

if __name__ == "__main__":
    check_live_models()
