"""
Admin configuration for libraries app.
"""
from django.contrib import admin
from apps.libraries.models import Library, Chapter


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    """Admin interface for Library model."""
    list_display = ['title', 'user', 'color_theme', 'is_archived', 'created_at']
    list_filter = ['is_archived', 'created_at']
    search_fields = ['title', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    """Admin interface for Chapter model."""
    list_display = ['title', 'library', 'is_archived', 'updated_at', 'created_at']
    list_filter = ['is_archived', 'created_at', 'updated_at']
    search_fields = ['title', 'content_preview', 'library__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-updated_at']
