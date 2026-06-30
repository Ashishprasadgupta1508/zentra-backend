from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
import traceback

from users.models import User
from users.permissions import FirebaseAuthenticated

from .models import (
    LearningProgress,
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
            "note_id": task.note_id,
            "topic_id": task.topic_id,
            "title": task.title,
            "topic": task.topic.title if task.topic else "",
            "estimated_time": task.estimated_time,
            "task_type": task.task_type,
            "order": task.order,
            "locked": task.locked,
            "status": task.status,
            "description": task.description,
            "completed": task.completed,
            "started_at": task.started_at,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
            "study_time_seconds": task.study_time_seconds,
        }
        for task in tasks
    ]


def serialize_lectures(lectures):
    return [
        serialize_lecture_detail(lecture)
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
                    "answer": question.correct_answer or question.answer,
                    "explanation": question.explanation,
                    "difficulty": question.difficulty,
                    "order": question.order,
                }
                for question in questions
            ]
        })

    return data


def serialize_test_questions(test):
    return [
        {
            "id": question.id,
            "question_type": question.question_type,
            "question": question.question,
            "options": question.options,
            "answer": question.correct_answer or question.answer,
            "explanation": question.explanation,
            "difficulty": question.difficulty,
            "order": question.order,
        }
        for question in TestQuestion.objects.filter(test=test).order_by("order", "id")
    ]


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
            "completed": module.completed,
            "completed_at": module.completed_at,
            "topics": [
                {
                    "id": topic.id,
                    "title": topic.title,
                    "order": topic.order,
                    "difficulty": topic.difficulty,
                    "locked": topic.locked,
                    "lecture_completed": topic.lecture_completed,
                    "test_completed": topic.test_completed,
                    "completed": topic.completed,
                    "completed_at": topic.completed_at,
                }
                for topic in topics
            ]
        })

    return modules_data


def sync_task_status(task):
    if task.completed:
        task.status = Task.STATUS_COMPLETED
        task.locked = False
    elif task.locked:
        task.status = Task.STATUS_LOCKED
    elif task.started_at:
        task.status = Task.STATUS_IN_PROGRESS
    else:
        task.status = Task.STATUS_UNLOCKED


def sync_note_tasks(note):
    first_topic = ordered_topics_for_note(note).first()
    if first_topic and first_topic.locked:
        has_unlocked_topic = Topic.objects.filter(
            module__note=note,
            locked=False
        ).exists()
        if not has_unlocked_topic:
            first_topic.locked = False
            first_topic.save(update_fields=["locked"])

    for index, topic in enumerate(ordered_topics_for_note(note), start=1):
        task = Task.objects.filter(note=note, topic=topic).order_by("order", "id").first()
        if not task:
            task = Task.objects.create(
                note=note,
                topic=topic,
                title=f"Study {topic.title}",
                estimated_time=note.estimated_time,
                task_type="lecture",
                order=index,
                locked=topic.locked,
                status=Task.STATUS_LOCKED if topic.locked else Task.STATUS_UNLOCKED,
                description=f"Read the lecture and complete the test for {topic.title}."
            )

        update_fields = []
        if task.order != index:
            task.order = index
            update_fields.append("order")
        if task.locked != topic.locked and not task.completed:
            task.locked = topic.locked
            update_fields.append("locked")

        old_status = task.status
        sync_task_status(task)
        if task.status != old_status:
            update_fields.append("status")

        if update_fields:
            task.save(update_fields=sorted(set(update_fields)))


def unlock_task(task):
    task.locked = False
    if task.status == Task.STATUS_LOCKED:
        task.status = Task.STATUS_UNLOCKED
    task.save(update_fields=["locked", "status"])


def unlock_next_task_after_pass(note, current_task):
    next_task = Task.objects.filter(
        note=note,
        order__gt=current_task.order,
        completed=False
    ).order_by("order", "id").first()

    if not next_task:
        return None

    if next_task.locked:
        unlock_task(next_task)

    return next_task


