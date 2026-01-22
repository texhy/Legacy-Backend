"""
Models for library and chapter management.
"""
import uuid
from django.db import models
from django.utils import timezone


class Library(models.Model):
    """Enhanced Library model with AI summary."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='libraries',
        db_index=True
    )
    title = models.CharField(max_length=255)
    color_theme = models.CharField(max_length=7, default='#000000', help_text='Hex color code')
    
    # NEW: AI-generated high-level summary of the entire library
    summary_text = models.TextField(
        blank=True, 
        default='', 
        help_text='AI-generated abstract of all chapters in this library'
    )
    
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'libraries'
        indexes = [
            models.Index(fields=['user', 'is_archived']),
            models.Index(fields=['user', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.user.email})"


class Chapter(models.Model):
    """Enhanced Chapter model for chat-based content."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name='chapters',
        db_index=True
    )
    title = models.CharField(max_length=255)
    
    # CHANGED: These now serve different purposes
    content_preview = models.TextField(
        blank=True,
        help_text='Auto-generated preview'
    )
    content_full = models.TextField(
        blank=True,
        help_text='Deprecated - use Messages for chat-based content'
    )
    
    # NEW: Rolling summary of conversation (compressed memory)
    summary_text = models.TextField(
        blank=True,
        default='',
        help_text='AI-compressed summary of older messages'
    )
    
    # NEW: Counter for triggering memory compression
    message_count = models.IntegerField(
        default=0,
        help_text='Triggers summarization every 20 messages'
    )
    
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    
    class Meta:
        db_table = 'chapters'
        indexes = [
            models.Index(fields=['library', 'is_archived']),
            models.Index(fields=['library', 'updated_at']),
            models.Index(fields=['updated_at']),  # For recent chapters query
        ]
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.title} ({self.library.title})"
