"""
Device models for tracking user devices.
"""
import uuid
from django.db import models
from django.utils import timezone


class Device(models.Model):
    """Device model for tracking user devices."""
    
    PLATFORM_CHOICES = [
        ('IOS', 'iOS'),
        ('ANDROID', 'Android'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='devices',
        db_index=True
    )
    fingerprint = models.CharField(max_length=255, db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    model = models.CharField(max_length=255, null=True, blank=True)
    os_version = models.CharField(max_length=50, null=True, blank=True)
    app_version = models.CharField(max_length=50, null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    biometric_enabled = models.BooleanField(default=False)
    biometric_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('FACE_ID', 'Face ID'),
            ('FINGERPRINT', 'Fingerprint'),
            ('UNKNOWN', 'Unknown'),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'devices'
        unique_together = [['user', 'fingerprint']]
        indexes = [
            models.Index(fields=['user', 'fingerprint']),
            models.Index(fields=['last_seen_at']),
        ]
        ordering = ['-last_seen_at']
    
    def __str__(self):
        return f"{self.platform} device for {self.user.email}"
    
    def update_last_seen(self):
        """Update last_seen_at to current time."""
        self.last_seen_at = timezone.now()
        self.save(update_fields=['last_seen_at'])
