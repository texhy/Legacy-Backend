"""
Account models for authentication and user management.
"""
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model with email as username."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    username = None  # Remove username field
    email_verified = models.BooleanField(default=False, db_index=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email


class RefreshToken(models.Model):
    """Refresh token model for JWT token rotation."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='refresh_tokens',
        db_index=True
    )
    device = models.ForeignKey(
        'devices.Device',
        on_delete=models.CASCADE,
        related_name='refresh_tokens',
        db_index=True
    )
    token_hash = models.CharField(max_length=255, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'refresh_tokens'
        indexes = [
            models.Index(fields=['user', 'device', 'revoked_at']),
            models.Index(fields=['token_hash']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"RefreshToken for {self.user.email} on {self.device.platform}"
    
    def is_valid(self):
        """Check if token is valid (not revoked and not expired)."""
        if self.revoked_at:
            return False
        return timezone.now() < self.expires_at


class PasswordResetOTP(models.Model):
    """Password reset OTP model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
        db_index=True
    )
    otp_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    consumed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'password_reset_otps'
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['consumed_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.user.email}"
    
    def is_valid(self):
        """Check if OTP is valid (not consumed, not expired, attempts not exceeded)."""
        if self.consumed_at:
            return False
        if self.attempts >= self.max_attempts:
            return False
        return timezone.now() < self.expires_at


class PasswordResetToken(models.Model):
    """Password reset token model (issued after OTP verification)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        db_index=True
    )
    token_hash = models.CharField(max_length=255, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'password_reset_tokens'
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['user', 'expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"ResetToken for {self.user.email}"
    
    def is_valid(self):
        """Check if token is valid (not consumed and not expired)."""
        if self.consumed_at:
            return False
        return timezone.now() < self.expires_at


class EmailVerificationOTP(models.Model):
    """Email verification OTP model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_verification_otps',
        db_index=True
    )
    otp_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    consumed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_verification_otps'
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['consumed_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email Verification OTP for {self.user.email}"
    
    def is_valid(self):
        """Check if OTP is valid (not consumed, not expired, attempts not exceeded)."""
        if self.consumed_at:
            return False
        if self.attempts >= self.max_attempts:
            return False
        return timezone.now() < self.expires_at
