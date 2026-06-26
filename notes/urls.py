from django.urls import path

from .views import UploadNoteView

urlpatterns = [

    path(

        "upload/",

        UploadNoteView.as_view(),

        name="upload-note"

    )

]