def unlock_next_task_after_completion(user, note, current_task):
    next_task = unlock_next_task_after_pass(note, current_task)

    if next_task and next_task.topic and next_task.topic.locked:
        next_task.topic.locked = False
        next_task.topic.save(update_fields=["locked"])

    if next_task and next_task.topic:
        Progress.objects.update_or_create(
            topic=next_task.topic,
            defaults={
                "user": user,
                "note": note,
                "unlocked": True,
                "lecture_completed": next_task.topic.lecture_completed,
                "test_completed": next_task.topic.test_completed,
            }
        )

    return next_task


def unlock_next_task_for_completed_progress(user, note):
    completed_task = Task.objects.filter(
        note=note,
        completed=True
    ).order_by("-order", "-id").first()

    if not completed_task:
        return None

    return unlock_next_task_after_completion(user, note, completed_task)


def get_or_create_topic_task(note, topic, estimated_time=""):
    topic_ids = list(ordered_topics_for_note(note).values_list("id", flat=True))
    order = topic_ids.index(topic.id) + 1 if topic.id in topic_ids else topic.order
    task, _ = Task.objects.get_or_create(
        note=note,
        topic=topic,
        defaults={
            "title": f"Study {topic.title}",
            "estimated_time": estimated_time,
            "task_type": "lecture",
            "order": order,
            "locked": topic.locked,
            "status": Task.STATUS_LOCKED if topic.locked else Task.STATUS_UNLOCKED,
            "description": f"Read the lecture and complete the test for {topic.title}.",
        }
    )
    task.locked = topic.locked
    sync_task_status(task)
    task.save(update_fields=["locked", "status"])
    return task


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


def complete_modules_and_note(note):
    for module in Module.objects.filter(note=note).order_by("order", "id"):
        topics = Topic.objects.filter(module=module)
        completed = topics.exists() and not topics.filter(completed=False).exists()

        if completed and not module.completed:
            module.completed = True
            module.completed_at = timezone.now()
            module.save(update_fields=["completed", "completed_at"])
        elif not completed and module.completed:
            module.completed = False
            module.completed_at = None
            module.save(update_fields=["completed", "completed_at"])

    modules = Module.objects.filter(note=note)
    note_completed = modules.exists() and not modules.filter(completed=False).exists()

    if note_completed and not note.completed:
        note.completed = True
        note.completed_at = timezone.now()
        note.save(update_fields=["completed", "completed_at"])
    elif not note_completed and note.completed:
        note.completed = False
        note.completed_at = None
        note.save(update_fields=["completed", "completed_at"])


def build_recommendations(progress):
    recommendations = []

    if progress.weak_topics:
        recommendations.append("Review weak topics before continuing.")

    if progress.completed_tests < progress.total_tests:
        recommendations.append("Complete the remaining tests to improve your progress.")

    if progress.completion_percentage >= 100:
        recommendations.append("All modules are complete. Revisit weak topics for mastery.")

    if not recommendations:
        recommendations.append("Continue with the next unlocked task.")

    return recommendations


def serialize_learning_progress(progress):
    return {
        "note_id": progress.note_id,
        "total_tasks": progress.total_tasks,
        "completed_tasks": progress.completed_tasks,
        "total_lectures": progress.total_lectures,
        "completed_lectures": progress.completed_lectures,
        "total_tests": progress.total_tests,
        "completed_tests": progress.completed_tests,
        "average_score": progress.average_score,
        "accuracy": progress.accuracy,
        "completion_percentage": progress.completion_percentage,
        "current_topic": progress.current_topic,
        "current_module": progress.current_module,
        "study_time_seconds": progress.study_time_seconds,
        "weak_topics": progress.weak_topics,
        "strong_topics": progress.strong_topics,
        "completed_modules": progress.completed_modules,
        "completed_topics": progress.completed_topics,
        "recommendations": progress.recommendations,
        "updated_at": progress.updated_at,
    }


def normalize_answer(value):
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return " ".join(str(value or "").strip().lower().split())


def normalize_question_type(value):
    normalized = normalize_answer(value).replace("-", "_").replace(" ", "_")
    if normalized in ("mcq", "multiple_choice", "multiple_choice_question"):
        return "mcq"
    if normalized in ("true_false", "true/false", "boolean"):
        return "true_false"
    return "short_answer"


