"""
Admin configuration for chat app.
"""
from django.contrib import admin
from apps.chat.models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""
    list_display = ['id', 'chapter', 'sender', 'content_preview', 'timestamp']
    list_filter = ['sender', 'timestamp']
    search_fields = ['content', 'chapter__title']
    readonly_fields = ['id', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
