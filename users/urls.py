from django.urls import path
from .views import VerifyUserView
from .views import (
    VerifyUserView,
    SignupView,
    SendVerificationEmailView,
)

urlpatterns = [
    path("verify-user/", VerifyUserView.as_view()),
    path("signup/", SignupView.as_view()),
    path(
        "send-verification-email/",
        SendVerificationEmailView.as_view()
    ),
]