def is_answer_correct(question, submitted):
    expected = normalize_answer(question.correct_answer or question.answer)
    actual = normalize_answer(submitted)

    if not expected or not actual:
        return False

    if question.question_type == "short_answer":
        return actual == expected or actual in expected or expected in actual

    return actual == expected


def grade_test_submission(test, answers):
    questions = TestQuestion.objects.filter(test=test).order_by("order", "id")
    total = questions.count()
    correct_answers = []
    wrong_answers = []
    topic_title = test.topic.title if test.topic else test.title

    for question in questions:
        submitted = answers.get(str(question.id), answers.get(question.id, ""))
        expected = question.correct_answer or question.answer
        row = {
            "question_id": question.id,
            "question": question.question,
            "question_type": question.question_type,
            "submitted_answer": submitted,
            "correct_answer": expected,
            "topic": topic_title,
        }

        if is_answer_correct(question, submitted):
            correct_answers.append(row)
        else:
            wrong_answers.append(row)

    score = len(correct_answers)
    percentage = round((score / total) * 100, 2) if total else 0
    weak_topics = [topic_title] if wrong_answers else []
    strong_topics = [topic_title] if correct_answers and not wrong_answers else []
    passed = percentage >= test.passing_score

    return {
        "total": total,
        "score": score,
        "percentage": percentage,
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "correct_answer_count": len(correct_answers),
        "wrong_answer_count": len(wrong_answers),
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "passed": passed,
    }


def get_or_create_topic_test(note, topic):
    test = getattr(topic, "test", None)
    if test:
        return test

    test_data = build_test(note.extracted_text, topic.title)
    test = Test.objects.create(
        note=note,
        topic=topic,
        title=f"{topic.title} Test",
        instructions="Answer using only your uploaded notes.",
        passing_score=70
    )

    questions = test_data.get("questions", [])
    if not questions:
        questions = [{
            "question_type": "short_answer",
            "question": f"What do you understand by {topic.title}?",
            "options": [],
            "correct_answer": topic.title,
        }]

    for index, question_data in enumerate(questions, start=1):
        question_type = normalize_question_type(question_data.get("question_type"))
        correct_answer = question_data.get("correct_answer") or question_data.get("answer", "")
        options = question_data.get("options", [])
        if question_type == "true_false" and not options:
            options = ["True", "False"]
        TestQuestion.objects.create(
            test=test,
            question=question_data.get("question", ""),
            question_type=question_type,
            answer=correct_answer,
            correct_answer=correct_answer,
            explanation=question_data.get("explanation", ""),
            difficulty=question_data.get("difficulty") or topic.difficulty or "Medium",
            options=options,
            order=index
        )

    return test


def get_or_create_topic_lecture(note, topic):
    lecture = getattr(topic, "lecture", None)
    if lecture:
        return lecture

    lecture_data = build_lecture(note.extracted_text, topic.title)
    simple_explanation = (
        lecture_data.get("simple_explanation")
        or lecture_data.get("explanation")
        or ""
    )
    detailed_explanation = lecture_data.get("detailed_explanation", "")
    real_life_examples = lecture_data.get("real_life_examples", [])
    exam_oriented_examples = lecture_data.get("exam_oriented_examples", [])
    examples = lecture_data.get("examples") or real_life_examples + exam_oriented_examples
    return Lecture.objects.create(
        note=note,
        topic=topic,
        title=lecture_data.get("title") or topic.title,
        content="\n\n".join(
            part for part in [
                lecture_data.get("introduction", ""),
                simple_explanation,
                detailed_explanation,
            ]
            if part
        ),
        introduction=lecture_data.get("introduction", ""),
        explanation=simple_explanation,
        detailed_explanation=detailed_explanation,
        examples=examples,
        real_life_examples=real_life_examples,
        exam_oriented_examples=exam_oriented_examples,
        key_points=lecture_data.get("key_points", []),
        important_definitions=lecture_data.get("important_definitions", []),
        revision_notes=lecture_data.get("revision_notes", []),
        common_mistakes=lecture_data.get("common_mistakes", []),
        quick_recap=lecture_data.get("quick_recap", []),
        order=topic.order
    )


