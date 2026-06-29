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

    explanation = models.TextField(blank=True)

    examples = models.JSONField(default=list, blank=True)

    key_points = models.JSONField(default=list, blank=True)

    order = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Task(models.Model):

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

    description = models.TextField(blank=True)

    completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    completed_at = models.DateTimeField(null=True, blank=True)

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
