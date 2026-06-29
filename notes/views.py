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
    Progress,
    Task,
    Test,
    TestQuestion,
    TestSubmission,
    Topic,
)
from .services.pdf_parser import extract_text_from_pdf
from .services.module_builder import build_lecture, build_modules, build_test


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
            "topic": task.topic.title if task.topic else "",
            "estimated_time": task.estimated_time,
            "task_type": task.task_type,
            "order": task.order,
            "locked": task.locked,
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
            "topic_id": lecture.topic_id,
            "title": lecture.title,
            "content": lecture.content,
            "explanation": lecture.explanation,
            "examples": lecture.examples,
            "key_points": lecture.key_points,
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
                    "question_type": question.question_type,
                    "question": question.question,
                    "options": question.options,
                    "order": question.order,
                }
                for question in questions
            ]
        })

    return data


def ordered_topics_for_note(note):
    return Topic.objects.filter(module__note=note).select_related("module").order_by(
        "module__order",
        "order",
        "id"
    )


def get_topic_note(topic):
    return topic.module.note


def serialize_modules(note):
    modules_data = []
    modules = Module.objects.filter(note=note).order_by("order", "id")

    for module in modules:
        topics = Topic.objects.filter(module=module).order_by("order", "id")
        modules_data.append({
            "id": module.id,
            "title": module.title,
            "description": module.description,
            "order": module.order,
            "topics": [
                {
                    "id": topic.id,
                    "title": topic.title,
                    "order": topic.order,
                    "difficulty": topic.difficulty,
                    "locked": topic.locked,
                    "lecture_completed": topic.lecture_completed,
                    "test_completed": topic.test_completed,
                }
                for topic in topics
            ]
        })

    return modules_data


def unlock_next_task(note):
    next_task = Task.objects.filter(note=note, completed=False).order_by("order", "id").first()
    if next_task and next_task.locked:
        next_task.locked = False
        next_task.save(update_fields=["locked"])


def unlock_next_topic(user, current_topic):
    note = get_topic_note(current_topic)
    topics = list(ordered_topics_for_note(note))

    for index, topic in enumerate(topics):
        if topic.id != current_topic.id:
            continue

        if index + 1 >= len(topics):
            return None

        next_topic = topics[index + 1]
        if next_topic.locked:
            next_topic.locked = False
            next_topic.save(update_fields=["locked"])

        Progress.objects.update_or_create(
            user=user,
            note=note,
            topic=next_topic,
            defaults={
                "unlocked": True,
                "lecture_completed": next_topic.lecture_completed,
                "test_completed": next_topic.test_completed,
            }
        )
        return next_topic

    return None


def ensure_progress_rows(user, note):
    for topic in ordered_topics_for_note(note):
        Progress.objects.update_or_create(
            user=user,
            note=note,
            topic=topic,
            defaults={
                "unlocked": not topic.locked,
                "lecture_completed": topic.lecture_completed,
                "test_completed": topic.test_completed,
            }
        )


