import json

from .gemini import ask_gemini
from .prompts import MODULE_PROMPT


def build_modules(text):

    prompt = MODULE_PROMPT + text

    response = ask_gemini(prompt)

    print("RAW GEMINI RESPONSE:")
    print(response)

    response = response.replace("```json", "")
    response = response.replace("```", "")
    response = response.strip()

    try:
        return json.loads(response)

    except Exception as e:

        print("JSON ERROR:", e)

        print("RAW RESPONSE:")
        print(response)

        raise