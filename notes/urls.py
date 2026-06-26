from django.urls import path

from .views import NoteDetailView, UploadNoteView

urlpatterns = [

    path(

        "upload/",

        UploadNoteView.as_view(),

        name="upload-note"

    ),

    path(

    "<int:note_id>/",

    NoteDetailView.as_view(),

    name="note-detail"

    ),

]