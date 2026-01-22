"""
Models for chat messages.
"""
from django.db import models
from django.utils import timezone


class Message(models.Model):
    """Individual chat message within a chapter."""
    
    class Sender(models.TextChoices):
        USER = 'USER', 'User'
        AI = 'AI', 'AI Assistant'
        SYSTEM = 'SYSTEM', 'System'
    
    id = models.BigAutoField(primary_key=True)  # Snowflake-style for ordering
    chapter = models.ForeignKey(
        'libraries.Chapter', 
        on_delete=models.CASCADE, 
        related_name='messages',
        db_index=True
    )
    sender = models.CharField(max_length=10, choices=Sender.choices, db_index=True)
    content = models.TextField()
    
    # NEW: Metadata for enhanced AI understanding
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text='{"emotion": "happy", "topics": ["work", "promotion"]}'
    )
    
    # NEW: For streaming responses
    is_complete = models.BooleanField(
        default=True,
        help_text='False while AI is still generating'
    )
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['chapter', 'timestamp']),
            models.Index(fields=['chapter', 'sender']),
        ]
    
    def __str__(self):
        return f"{self.sender}: {self.content[:50]}..."
