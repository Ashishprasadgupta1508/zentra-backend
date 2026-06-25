from django.db import models


class User(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    photo_url = models.URLField(blank=True, null=True)

    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email