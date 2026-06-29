"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.http import JsonResponse
from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from insights.views import ChatView
from notes.views import (
    CompleteLectureView,
    CompleteTaskView,
    FinalReportView,
    LectureDetailView,
    LectureView,
    ProgressView,
    StartTaskView,
    SubmitTestView,
    SubmitTopicTestView,
    TaskLectureView,
    TaskListView,
    TopicTestView,
)


def home(request):
    return JsonResponse({
        "status": "Backend is running successfully 🚀"
    })


urlpatterns = [

    path("", home),

    path("admin/", admin.site.urls),

    path("api/", include("users.urls")),

    path("api/notes/", include("notes.urls")),
    path("api/insights/", include("insights.urls")),
    path("api/chat", ChatView.as_view(), name="chat-no-slash"),
    path("api/chat/", ChatView.as_view(), name="chat"),
    path("api/tasks/<int:note_id>", TaskListView.as_view(), name="task-list-no-slash"),
    path("api/tasks/<int:note_id>/", TaskListView.as_view(), name="task-list"),
    path("api/tasks/<int:task_id>/start", StartTaskView.as_view(), name="task-start-no-slash"),
    path("api/tasks/<int:task_id>/start/", StartTaskView.as_view(), name="task-start"),
    path("api/tasks/<int:task_id>/lecture", TaskLectureView.as_view(), name="task-lecture-no-slash"),
    path("api/tasks/<int:task_id>/lecture/", TaskLectureView.as_view(), name="task-lecture"),
    path("api/tasks/<int:task_id>/complete", CompleteTaskView.as_view(), name="task-complete-no-slash"),
    path("api/tasks/<int:task_id>/complete/", CompleteTaskView.as_view(), name="task-complete"),
    path("api/lecture/<int:topic_id>", LectureView.as_view(), name="topic-lecture-no-slash"),
    path("api/lecture/<int:topic_id>/", LectureView.as_view(), name="topic-lecture"),
    path("api/lectures/<int:lecture_id>", LectureDetailView.as_view(), name="lecture-detail-no-slash"),
    path("api/lectures/<int:lecture_id>/", LectureDetailView.as_view(), name="lecture-detail"),
    path("api/lectures/<int:lecture_id>/complete", CompleteLectureView.as_view(), name="lecture-complete-no-slash"),
    path("api/lectures/<int:lecture_id>/complete/", CompleteLectureView.as_view(), name="lecture-complete"),
    path("api/test/<int:topic_id>", TopicTestView.as_view(), name="topic-test-no-slash"),
    path("api/test/<int:topic_id>/", TopicTestView.as_view(), name="topic-test"),
    path("api/test/<int:topic_id>/submit", SubmitTopicTestView.as_view(), name="topic-test-submit-no-slash"),
    path("api/test/<int:topic_id>/submit/", SubmitTopicTestView.as_view(), name="topic-test-submit"),
    path("api/progress", ProgressView.as_view(), name="progress-no-slash"),
    path("api/progress/", ProgressView.as_view(), name="progress"),
    path("api/notes/<int:note_id>/final-report", FinalReportView.as_view(), name="final-report-no-slash"),
    path("api/notes/<int:note_id>/final-report/", FinalReportView.as_view(), name="final-report"),
    path("api/tests/<int:test_id>/submit", SubmitTestView.as_view(), name="test-submit-no-slash"),
    path("api/tests/<int:test_id>/submit/", SubmitTestView.as_view(), name="test-submit"),

]


# ADD THIS AT THE VERY BOTTOM

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