def serialize_lecture_detail(lecture):
    status = "locked"
    if lecture.topic:
        if lecture.topic.lecture_completed:
            status = "completed"
        elif not lecture.topic.locked:
            status = "unlocked"

    return {
        "id": lecture.id,
        "topic_id": lecture.topic_id,
        "title": lecture.title,
        "introduction": lecture.introduction,
        "simple_explanation": lecture.explanation or lecture.content,
        "explanation": lecture.explanation or lecture.content,
        "detailed_explanation": lecture.detailed_explanation,
        "examples": lecture.examples,
        "real_life_examples": lecture.real_life_examples,
        "exam_oriented_examples": lecture.exam_oriented_examples,
        "key_points": lecture.key_points,
        "important_definitions": lecture.important_definitions,
        "revision_notes": lecture.revision_notes,
        "common_mistakes": lecture.common_mistakes,
        "quick_recap": lecture.quick_recap,
        "status": status,
        "order": lecture.order,
        "created_at": lecture.created_at,
    }


def complete_lecture_for_user(user, lecture):
    if not lecture.topic:
        return None, None, False

    topic = lecture.topic
    note = lecture.note
    now = timezone.now()
    task = Task.objects.filter(note=note, topic=topic).order_by("order", "id").first()

    if task:
        was_completed = task.completed
        task.completed = True
        task.completed_at = task.completed_at or now
        task.locked = False
        if task.started_at and not was_completed:
            task.study_time_seconds += int((task.completed_at - task.started_at).total_seconds())
        sync_task_status(task)
        task.save(update_fields=[
            "completed",
            "completed_at",
            "study_time_seconds",
            "locked",
            "status",
        ])

    if not topic.lecture_completed:
        topic.lecture_completed = True
        topic.save(update_fields=["lecture_completed"])

    test = get_or_create_topic_test(note, topic)

    Progress.objects.update_or_create(
        user=user,
        note=note,
        topic=topic,
        defaults={
            "unlocked": True,
            "lecture_completed": topic.lecture_completed,
            "test_completed": topic.test_completed,
        }
    )
    learning_progress = recalculate_learning_progress(user, note)
    return task, learning_progress, bool(test)


def apply_passed_test_side_effects(user, test):
    next_topic = None
    next_task = None

    if not test.topic:
        return next_topic, next_task

    topic = test.topic
    now = timezone.now()

    update_fields = []
    if not topic.test_completed:
        topic.test_completed = True
        update_fields.append("test_completed")
    if not topic.completed:
        topic.completed = True
        update_fields.append("completed")
    if not topic.completed_at:
        topic.completed_at = now
        update_fields.append("completed_at")
    if update_fields:
        topic.save(update_fields=update_fields)

    current_task = Task.objects.filter(
        note=test.note,
        topic=topic
    ).order_by("order", "id").first()
    if current_task:
        next_task = unlock_next_task_after_pass(test.note, current_task)

    next_topic = unlock_next_topic(user, topic)
    if next_topic:
        next_task = get_or_create_topic_task(test.note, next_topic, test.note.estimated_time)
        unlock_task(next_task)

    return next_topic, next_task


def submit_test_for_user(user, test, answers):
    result = grade_test_submission(test, answers)
    submission = TestSubmission.objects.create(
        test=test,
        user=user,
        answers=answers,
        score=result["score"],
        total=result["total"],
        percentage=result["percentage"],
        correct_answers=result["correct_answers"],
        wrong_answers=result["wrong_answers"],
        weak_topics=result["weak_topics"],
        strong_topics=result["strong_topics"],
        passed=result["passed"],
        feedback=f"You scored {result['score']}/{result['total']}."
    )

    next_topic = None
    next_task = None
    if result["passed"]:
        next_topic, next_task = apply_passed_test_side_effects(user, test)

    if test.topic:
        Progress.objects.update_or_create(
            user=user,
            note=test.note,
            topic=test.topic,
            defaults={
                "unlocked": True,
                "lecture_completed": test.topic.lecture_completed,
                "test_completed": test.topic.test_completed,
            }
        )

    learning_progress = recalculate_learning_progress(user, test.note)
    correct_answer_count = result["correct_answer_count"]
    wrong_answer_count = result["wrong_answer_count"]
    response = {
        "success": True,
        "submission_id": submission.id,
        "passed": result["passed"],
        "score": result["score"],
        "total": result["total"],
        "percentage": result["percentage"],
        "accuracy": result["percentage"],
        "correct_answers": correct_answer_count,
        "wrong_answers": wrong_answer_count,
        "correct_answer_details": result["correct_answers"],
        "wrong_answer_details": result["wrong_answers"],
        "weak_topics": result["weak_topics"],
        "strong_topics": result["strong_topics"],
        "next_task_unlocked": result["passed"],
        "next_lecture_unlocked": result["passed"],
        "next_topic_id": next_topic.id if next_topic else None,
        "next_task_id": next_task.id if next_task else None,
        "feedback": submission.feedback,
        "progress_summary": serialize_learning_progress(learning_progress),
    }

    if not result["passed"]:
        response["next_task_unlocked"] = False
        response["next_lecture_unlocked"] = False
        response["message"] = "Pass the current test before continuing."

    return response


