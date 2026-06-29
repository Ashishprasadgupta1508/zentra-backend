from rest_framework.views import APIView
from rest_framework.response import Response
import traceback

from users.models import User
from users.permissions import FirebaseAuthenticated

from .models import Note, Module, Topic
from .services.pdf_parser import extract_text_from_pdf
from .services.module_builder import build_modules


def build_note_file_data(request, note):
    return {
        "file_name": note.uploaded_file.name.split("/")[-1],
        "file_path": note.uploaded_file.name,
        "file_url": request.build_absolute_uri(note.uploaded_file.url),
    }


def get_or_create_request_user(firebase_user):
    return User.objects.get_or_create(
        uid=firebase_user.uid,
        defaults={
            "email": firebase_user.email or f"{firebase_user.uid}@firebase.local",
            "name": firebase_user.display_name or "",
            "photo_url": firebase_user.photo_url,
            "email_verified": firebase_user.email_verified,
        }
    )[0]


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

            user = get_or_create_request_user(request.user)

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
                topics = module_data.get("topics") or []

                module = Module.objects.create(
                    note=note,
                    title=module_data.get("title") or f"Module {index}",
                    description="",
                    order=index
                )

                for topic in topics:
                    topic_title = topic.get("title") if isinstance(topic, dict) else topic
                    if not topic_title:
                        continue

                    Topic.objects.create(
                        module=module,
                        title=topic_title,
                        difficulty="Medium"
                    )

            note.subject = ai["subject"]
            note.summary = ai["summary"]
            note.save()

            analysis = {
                "source": ai.get("source", "gemini"),
                "subject": note.subject,
                "summary": note.summary,
                "modules": ai["modules"],
            }
            uploaded_file = build_note_file_data(request, note)

            return Response(
                {
                    "success": True,
                    "note_id": note.id,
                    "title": note.title,
                    "uploaded_file": uploaded_file,
                    "analysis": analysis,
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


class NoteListView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request):

        try:
            user = get_or_create_request_user(request.user)
            notes = Note.objects.filter(user=user).order_by("-created_at")

            data = []

            for note in notes:
                data.append({
                    "id": note.id,
                    "title": note.title,
                    "subject": note.subject,
                    "summary": note.summary,
                    "uploaded_file": build_note_file_data(request, note),
                    "created_at": note.created_at,
                })

            return Response({
                "success": True,
                "notes": data
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

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, note_id):

        try:

            user = get_or_create_request_user(request.user)
            note = Note.objects.get(id=note_id, user=user)

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

            analysis = {
                "subject": note.subject,
                "summary": note.summary,
                "modules": modules_data
            }
            uploaded_file = build_note_file_data(request, note)

            return Response({

                "success": True,

                "id": note.id,

                "title": note.title,

                "uploaded_file": uploaded_file,

                "analysis": analysis,

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
