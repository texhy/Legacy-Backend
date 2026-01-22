"""
URL configuration for chat app.
"""
from django.urls import path
from apps.chat.views import ChapterMessagesView

app_name = 'chat'

urlpatterns = [
    path('chapters/<uuid:chapter_id>/messages/', ChapterMessagesView.as_view(), name='chapter-messages'),
]
