from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import traceback

from users.models import User

from .models import Note, Module, Topic
from .services.pdf_parser import extract_text_from_pdf
from .services.module_builder import build_modules


class UploadNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:

            print("=" * 60)
            print("UPLOAD REQUEST")
            print("=" * 60)

            print("REQUEST DATA:", request.data)
            print("FILES:", request.FILES)
            print("AUTH USER:", request.user)
            print("AUTH USER TYPE:", type(request.user))
            print("AUTH UID:", getattr(request.user, "uid", None))

            title = request.data.get("title")
            file = request.FILES.get("file")

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

            print("Looking for user:", uid)

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

            print("User Found:", user.email)

            note = Note.objects.create(
                user=user,
                title=title,
                uploaded_file=file
            )

            print("Note Created:", note.id)

            text = extract_text_from_pdf(
                note.uploaded_file.path
            )

            print("PDF Extracted")
            print("Characters:", len(text))

            note.extracted_text = text

            ai = build_modules(text)

            ai = {
                "subject": "Test Subject",
                "summary": "Test Summary",
                "modules": [
                    {
                        "title": "Module 1",
                        "topics": [
                            "Topic 1",
                            "Topic 2"
                        ]
                    }
                ]
            }

            print("AI Response:")
            print(ai)

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

            print("SUCCESS")
            print("=" * 60)

            return Response(
                {
                    "success": True,
                    "subject": note.subject,
                    "summary": note.summary,
                    "modules": ai["modules"]
                }
            )

        except Exception as e:
            import traceback

            print("=" * 60)
            print("UPLOAD ERROR")
            traceback.print_exc()
            print("=" * 60)

            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "type": type(e).__name__,
                },
                status=500,
            )


class NoteDetailView(APIView):

    permission_classes = [IsAuthenticated]

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