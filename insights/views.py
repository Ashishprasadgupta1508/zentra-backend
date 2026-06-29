from rest_framework.views import APIView
from rest_framework.response import Response
import traceback

from notes.models import ChatHistory, Note
from notes.services.gemini import ask_gemini
from notes.views import get_or_create_request_user
from users.permissions import FirebaseAuthenticated


def get_chat_message(data):
    if isinstance(data, str):
        return data.strip()

    if not hasattr(data, "get"):
        return ""

    for key in (
        "message",
        "prompt",
        "question",
        "query",
        "text",
        "input",
        "content",
        "user_message",
        "userMessage",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = data.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue

            content = item.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

    return ""


class ChatView(APIView):
    permission_classes = [FirebaseAuthenticated]

    def post(self, request):

        message = get_chat_message(request.data)
        note_id = request.data.get("note_id")

        if not message:
            return Response(
                {
                    "success": False,
                    "message": "Message is required"
                },
                status=400
            )

        try:
            user = get_or_create_request_user(request.user)
            note = None

            if note_id:
                notes = Note.objects.filter(id=note_id, user=user)
            else:
                notes = Note.objects.filter(user=user).order_by("-created_at")

            if note_id and not notes.exists():
                raise Note.DoesNotExist

            context_parts = []
            for note_obj in notes:
                if note is None:
                    note = note_obj
                if note_obj.extracted_text:
                    context_parts.append(
                        f"Note title: {note_obj.title}\nNote content:\n{note_obj.extracted_text}"
                    )

            context = "\n\n".join(context_parts).strip()

            if not context:
                answer = "I couldn't find this information in your uploaded notes."
            else:
                prompt = f"""
Answer the user's question using only the uploaded note content below.
If the answer is not explicitly available inside the notes, return exactly:
I couldn't find this information in your uploaded notes.

Do not use markdown.
Do not use outside knowledge.

Uploaded notes:
{context}

User question:
{message}
"""

                answer = ask_gemini(prompt).strip()

            ChatHistory.objects.create(
                user=user,
                note=note,
                message=message,
                answer=answer
            )

            return Response({
                "success": True,
                "response": answer,
                "answer": answer,
                "note_id": note_id,
                "notes_only": True
            })

        except Note.DoesNotExist:
            return Response({
                "success": False,
                "error": "Note not found"
            }, status=404)

        except Exception as e:
            traceback.print_exc()

            return Response({
                "success": False,
                "error": str(e)
            }, status=500)
