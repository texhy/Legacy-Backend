"""
Models for library and chapter management.
"""
import uuid
from django.db import models
from django.utils import timezone


class Library(models.Model):
    """Library model for user's content containers."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='libraries',
        db_index=True
    )
    title = models.CharField(max_length=255)
    color_theme = models.CharField(max_length=7, default='#000000', help_text='Hex color code')
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
    """Chapter model for library content entries."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name='chapters',
        db_index=True
    )
    title = models.CharField(max_length=255)
    content_preview = models.TextField(
        blank=True,
        help_text='Preview/snippet text for card display'
    )
    content_full = models.TextField(
        help_text='Full content of the chapter'
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