def serialize_progress(user):
    rows = Progress.objects.filter(user=user).select_related(
        "note",
        "topic",
        "topic__module"
    ).order_by("-note__created_at", "topic__module__order", "topic__order", "topic_id")

    return [
        {
            "note_id": row.note_id,
            "note_title": row.note.title,
            "topic_id": row.topic_id,
            "topic_title": row.topic.title if row.topic else "",
            "module_id": row.topic.module_id if row.topic else None,
            "lecture_completed": row.lecture_completed,
            "test_completed": row.test_completed,
            "unlocked": row.unlocked,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


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
                module_title = module_data.get("title") or f"Module {index}"

                module = Module.objects.create(
                    note=note,
                    title=module_title,
                    description=module_data.get("description", ""),
                    order=module_data.get("order") or index
                )

                for topic_index, topic in enumerate(topics, start=1):
                    topic_title = topic.get("title") if isinstance(topic, dict) else topic
                    if not topic_title:
                        continue

                    topic_order = topic.get("order") if isinstance(topic, dict) else topic_index
                    topic_difficulty = (
                        topic.get("difficulty") if isinstance(topic, dict) else None
                    ) or ai.get("difficulty") or "Medium"

                    Topic.objects.create(
                        module=module,
                        title=str(topic_title),
                        order=topic_order or topic_index,
                        difficulty=topic_difficulty,
                        locked=True
                    )

            for index, topic in enumerate(ordered_topics_for_note(note), start=1):
                unlocked = index == 1
                if unlocked:
                    topic.locked = False
                    topic.save(update_fields=["locked"])

                Task.objects.create(
                    note=note,
                    topic=topic,
                    title=f"Study {topic.title}",
                    estimated_time=ai.get("estimated_time", ""),
                    task_type="lecture",
                    order=index,
                    locked=not unlocked,
                    description=f"Read the lecture and complete the test for {topic.title}."
                )

            note.subject = ai["subject"]
            note.summary = ai["summary"]
            note.difficulty = ai.get("difficulty", "Medium")
            note.estimated_time = ai.get("estimated_time", "")
            note.learning_plan = ai.get("learning_plan", [])
            note.save()
            ensure_progress_rows(user, note)

            analysis = {
                "source": ai.get("source", "gemini"),
                "subject": note.subject,
                "summary": note.summary,
                "difficulty": note.difficulty,
                "estimated_time": note.estimated_time,
                "learning_plan": note.learning_plan,
                "modules": serialize_modules(note),
            }
            uploaded_file = build_note_file_data(request, note)
            tasks = serialize_tasks(Task.objects.filter(note=note).order_by("order", "id"))

            return Response(
                {
                    "success": True,
                    "note_id": note.id,
                    "title": note.title,
                    "uploaded_file": uploaded_file,
                    "analysis": analysis,
                    "subject": note.subject,
                    "summary": note.summary,
                    "difficulty": note.difficulty,
                    "estimated_time": note.estimated_time,
                    "learning_plan": note.learning_plan,
                    "modules": analysis["modules"],
                    "tasks": tasks,
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
                    "difficulty": note.difficulty,
                    "estimated_time": note.estimated_time,
                    "learning_plan": note.learning_plan,
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

            ensure_progress_rows(user, note)
            modules_data = serialize_modules(note)

            analysis = {
                "subject": note.subject,
                "summary": note.summary,
                "difficulty": note.difficulty,
                "estimated_time": note.estimated_time,
                "learning_plan": note.learning_plan,
                "modules": modules_data
            }
            uploaded_file = build_note_file_data(request, note)
            tasks = serialize_tasks(Task.objects.filter(note=note).order_by("order", "id"))
            lectures = serialize_lectures(Lecture.objects.filter(note=note).order_by("order", "id"))
            tests = serialize_tests(Test.objects.filter(note=note).order_by("id"))

            return Response({

                "success": True,

                "id": note.id,

                "title": note.title,

                "uploaded_file": uploaded_file,

                "analysis": analysis,

                "subject": note.subject,

                "summary": note.summary,

                "difficulty": note.difficulty,

                "estimated_time": note.estimated_time,

                "learning_plan": note.learning_plan,

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

            if task.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Task is locked"
                    },
                    status=403
                )

            task.completed = True
            task.completed_at = timezone.now()
            task.save()
            unlock_next_task(task.note)

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


class TaskListView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, note_id):

        try:
            user = get_or_create_request_user(request.user)
            note = Note.objects.get(id=note_id, user=user)
            tasks = Task.objects.filter(note=note).order_by("order", "id")

            return Response({
                "success": True,
                "note_id": note.id,
                "tasks": serialize_tasks(tasks)
            })

        except Note.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Note not found"
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


class LectureView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, topic_id):

        try:
            user = get_or_create_request_user(request.user)
            topic = Topic.objects.select_related("module", "module__note").get(
                id=topic_id,
                module__note__user=user
            )
            note = get_topic_note(topic)

            if topic.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Topic is locked"
                    },
                    status=403
                )

            lecture = getattr(topic, "lecture", None)

            if not lecture:
                lecture_data = build_lecture(note.extracted_text, topic.title)
                lecture = Lecture.objects.create(
                    note=note,
                    topic=topic,
                    title=lecture_data.get("title") or topic.title,
                    content=lecture_data.get("explanation", ""),
                    explanation=lecture_data.get("explanation", ""),
                    examples=lecture_data.get("examples", []),
                    key_points=lecture_data.get("key_points", []),
                    order=topic.order
                )

            if not topic.lecture_completed:
                topic.lecture_completed = True
                topic.save(update_fields=["lecture_completed"])

            Progress.objects.update_or_create(
                user=user,
                note=note,
                topic=topic,
                defaults={
                    "unlocked": True,
                    "lecture_completed": True,
                    "test_completed": topic.test_completed,
                }
            )

            return Response({
                "success": True,
                "topic_id": topic.id,
                "lecture": {
                    "id": lecture.id,
                    "title": lecture.title,
                    "explanation": lecture.explanation or lecture.content,
                    "examples": lecture.examples,
                    "key_points": lecture.key_points,
                }
            })

        except Topic.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Topic not found"
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


