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

    difficulty = models.CharField(
        max_length=50,
        default="Medium"
    )

    def __str__(self):
        return self.title


class Lecture(models.Model):

    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="lectures"
    )

    title = models.CharField(max_length=255)

    content = models.TextField(blank=True)

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

    title = models.CharField(max_length=255)

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

    answer = models.TextField(blank=True)

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
