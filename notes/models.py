from django.db import models
from users.models import User


class Note(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=255)

    uploaded_file = models.FileField(
        upload_to="notes/"
    )

    extracted_text = models.TextField(
        blank=True
    )

    subject = models.CharField(
        max_length=255,
        blank=True
    )

    summary = models.TextField(
        blank=True
    )

    difficulty = models.CharField(
        max_length=50,
        blank=True
    )

    estimated_time = models.CharField(
        max_length=100,
        blank=True
    )

    learning_plan = models.JSONField(
        default=list,
        blank=True
    )

    completed = models.BooleanField(default=False)

    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title


class Module(models.Model):

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="modules"
    )

    title = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True
    )

    order = models.IntegerField()

    completed = models.BooleanField(default=False)

    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Topic(models.Model):

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="topics"
    )

    title = models.CharField(
        max_length=255
    )

    order = models.IntegerField(default=1)

    difficulty = models.CharField(
        max_length=50,
        default="Medium"
    )

    locked = models.BooleanField(default=True)

    lecture_completed = models.BooleanField(default=False)

    test_completed = models.BooleanField(default=False)

    completed = models.BooleanField(default=False)

    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Lecture(models.Model):

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="lectures"
    )

    topic = models.OneToOneField(
        Topic,
        on_delete=models.CASCADE,
        related_name="lecture",
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255)

    content = models.TextField(blank=True)

    introduction = models.TextField(blank=True)

    explanation = models.TextField(blank=True)

    detailed_explanation = models.TextField(blank=True)

    examples = models.JSONField(default=list, blank=True)

    real_life_examples = models.JSONField(default=list, blank=True)

    exam_oriented_examples = models.JSONField(default=list, blank=True)

    key_points = models.JSONField(default=list, blank=True)

    important_definitions = models.JSONField(default=list, blank=True)

    revision_notes = models.JSONField(default=list, blank=True)

    common_mistakes = models.JSONField(default=list, blank=True)

    quick_recap = models.JSONField(default=list, blank=True)

    order = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Task(models.Model):

    STATUS_LOCKED = "locked"
    STATUS_UNLOCKED = "unlocked"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_LOCKED, "Locked"),
        (STATUS_UNLOCKED, "Unlocked"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255)

    estimated_time = models.CharField(max_length=100, blank=True)

    task_type = models.CharField(max_length=50, default="study")

    order = models.IntegerField(default=1)

    locked = models.BooleanField(default=True)

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_LOCKED
    )

    description = models.TextField(blank=True)

    completed = models.BooleanField(default=False)

    started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    completed_at = models.DateTimeField(null=True, blank=True)

    study_time_seconds = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title


class Test(models.Model):

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="tests"
    )

    topic = models.OneToOneField(
        Topic,
        on_delete=models.CASCADE,
        related_name="test",
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255)

    instructions = models.TextField(blank=True)

    passing_score = models.PositiveIntegerField(default=70)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class TestQuestion(models.Model):

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question = models.TextField()

    question_type = models.CharField(max_length=50, default="short_answer")

    answer = models.TextField(blank=True)

    correct_answer = models.TextField(blank=True)

    explanation = models.TextField(blank=True)

    difficulty = models.CharField(max_length=50, default="Medium")

    options = models.JSONField(default=list, blank=True)

    order = models.IntegerField(default=1)

    def __str__(self):
        return self.question


class TestSubmission(models.Model):

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="submissions"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="test_submissions"
    )

    answers = models.JSONField(default=dict)

    score = models.IntegerField(default=0)

    total = models.IntegerField(default=0)

    percentage = models.FloatField(default=0)

    correct_answers = models.JSONField(default=list, blank=True)

    wrong_answers = models.JSONField(default=list, blank=True)

    weak_topics = models.JSONField(default=list, blank=True)

    strong_topics = models.JSONField(default=list, blank=True)

    passed = models.BooleanField(default=False)

    feedback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.test.title} - {self.score}/{self.total}"


class Progress(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="progress"
    )

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="progress"
    )

    topic = models.OneToOneField(
        Topic,
        on_delete=models.CASCADE,
        related_name="progress",
        null=True,
        blank=True
    )

    lecture_completed = models.BooleanField(default=False)

    test_completed = models.BooleanField(default=False)

    unlocked = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "topic")

    def __str__(self):
        return f"{self.user_id} - {self.topic_id}"


class LearningProgress(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="learning_progress"
    )

    note = models.OneToOneField(
        Note,
        on_delete=models.CASCADE,
        related_name="learning_progress"
    )

    total_tasks = models.PositiveIntegerField(default=0)

    completed_tasks = models.PositiveIntegerField(default=0)

    total_lectures = models.PositiveIntegerField(default=0)

    completed_lectures = models.PositiveIntegerField(default=0)

    total_tests = models.PositiveIntegerField(default=0)

    completed_tests = models.PositiveIntegerField(default=0)

    average_score = models.FloatField(default=0)

    accuracy = models.FloatField(default=0)

    completion_percentage = models.FloatField(default=0)

    current_topic = models.CharField(max_length=255, blank=True)

    current_module = models.CharField(max_length=255, blank=True)

    study_time_seconds = models.PositiveIntegerField(default=0)

    weak_topics = models.JSONField(default=list, blank=True)

    strong_topics = models.JSONField(default=list, blank=True)

    completed_modules = models.PositiveIntegerField(default=0)

    completed_topics = models.PositiveIntegerField(default=0)

    recommendations = models.JSONField(default=list, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "note")

    def __str__(self):
        return f"{self.user_id} - {self.note_id}"


class ChatHistory(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_history"
    )

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="chat_history",
        null=True,
        blank=True
    )

    message = models.TextField()

    answer = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message[:80]
