from rest_framework.views import APIView
from rest_framework.response import Response
import traceback

from notes.models import Note
from notes.services.gemini import ask_gemini
from notes.views import get_or_create_request_user
from users.permissions import FirebaseAuthenticated


class ChatView(APIView):
    permission_classes = [FirebaseAuthenticated]

    def post(self, request):

        message = request.data.get("message")
        note_id = request.data.get("note_id")
        notes_only = request.data.get("notes_only", False)
        notes_only = notes_only is True or str(notes_only).lower() == "true"

        if not message:
            return Response(
                {
                    "success": False,
                    "message": "Message is required"
                },
                status=400
            )

        try:
            prompt = message

            if notes_only:
                if not note_id:
                    return Response(
                        {
                            "success": False,
                            "message": "note_id is required when notes_only is true"
                        },
                        status=400
                    )

                user = get_or_create_request_user(request.user)
                note = Note.objects.get(id=note_id, user=user)

                prompt = f"""
Answer the user's question using only the uploaded note content below.
If the answer is not present in the notes, say that it is not available in the uploaded notes.

Uploaded note title: {note.title}

Uploaded note content:
{note.extracted_text}

User question:
{message}
"""

            answer = ask_gemini(prompt)

            return Response({
                "success": True,
                "response": answer,
                "answer": answer,
                "note_id": note_id,
                "notes_only": notes_only
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
