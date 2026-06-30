from django.conf import settings

try:
    from google import genai as google_genai
except ImportError:
    google_genai = None

legacy_genai = None
if google_genai is None:
    try:
        import google.generativeai as legacy_genai
    except ImportError:
        legacy_genai = None


MODEL_NAME = "gemini-2.5-flash"


def generate_content(prompt):
    if google_genai:
        client = google_genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return response

    if legacy_genai:
        legacy_genai.configure(api_key=settings.GEMINI_API_KEY)
        model = legacy_genai.GenerativeModel(MODEL_NAME)
        return model.generate_content(prompt)

    raise ImportError("Install google-genai or google-generativeai to use Gemini.")

def ask_gemini(prompt):
    try:
        response = generate_content(prompt)

        print(response)

        return response.text

    except Exception as e:
        print("GEMINI ERROR:", e)
        raise
