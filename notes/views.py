from rest_framework.views import APIView
from rest_framework.response import Response
import traceback

from users.models import User
from users.permissions import FirebaseAuthenticated

from .models import Note, Module, Topic
from .services.pdf_parser import extract_text_from_pdf
from .services.module_builder import build_modules


class UploadNoteView(APIView):
    permission_classes = [FirebaseAuthenticated]

    def post(self, request):

        try:

            file = request.FILES.get("file")
            title = request.data.get("title") or getattr(file, "name", "Untitled Note")

            if not file:
                return Response(
                    {
                        "success": False,
                        "error": "PDF required"
                    },
                    status=400
                )

            uid = getattr(request.user, "uid", None)

            if not uid:
                return Response(
                    {
                        "success": False,
                        "error": "User UID not found"
                    },
                    status=401
                )

            try:
                user = User.objects.get(uid=uid)
            except User.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "error": f"User with uid '{uid}' does not exist"
                    },
                    status=404
                )

            note = Note.objects.create(
                user=user,
                title=title,
                uploaded_file=file
            )

            text = extract_text_from_pdf(
                note.uploaded_file.path
            )

            if not text.strip():
                note.delete()
                return Response(
                    {
                        "success": False,
                        "error": "Could not extract text from this PDF"
                    },
                    status=400
                )

            note.extracted_text = text

            ai = build_modules(text)

            for index, module_data in enumerate(ai["modules"], start=1):

                module = Module.objects.create(
                    note=note,
                    title=module_data["title"],
                    description="",
                    order=index
                )

                for topic in module_data["topics"]:

                    Topic.objects.create(
                        module=module,
                        title=topic,
                        difficulty="Medium"
                    )

            note.subject = ai["subject"]
            note.summary = ai["summary"]
            note.save()

            return Response(
                {
                    "success": True,
                    "subject": note.subject,
                    "summary": note.summary,
                    "modules": ai["modules"]
                }
            )

        except Exception as e:
            traceback.print_exc()

            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "type": type(e).__name__,
                },
                status=500,
            )


class NoteDetailView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, note_id):

        try:

            note = Note.objects.get(id=note_id)

            modules_data = []

            modules = Module.objects.filter(note=note)

            for module in modules:

                topics = Topic.objects.filter(module=module)

                modules_data.append({

                    "id": module.id,

                    "title": module.title,

                    "topics": list(
                        topics.values(
                            "id",
                            "title",
                            "difficulty"
                        )
                    )

                })

            return Response({

                "id": note.id,

                "title": note.title,

                "subject": note.subject,

                "summary": note.summary,

                "modules": modules_data

            })

        except Exception as e:

            traceback.print_exc()

            return Response(

                {

                    "success": False,

                    "error": str(e)

                },

                status=500

            )
