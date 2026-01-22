"""
URL configuration for libraries app.
"""
from django.urls import path
from apps.libraries.views import (
    LibraryCreateView,
    LibraryListView,
    LibraryUpdateView,
    LibrarySummaryView,
    ChapterCreateView,
    ChapterListView,
    ChapterRecentView,
    ChapterDetailView,
    ChapterSummaryView,
)

app_name = 'libraries'

urlpatterns = [
    # Chapter endpoints (more specific paths first)
    path('chapters/recent', ChapterRecentView.as_view(), name='chapter-recent'),
    path('chapters/<uuid:chapter_id>/summary', ChapterSummaryView.as_view(), name='chapter-summary'),
    path('chapters/<uuid:chapter_id>', ChapterDetailView.as_view(), name='chapter-detail'),
    
    # Library-specific chapter endpoints
    path('<uuid:library_id>/chapters/create', ChapterCreateView.as_view(), name='chapter-create'),
    path('<uuid:library_id>/chapters', ChapterListView.as_view(), name='chapter-list'),
    
    # Library endpoints
    path('<uuid:library_id>/summary', LibrarySummaryView.as_view(), name='library-summary'),
    path('create', LibraryCreateView.as_view(), name='library-create'),
    path('<uuid:library_id>', LibraryUpdateView.as_view(), name='library-update'),
    path('', LibraryListView.as_view(), name='library-list'),
]
