from django.urls import path

from .views import NoteDetailView, NoteListView, UploadNoteView

urlpatterns = [

    path(

        "",

        NoteListView.as_view(),

        name="note-list"

    ),

    path(

        "upload",

        UploadNoteView.as_view(),

        name="upload-note-no-slash"

    ),

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
