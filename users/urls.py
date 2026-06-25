from django.urls import path
from .views import VerifyUserView, SignupView

urlpatterns = [
    path("verify-user/", VerifyUserView.as_view()),
    path("signup/", SignupView.as_view()),
]