def recalculate_learning_progress(user, note):
    complete_modules_and_note(note)

    tasks = Task.objects.filter(note=note)
    topics = Topic.objects.filter(module__note=note).select_related("module")
    tests = Test.objects.filter(note=note)
    submissions = TestSubmission.objects.filter(
        user=user,
        test__note=note
    ).order_by("test_id", "-created_at")

    latest_by_test = {}
    for submission in submissions:
        latest_by_test.setdefault(submission.test_id, submission)

    latest_submissions = list(latest_by_test.values())
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(completed=True).count()
    total_lectures = topics.count()
    completed_lectures = topics.filter(lecture_completed=True).count()
    total_tests = tests.count()
    completed_tests = len([submission for submission in latest_submissions if submission.passed])

    average_score = 0
    accuracy = 0
    weak_topics = []
    strong_topics = []

    if latest_submissions:
        average_score = round(
            sum(submission.score for submission in latest_submissions) / len(latest_submissions),
            2
        )
        accuracy = round(
            sum(submission.percentage for submission in latest_submissions) / len(latest_submissions),
            2
        )

        for submission in latest_submissions:
            weak_topics.extend(submission.weak_topics or [])
            strong_topics.extend(submission.strong_topics or [])

    completion_units = total_tasks + total_lectures + total_tests
    completed_units = completed_tasks + completed_lectures + completed_tests
    completion_percentage = round((completed_units / completion_units) * 100, 2) if completion_units else 0

    current_task = tasks.filter(completed=False, locked=False).select_related(
        "topic",
        "topic__module"
    ).order_by("order", "id").first()
    current_topic = current_task.topic.title if current_task and current_task.topic else ""
    current_module = current_task.topic.module.title if current_task and current_task.topic else ""
    study_time_seconds = sum(task.study_time_seconds for task in tasks)

    progress, _ = LearningProgress.objects.update_or_create(
        user=user,
        note=note,
        defaults={
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "total_lectures": total_lectures,
            "completed_lectures": completed_lectures,
            "total_tests": total_tests,
            "completed_tests": completed_tests,
            "average_score": average_score,
            "accuracy": accuracy,
            "completion_percentage": completion_percentage,
            "current_topic": current_topic,
            "current_module": current_module,
            "study_time_seconds": study_time_seconds,
            "weak_topics": sorted(set(weak_topics)),
            "strong_topics": sorted(set(strong_topics)),
            "completed_modules": Module.objects.filter(note=note, completed=True).count(),
            "completed_topics": topics.filter(completed=True).count(),
        }
    )
    progress.recommendations = build_recommendations(progress)
    progress.save(update_fields=["recommendations", "updated_at"])
    return progress


