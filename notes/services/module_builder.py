import json

from .gemini import ask_gemini

from .prompts import MODULE_PROMPT


def build_modules(text):

    prompt = MODULE_PROMPT + text

    result = ask_gemini(prompt)

    # Gemini sometimes wraps JSON in ```json ... ```
    cleaned = (
        result.replace("```json", "")
              .replace("```", "")
              .strip()
    )

    return json.loads(cleaned)