class TopicTestView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, topic_id):

        try:
            user = get_or_create_request_user(request.user)
            topic = Topic.objects.select_related("module", "module__note").get(
                id=topic_id,
                module__note__user=user
            )
            note = get_topic_note(topic)

            if topic.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Topic is locked"
                    },
                    status=403
                )

            if not topic.lecture_completed:
                return Response(
                    {
                        "success": False,
                        "error": "Complete the lecture before opening the test"
                    },
                    status=403
                )

            test = getattr(topic, "test", None)

            if not test:
                test_data = build_test(note.extracted_text, topic.title)
                test = Test.objects.create(
                    note=note,
                    topic=topic,
                    title=f"{topic.title} Test",
                    instructions="Answer using only your uploaded notes."
                )

                for index, question_data in enumerate(test_data.get("questions", []), start=1):
                    correct_answer = question_data.get("correct_answer", "")
                    TestQuestion.objects.create(
                        test=test,
                        question=question_data.get("question", ""),
                        question_type=question_data.get("question_type", "short_answer"),
                        answer=correct_answer,
                        correct_answer=correct_answer,
                        options=question_data.get("options", []),
                        order=index
                    )

            questions = TestQuestion.objects.filter(test=test).order_by("order", "id")

            return Response({
                "success": True,
                "topic_id": topic.id,
                "test_id": test.id,
                "questions": [
                    {
                        "id": question.id,
                        "question_type": question.question_type,
                        "question": question.question,
                        "options": question.options,
                        "order": question.order,
                    }
                    for question in questions
                ]
            })

        except Topic.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Topic not found"
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


class SubmitTopicTestView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def post(self, request, topic_id):

        try:
            user = get_or_create_request_user(request.user)
            topic = Topic.objects.select_related("module", "module__note").get(
                id=topic_id,
                module__note__user=user
            )
            note = get_topic_note(topic)

            if topic.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Topic is locked"
                    },
                    status=403
                )

            if not topic.lecture_completed:
                return Response(
                    {
                        "success": False,
                        "error": "Complete the lecture before submitting the test"
                    },
                    status=403
                )

            test = getattr(topic, "test", None)
            if not test:
                return Response(
                    {
                        "success": False,
                        "error": "Generate the test before submitting answers"
                    },
                    status=400
                )

            answers = request.data.get("answers") or {}
            questions = TestQuestion.objects.filter(test=test).order_by("order", "id")
            total = questions.count()
            correct_answers = []
            wrong_answers = []

            for question in questions:
                submitted = answers.get(str(question.id), answers.get(question.id, ""))
                expected = question.correct_answer or question.answer
                is_correct = str(submitted).strip().lower() == expected.strip().lower()
                row = {
                    "question_id": question.id,
                    "question": question.question,
                    "submitted_answer": submitted,
                    "correct_answer": expected,
                }

                if is_correct:
                    correct_answers.append(row)
                else:
                    wrong_answers.append(row)

            score = len(correct_answers)
            accuracy = round((score / total) * 100, 2) if total else 0

            submission = TestSubmission.objects.create(
                test=test,
                user=user,
                answers=answers,
                score=score,
                total=total,
                feedback=f"You scored {score}/{total}."
            )

            topic.test_completed = True
            topic.save(update_fields=["test_completed"])

            next_topic = unlock_next_topic(user, topic)
            unlock_next_task(note)
            Progress.objects.update_or_create(
                user=user,
                note=note,
                topic=topic,
                defaults={
                    "unlocked": True,
                    "lecture_completed": topic.lecture_completed,
                    "test_completed": True,
                }
            )

            return Response({
                "success": True,
                "submission_id": submission.id,
                "score": score,
                "accuracy": accuracy,
                "correct_answers": correct_answers,
                "wrong_answers": wrong_answers,
                "weak_topics": [topic.title] if wrong_answers else [],
                "next_topic_id": next_topic.id if next_topic else None,
            })

        except Topic.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Topic not found"
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


class ProgressView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request):

        try:
            user = get_or_create_request_user(request.user)

            for note in Note.objects.filter(user=user):
                ensure_progress_rows(user, note)

            return Response({
                "success": True,
                "progress": serialize_progress(user)
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
