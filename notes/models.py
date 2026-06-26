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