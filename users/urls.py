from django.urls import path

from .views import (
    SignupView,
    LoginView,
    VerifyUserView,
    ProfileView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("verify-user/", VerifyUserView.as_view(), name="verify-user"),
    path("profile/", ProfileView.as_view(), name="profile"),
]