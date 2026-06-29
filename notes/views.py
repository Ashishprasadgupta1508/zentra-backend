from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .services.module_builder import build_modules
from .models import Note, Module, Topic

from .serializers import NoteSerializer

from .services.pdf_parser import extract_text_from_pdf

from users.models import User
import traceback


class UploadNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:
            print("REQUEST DATA:", request.data)
            print("FILES:", request.FILES)
            print("AUTH USER:", request.user)

            title = request.data.get("title")
            file = request.FILES.get("file")

            print("REQUEST USER UID:", request.user.uid)

            if not file:
                return Response(
                    {"error": "PDF required"},
                    status=400
                )

            user = User.objects.get(uid=request.user.uid)

            note = Note.objects.create(
                user=user,
                title=title,
                uploaded_file=file
            )

            text = extract_text_from_pdf(note.uploaded_file.path)

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

            return Response({
                "success": True,
                "subject": ai["subject"],
                "summary": ai["summary"],
                "modules": ai["modules"]
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
class NoteDetailView(APIView):

    def get(self, request, note_id):

        note = Note.objects.get(id=note_id)

        data = {

            "id": note.id,

            "title": note.title,

            "subject": note.subject,

            "summary": note.summary,

            "modules": []

        }

        modules = Module.objects.filter(note=note)

        for module in modules:

            data["modules"].append({

                "id": module.id,

                "title": module.title,

                "topics": list(

                    Topic.objects.filter(

                        module=module

                    ).values(

                        "id",

                        "title",

                        "difficulty"

                    )

                )

            })

        return Response(data)