def ensure_progress_rows(user, note):
    sync_note_tasks(note)

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
                    status=Task.STATUS_UNLOCKED if unlocked else Task.STATUS_LOCKED,
                    description=f"Read the lecture and complete the test for {topic.title}."
                )

            note.subject = ai["subject"]
            note.summary = ai["summary"]
            note.difficulty = ai.get("difficulty", "Medium")
            note.estimated_time = ai.get("estimated_time", "")
            note.learning_plan = ai.get("learning_plan", [])
            note.save()
            ensure_progress_rows(user, note)
            recalculate_learning_progress(user, note)

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
                    "completed": note.completed,
                    "completed_at": note.completed_at,
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
            unlock_next_task_for_completed_progress(user, note)
            learning_progress = recalculate_learning_progress(user, note)
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
                ,
                "progress_summary": serialize_learning_progress(learning_progress)

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

            if task.topic:
                lecture = get_or_create_topic_lecture(task.note, task.topic)
                task, learning_progress, test_available = complete_lecture_for_user(user, lecture)
                next_task = unlock_next_task_after_completion(user, task.note, task) if task else None
            else:
                was_completed = task.completed
                completed_at = task.completed_at or timezone.now()
                task.completed = True
                task.completed_at = completed_at
                if task.started_at and not was_completed:
                    task.study_time_seconds += int((task.completed_at - task.started_at).total_seconds())
                sync_task_status(task)
                task.save(update_fields=[
                    "completed",
                    "completed_at",
                    "study_time_seconds",
                    "status",
                    "locked",
                ])
                next_task = unlock_next_task_after_completion(user, task.note, task)
                learning_progress = recalculate_learning_progress(user, task.note)
                test_available = False

            if task and task.topic:
                learning_progress = recalculate_learning_progress(user, task.note)

            return Response({
                "success": True,
                "task": serialize_tasks([task])[0],
                "lecture_completed": bool(task.topic and task.topic.lecture_completed),
                "test_available": test_available,
                "next_task_unlocked": bool(next_task),
                "next_task": serialize_tasks([next_task])[0] if next_task else None,
                "progress_summary": serialize_learning_progress(learning_progress),
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
            sync_note_tasks(note)
            unlock_next_task_for_completed_progress(user, note)
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


class StartTaskView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, task_id):
        return self.post(request, task_id)

    def post(self, request, task_id):

        try:
            user = get_or_create_request_user(request.user)
            task = Task.objects.select_related(
                "note",
                "topic",
                "topic__module"
            ).get(id=task_id, note__user=user)

            if task.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Task is locked"
                    },
                    status=403
                )

            if not task.topic:
                return Response(
                    {
                        "success": False,
                        "error": "Task topic not found"
                    },
                    status=400
                )

            lecture = get_or_create_topic_lecture(task.note, task.topic)
            update_fields = []
            if not task.started_at:
                task.started_at = timezone.now()
                update_fields.append("started_at")
            if task.status != Task.STATUS_IN_PROGRESS and not task.completed:
                task.status = Task.STATUS_IN_PROGRESS
                update_fields.append("status")
            if update_fields:
                task.save(update_fields=update_fields)

            Progress.objects.update_or_create(
                user=user,
                note=task.note,
                topic=task.topic,
                defaults={
                    "unlocked": True,
                    "lecture_completed": task.topic.lecture_completed,
                    "test_completed": task.topic.test_completed,
                }
            )
            learning_progress = recalculate_learning_progress(user, task.note)

            return Response({
                "success": True,
                "task": serialize_tasks([task])[0],
                "lecture": serialize_lecture_detail(lecture),
                "progress_summary": serialize_learning_progress(learning_progress),
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


class TaskLectureView(StartTaskView):
    pass


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

            lecture = get_or_create_topic_lecture(note, topic)

            task = Task.objects.filter(note=note, topic=topic).order_by("order", "id").first()
            if task and not task.completed:
                update_fields = []
                if not task.started_at:
                    task.started_at = timezone.now()
                    update_fields.append("started_at")
                if task.status != Task.STATUS_IN_PROGRESS:
                    task.status = Task.STATUS_IN_PROGRESS
                    update_fields.append("status")
                if update_fields:
                    task.save(update_fields=update_fields)

            Progress.objects.update_or_create(
                user=user,
                note=note,
                topic=topic,
                defaults={
                    "unlocked": True,
                    "lecture_completed": topic.lecture_completed,
                    "test_completed": topic.test_completed,
                }
            )
            learning_progress = recalculate_learning_progress(user, note)
            lecture_data = serialize_lecture_detail(lecture)

            return Response({
                "success": True,
                **lecture_data,
                "topic_id": topic.id,
                "task": serialize_tasks([task])[0] if task else None,
                "lecture": lecture_data,
                "progress_summary": serialize_learning_progress(learning_progress),
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


class LectureDetailView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, lecture_id):

        try:
            user = get_or_create_request_user(request.user)
            lecture = Lecture.objects.select_related(
                "note",
                "topic"
            ).get(id=lecture_id, note__user=user)

            if lecture.topic and lecture.topic.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Lecture is locked"
                    },
                    status=403
                )

            lecture_data = serialize_lecture_detail(lecture)
            return Response({
                "success": True,
                **lecture_data,
                "lecture": lecture_data,
            })

        except Lecture.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Lecture not found"
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


class CompleteLectureView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def post(self, request, lecture_id):

        try:
            user = get_or_create_request_user(request.user)
            lecture = Lecture.objects.select_related(
                "note",
                "topic"
            ).get(id=lecture_id, note__user=user)

            if lecture.topic and lecture.topic.locked:
                return Response(
                    {
                        "success": False,
                        "error": "Lecture is locked"
                    },
                    status=403
                )

            task, learning_progress, test_available = complete_lecture_for_user(user, lecture)

            return Response({
                "success": True,
                "lecture_completed": bool(lecture.topic and lecture.topic.lecture_completed),
                "test_available": test_available,
                "task": serialize_tasks([task])[0] if task else None,
                "progress_summary": serialize_learning_progress(learning_progress),
            })

        except Lecture.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Lecture not found"
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

            test = get_or_create_topic_test(note, topic)
            recalculate_learning_progress(user, note)

            return Response({
                "success": True,
                "topic_id": topic.id,
                "test_id": test.id,
                "passing_score": test.passing_score,
                "questions": serialize_test_questions(test)
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
            return Response(submit_test_for_user(user, test, answers))

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
            summaries = []

            for note in Note.objects.filter(user=user):
                ensure_progress_rows(user, note)
                summaries.append(serialize_learning_progress(
                    recalculate_learning_progress(user, note)
                ))

            return Response({
                "success": True,
                "progress": serialize_progress(user),
                "summaries": summaries,
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


class FinalReportView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def get(self, request, note_id):

        try:
            user = get_or_create_request_user(request.user)
            note = Note.objects.get(id=note_id, user=user)
            progress = recalculate_learning_progress(user, note)
            latest_submissions = []
            seen_tests = set()

            submissions = TestSubmission.objects.filter(
                user=user,
                test__note=note
            ).select_related("test", "test__topic").order_by("test_id", "-created_at")

            for submission in submissions:
                if submission.test_id in seen_tests:
                    continue
                seen_tests.add(submission.test_id)
                latest_submissions.append(submission)

            completed_topics = list(
                Topic.objects.filter(module__note=note, completed=True)
                .order_by("module__order", "order", "id")
                .values_list("title", flat=True)
            )
            completed_modules = list(
                Module.objects.filter(note=note, completed=True)
                .order_by("order", "id")
                .values_list("title", flat=True)
            )

            return Response({
                "success": True,
                "note_id": note.id,
                "overall_score": progress.average_score,
                "average_accuracy": progress.accuracy,
                "study_time": progress.study_time_seconds,
                "study_time_seconds": progress.study_time_seconds,
                "completed_modules": completed_modules,
                "completed_topics": completed_topics,
                "weak_topics": progress.weak_topics,
                "strong_topics": progress.strong_topics,
                "recommendations": progress.recommendations,
                "submissions": [
                    {
                        "submission_id": submission.id,
                        "test_id": submission.test_id,
                        "topic": submission.test.topic.title if submission.test.topic else "",
                        "score": submission.score,
                        "total": submission.total,
                        "percentage": submission.percentage,
                        "passed": submission.passed,
                        "created_at": submission.created_at,
                    }
                    for submission in latest_submissions
                ],
                "progress_summary": serialize_learning_progress(progress),
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


class SubmitTestView(APIView):

    permission_classes = [FirebaseAuthenticated]

    def post(self, request, test_id):

        try:
            user = get_or_create_request_user(request.user)
            test = Test.objects.get(id=test_id, note__user=user)
            answers = request.data.get("answers") or {}
            return Response(submit_test_for_user(user, test, answers))

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
