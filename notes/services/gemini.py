import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")

def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)

        print(response)

        return response.text

    except Exception as e:
        print("GEMINI ERROR:", e)
        raise
