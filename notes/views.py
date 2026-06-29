from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
import traceback

from users.models import User
from users.permissions import FirebaseAuthenticated

from .models import (
    Lecture,
    Module,
    Note,
    Task,
    Test,
    TestQuestion,
    TestSubmission,
    Topic,
)
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


def serialize_tasks(tasks):
    return [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
        }
        for task in tasks
    ]


def serialize_lectures(lectures):
    return [
        {
            "id": lecture.id,
            "title": lecture.title,
            "content": lecture.content,
            "order": lecture.order,
            "created_at": lecture.created_at,
        }
        for lecture in lectures
    ]


def serialize_tests(tests):
    data = []

    for test in tests:
        questions = TestQuestion.objects.filter(test=test).order_by("order")
        data.append({
            "id": test.id,
            "title": test.title,
            "instructions": test.instructions,
            "created_at": test.created_at,
            "questions": [
                {
                    "id": question.id,
                    "question": question.question,
                    "options": question.options,
                    "order": question.order,
                }
                for question in questions
            ]
        })

    return data


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
            topic_titles = []

            for index, module_data in enumerate(ai["modules"], start=1):
                topics = module_data.get("topics") or []
                module_title = module_data.get("title") or f"Module {index}"

                module = Module.objects.create(
                    note=note,
                    title=module_title,
                    description="",
                    order=index
                )

                Lecture.objects.create(
                    note=note,
                    title=module_title,
                    content="Study this lecture from the uploaded notes: "
                    + ", ".join(
                        str(topic.get("title") if isinstance(topic, dict) else topic)
                        for topic in topics
                    ),
                    order=index
                )

                for topic in topics:
                    topic_title = topic.get("title") if isinstance(topic, dict) else topic
                    if not topic_title:
                        continue

                    topic_titles.append(str(topic_title))

                    Topic.objects.create(
                        module=module,
                        title=topic_title,
                        difficulty="Medium"
                    )

            for topic_title in topic_titles:
                Task.objects.create(
                    note=note,
                    title=f"Review {topic_title}",
                    description=f"Revise and understand {topic_title} from the uploaded PDF."
                )

            test = Test.objects.create(
                note=note,
                title=f"{note.title} Test",
                instructions="Answer these questions using your uploaded notes."
            )

            for index, topic_title in enumerate(topic_titles[:10], start=1):
                TestQuestion.objects.create(
                    test=test,
                    question=f"What do you understand by {topic_title}?",
                    answer=topic_title,
                    order=index
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
            tasks = serialize_tasks(Task.objects.filter(note=note).order_by("id"))
            lectures = serialize_lectures(Lecture.objects.filter(note=note).order_by("order"))
            tests = serialize_tests(Test.objects.filter(note=note).order_by("id"))

            return Response(
                {
                    "success": True,
                    "note_id": note.id,
                    "title": note.title,
                    "uploaded_file": uploaded_file,
                    "analysis": analysis,
                    "subject": note.subject,
                    "summary": note.summary,
                    "modules": ai["modules"],
                    "tasks": tasks,
                    "lectures": lectures,
                    "tests": tests,
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
                    "tasks_count": Task.objects.filter(note=note).count(),
                    "lectures_count": Lecture.objects.filter(note=note).count(),
                    "tests_count": Test.objects.filter(note=note).count(),
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
            tasks = serialize_tasks(Task.objects.filter(note=note).order_by("id"))
            lectures = serialize_lectures(Lecture.objects.filter(note=note).order_by("order"))
            tests = serialize_tests(Test.objects.filter(note=note).order_by("id"))

            return Response({

                "success": True,

                "id": note.id,

                "title": note.title,

                "uploaded_file": uploaded_file,

                "analysis": analysis,

                "subject": note.subject,

                "summary": note.summary,

                "modules": modules_data,

                "tasks": tasks,

                "lectures": lectures,

                "tests": tests

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


class CompleteTaskView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def post(self, request, task_id):

        try:
            user = get_or_create_request_user(request.user)
            task = Task.objects.get(id=task_id, note__user=user)
            task.completed = True
            task.completed_at = timezone.now()
            task.save()

            return Response({
                "success": True,
                "task": serialize_tasks([task])[0]
            })

        except Task.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Task not found"
                },
                status=404
            )

        except Exception as e:
            traceback.print_exc()

            return Response(
                {
                    "success": False,
                    "error": str(e)
                },
                status=500
            )


class SubmitTestView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def post(self, request, test_id):

        try:
            user = get_or_create_request_user(request.user)
            test = Test.objects.get(id=test_id, note__user=user)
            answers = request.data.get("answers") or {}
            questions = TestQuestion.objects.filter(test=test)
            total = questions.count()
            score = 0

            for question in questions:
                submitted = answers.get(str(question.id), answers.get(question.id, ""))
                if str(submitted).strip().lower() == question.answer.strip().lower():
                    score += 1

            submission = TestSubmission.objects.create(
                test=test,
                user=user,
                answers=answers,
                score=score,
                total=total,
                feedback=f"You scored {score}/{total}."
            )

            return Response({
                "success": True,
                "submission_id": submission.id,
                "score": score,
                "total": total,
                "feedback": submission.feedback
            })

        except Test.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Test not found"
                },
                status=404
            )

        except Exception as e:
            traceback.print_exc()

            return Response(
                {
                    "success": False,
                    "error": str(e)
                },
                status=500
            )
