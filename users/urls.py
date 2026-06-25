from django.urls import path

from .views import (
    VerifyUserView,
    SignupView,
    SendVerificationEmailView,
)

urlpatterns = [
    path(
        "verify-user/",
        VerifyUserView.as_view(),
        name="verify-user"
    ),

    path(
        "signup/",
        SignupView.as_view(),
        name="signup"
    ),

    path(
        "send-verification-email/",
        SendVerificationEmailView.as_view(),
        name="send-verification-email"
    ),
]