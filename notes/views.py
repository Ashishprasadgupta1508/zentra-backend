from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.module_builder import build_modules

from .models import Note
from .serializers import NoteSerializer

from .services.pdf_parser import extract_text_from_pdf

from users.models import User


class UploadNoteView(APIView):

    def post(self, request):

        uid = request.data.get("uid")

        title = request.data.get("title")

        file = request.FILES.get("file")

        if not file:

            return Response(
                {
                    "error": "PDF required"
                },
                status=400
            )

        user = User.objects.get(uid=uid)

        note = Note.objects.create(

            user=user,

            title=title,

            uploaded_file=file

        )

        text = extract_text_from_pdf(
            note.uploaded_file.path
        )

        note.extracted_text = text

        ai = build_modules(text)

        note.subject = ai["subject"]

        note.summary = ai["summary"]

        note.save()

        return Response({

            "success": True,

            "subject": ai["subject"],

            "summary": ai["summary"],

            "modules": ai["modules"]

        })