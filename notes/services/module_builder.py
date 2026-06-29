import json

from .gemini import ask_gemini

from .prompts import MODULE_PROMPT


def _fallback_modules(text):
    summary = " ".join(text.split())[:500]

    return {
        "source": "fallback",
        "subject": "Study Notes",
        "summary": summary or "Uploaded study material.",
        "modules": [
            {
                "title": "Overview",
                "topics": [
                    "Key concepts",
                    "Important points",
                    "Revision notes"
                ]
            }
        ]
    }


def _extract_json(response):
    cleaned = (
        response.replace("```json", "")
                .replace("```", "")
                .strip()
    )

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


def _is_valid_modules(data):
    return (
        isinstance(data, dict)
        and isinstance(data.get("subject"), str)
        and isinstance(data.get("summary"), str)
        and isinstance(data.get("modules"), list)
        and data["modules"]
    )


def build_modules(text):

    prompt = MODULE_PROMPT + text

    try:
        result = ask_gemini(prompt)
        data = _extract_json(result)

        if _is_valid_modules(data):
            data["source"] = "gemini"
            return data

    except Exception as e:
        print("MODULE BUILDER ERROR:", e)

    return _fallback_modules(text)
