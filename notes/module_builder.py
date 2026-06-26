import json

from .gemini import ask_gemini

from .prompts import MODULE_PROMPT


def build_modules(text):

    prompt = MODULE_PROMPT + text

    response = ask_gemini(prompt)

    return json.loads(response)