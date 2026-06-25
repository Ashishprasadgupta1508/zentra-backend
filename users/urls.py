from django.urls import path
from .views import VerifyUserView

urlpatterns = [
    path(
        "verify-user/",
        VerifyUserView.as_view(),
        name="verify-user",
    ),
]