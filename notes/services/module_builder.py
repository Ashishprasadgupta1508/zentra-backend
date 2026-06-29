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
        "introduction": f"This lecture covers {topic_title} from the uploaded notes.",
        "simple_explanation": f"Review the main idea of {topic_title} using the uploaded notes.",
        "detailed_explanation": f"Study the definitions, steps, examples, and exam points about {topic_title} from the uploaded notes.",
        "explanation": f"Review the main idea of {topic_title} using the uploaded notes.",
        "real_life_examples": [],
        "exam_oriented_examples": [],
        "examples": [],
        "key_points": [topic_title],
        "important_definitions": [],
        "revision_notes": [f"Revise {topic_title} directly from the uploaded notes."],
        "common_mistakes": [],
        "quick_recap": [topic_title],
        "source": "fallback"
    }


def _fallback_test(topic_title):
    return {
        "questions": [
            {
                "question_type": "short_answer",
                "question": f"What do you understand by {topic_title}?",
                "options": [],
                "correct_answer": topic_title,
                "explanation": f"The answer should be based on the uploaded notes for {topic_title}.",
                "difficulty": "Medium"
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
Create a complete educational lecture for the topic below using only the uploaded notes.
Return only valid JSON. No markdown.
Use text only.
Do not invent facts that are not supported by the uploaded notes.
Do not return a single paragraph.

Return exactly:
{{
  "title": "",
  "introduction": "",
  "simple_explanation": "",
  "detailed_explanation": "",
  "real_life_examples": ["", ""],
  "exam_oriented_examples": ["", ""],
  "key_points": ["", ""],
  "important_definitions": ["", ""],
  "revision_notes": ["", ""],
  "common_mistakes": ["", ""],
  "quick_recap": ["", ""]
}}

Content requirements:
- introduction: 2-4 sentences.
- simple_explanation: explain plainly for a beginner.
- detailed_explanation: deeper explanation with logical sections in paragraph form.
- real_life_examples: practical examples from or clearly grounded in the notes.
- exam_oriented_examples: exam-style examples or likely question patterns from the notes.
- key_points, important_definitions, revision_notes, common_mistakes, quick_recap: concise lists.

Topic:
{topic_title}

Uploaded notes:
{note_text}
"""

    try:
        data = _extract_json(ask_gemini(prompt))
        if isinstance(data, dict) and (
            data.get("simple_explanation") or data.get("detailed_explanation")
        ):
            data["source"] = "gemini"
            data.setdefault("title", topic_title)
            data.setdefault("introduction", "")
            data.setdefault("simple_explanation", data.get("explanation", ""))
            data.setdefault("detailed_explanation", "")
            data.setdefault("real_life_examples", [])
            data.setdefault("exam_oriented_examples", [])
            data["examples"] = (
                data.get("examples")
                or data.get("real_life_examples", []) + data.get("exam_oriented_examples", [])
            )
            data.setdefault("examples", [])
            data.setdefault("key_points", [])
            data.setdefault("important_definitions", [])
            data.setdefault("revision_notes", [])
            data.setdefault("common_mistakes", [])
            data.setdefault("quick_recap", [])
            return data
    except Exception as e:
        print("LECTURE BUILDER ERROR:", e)

    return _fallback_lecture(topic_title)


def build_test(note_text, topic_title):
    prompt = f"""
Generate a test for the topic below using only the uploaded notes.
Return only valid JSON. No markdown.
Include MCQ, short answer, and true false questions where possible.
Do not invent facts outside the uploaded notes.

Return exactly:
{{
  "questions": [
    {{
      "question_type": "mcq | short_answer | true_false",
      "question": "",
      "options": ["", "", "", ""],
      "correct_answer": "",
      "explanation": "",
      "difficulty": "Easy | Medium | Hard"
    }}
  ]
}}

Question requirements:
- Generate 20 questions when enough note content exists.
- Include a mix of MCQ, true_false, and short_answer.
- Every question must include answer, explanation, and difficulty.
- For true_false questions, options must be ["True", "False"].

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
