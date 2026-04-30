import os
from google import genai
from prompt import SYSTEM_PROMPT, build_user_message

def get_code_review(diff: str) -> str:
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
           model="gemini-1.5-flash",
            contents=SYSTEM_PROMPT + "\n\n" + build_user_message(diff)
        )
        return response.text
    except Exception as e:
        print(f"LLM error: {e}")
        return "Code Review Buddy encountered an error generating the review."