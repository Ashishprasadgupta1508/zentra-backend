import json

from .gemini import ask_gemini


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


def _fallback_analysis(text):
    summary = " ".join(text.split())[:500]

    return {
        "subject": "Study Notes",
        "summary": summary or "Uploaded study material.",
        "difficulty": "Medium",
        "estimated_time": "30 minutes",
        "learning_plan": [
            "Read the uploaded notes",
            "Review each topic in order",
            "Complete the topic tests"
        ],
        "modules": [
            {
                "title": "Overview",
                "order": 1,
                "topics": [
                    {
                        "title": "Key concepts",
                        "order": 1,
                        "difficulty": "Medium"
                    }
                ]
            }
        ],
        "source": "fallback"
    }


def _fallback_lecture(topic_title):
    return {
        "title": topic_title,
        "explanation": f"Review {topic_title} using the uploaded notes.",
        "examples": [],
        "key_points": [topic_title],
        "source": "fallback"
    }


def _fallback_test(topic_title):
    return {
        "questions": [
            {
                "question_type": "short_answer",
                "question": f"What do you understand by {topic_title}?",
                "options": [],
                "correct_answer": topic_title
            }
        ],
        "source": "fallback"
    }


def build_modules(text):
    prompt = f"""
You are an expert AI teacher.

Analyze the uploaded study material and return only valid JSON.
Do not use markdown.
Do not include explanations outside JSON.
Only use the uploaded study material as the knowledge source.

Return exactly this shape:
{{
  "subject": "",
  "summary": "",
  "difficulty": "Easy | Medium | Hard",
  "estimated_time": "",
  "learning_plan": ["", ""],
  "modules": [
    {{
      "title": "",
      "order": 1,
      "topics": [
        {{
          "title": "",
          "order": 1,
          "difficulty": "Easy | Medium | Hard"
        }}
      ]
    }}
  ]
}}

Uploaded study material:
{text}
"""

    try:
        data = _extract_json(ask_gemini(prompt))
        if isinstance(data, dict) and data.get("modules"):
            data["source"] = "gemini"
            data.setdefault("difficulty", "Medium")
            data.setdefault("estimated_time", "30 minutes")
            data.setdefault("learning_plan", [])
            return data
    except Exception as e:
        print("MODULE BUILDER ERROR:", e)

    return _fallback_analysis(text)


def build_lecture(note_text, topic_title):
    prompt = f"""
Create a lecture for the topic below using only the uploaded notes.
Return only valid JSON. No markdown.
Use text only.

Return exactly:
{{
  "title": "",
  "explanation": "",
  "examples": ["", ""],
  "key_points": ["", ""]
}}

Topic:
{topic_title}

Uploaded notes:
{note_text}
"""

    try:
        data = _extract_json(ask_gemini(prompt))
        if isinstance(data, dict) and data.get("explanation"):
            data["source"] = "gemini"
            data.setdefault("title", topic_title)
            data.setdefault("examples", [])
            data.setdefault("key_points", [])
            return data
    except Exception as e:
        print("LECTURE BUILDER ERROR:", e)

    return _fallback_lecture(topic_title)


def build_test(note_text, topic_title):
    prompt = f"""
Generate a test for the topic below using only the uploaded notes.
Return only valid JSON. No markdown.
Include MCQ, short answer, and true false questions where possible.

Return exactly:
{{
  "questions": [
    {{
      "question_type": "mcq | short_answer | true_false",
      "question": "",
      "options": ["", "", "", ""],
      "correct_answer": ""
    }}
  ]
}}

Topic:
{topic_title}

Uploaded notes:
{note_text}
"""

    try:
        data = _extract_json(ask_gemini(prompt))
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            data["source"] = "gemini"
            return data
    except Exception as e:
        print("TEST BUILDER ERROR:", e)

    return _fallback_test(topic_title)
