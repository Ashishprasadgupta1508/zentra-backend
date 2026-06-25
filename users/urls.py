from django.urls import path

from users import SignupView
from .views import ProfileView, VerifyUserView
from .views import LoginView


urlpatterns = [
    path(
        "verify-user/",
        VerifyUserView.as_view(),
        name="verify-user",
    ),
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
    "profile/",
    ProfileView.as_view(),
    name="profile"
),

]