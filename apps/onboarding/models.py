"""
Onboarding models for tracking user onboarding progress.
"""
import uuid
from django.db import models
from django.utils import timezone


class Onboarding(models.Model):
    """Onboarding model for tracking user onboarding progress."""
    
    STEP_CHOICES = [
        ('SECURITY_METHOD', 'Security Method'),
        ('CREATE_PASSCODE', 'Create Passcode'),
        ('BIOMETRIC', 'Biometric'),
        ('DONE', 'Done'),
    ]
    
    LOCK_METHOD_CHOICES = [
        ('PIN', 'PIN'),
        ('PATTERN', 'Pattern'),
        ('PASSWORD', 'Password'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='onboarding',
        db_index=True
    )
    current_step = models.CharField(
        max_length=20,
        choices=STEP_CHOICES,
        default='SECURITY_METHOD'
    )
    lock_method = models.CharField(
        max_length=20,
        choices=LOCK_METHOD_CHOICES,
        null=True,
        blank=True
    )
    lock_enabled = models.BooleanField(default=False)
    biometric_enabled = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'onboarding'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Onboarding for {self.user.email} - {self.current_step}"
    
    @property
    def completed(self):
        """Check if onboarding is completed."""
        return self.completed_at is not None
    
    def mark_completed(self):
        """Mark onboarding as completed."""
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.current_step = 'DONE'
            self.save(update_fields=['completed_at', 'current_step', 'updated_at'])
