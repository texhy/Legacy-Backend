"""
Serializers for authentication endpoints.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.devices.models import Device
from apps.onboarding.models import Onboarding
from apps.accounts.models import RefreshToken
from apps.accounts.utils import hash_token

User = get_user_model()


class DeviceSerializer(serializers.Serializer):
    """Serializer for device information."""
    fingerprint = serializers.CharField(max_length=255, required=True)
    platform = serializers.ChoiceField(choices=Device.PLATFORM_CHOICES, required=True)
    model = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    osVersion = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, source='os_version')
    appVersion = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, source='app_version')
    
    def to_internal_value(self, data):
        """Convert osVersion and appVersion to os_version and app_version."""
        # Create a copy to avoid modifying the original
        data_copy = data.copy()
        if 'osVersion' in data_copy:
            data_copy['os_version'] = data_copy.pop('osVersion')
        if 'appVersion' in data_copy:
            data_copy['app_version'] = data_copy.pop('appVersion')
        return super().to_internal_value(data_copy)


class SignupSerializer(serializers.Serializer):
    """Serializer for user signup."""
    name = serializers.CharField(max_length=255, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    device = DeviceSerializer(required=True)
    
    def validate_email(self, value):
        """Check if email is already taken."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        """Create user, device, and onboarding."""
        device_data = validated_data.pop('device')
        password = validated_data.pop('password')
        
        # Create user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=password,
            name=validated_data['name']
        )
        
        # Create or get device
        # Handle camelCase to snake_case conversion
        os_version = device_data.get('osVersion') or device_data.get('os_version')
        app_version = device_data.get('appVersion') or device_data.get('app_version')
        device, _ = Device.objects.get_or_create(
            user=user,
            fingerprint=device_data['fingerprint'],
            defaults={
                'platform': device_data['platform'],
                'model': device_data.get('model'),
                'os_version': os_version,
                'app_version': app_version,
            }
        )
        
        # Create onboarding if it doesn't exist
        onboarding, _ = Onboarding.objects.get_or_create(
            user=user,
            defaults={'current_step': 'SECURITY_METHOD'}
        )
        
        return {
            'user': user,
            'device': device,
            'onboarding': onboarding
        }


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    rememberMe = serializers.BooleanField(default=True)
    device = DeviceSerializer(required=True)
    
    def validate(self, attrs):
        """Validate email and password."""
        email = attrs.get('email')
        password = attrs.get('password')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Invalid email or password."})
        
        if not user.check_password(password):
            raise serializers.ValidationError({"email": "Invalid email or password."})
        
        if not user.is_active:
            raise serializers.ValidationError({"email": "User account is disabled."})
        
        attrs['user'] = user
        return attrs


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for refresh token endpoint."""
    refreshToken = serializers.CharField(required=True)
    deviceId = serializers.UUIDField(required=True)
    
    def validate(self, attrs):
        """Validate refresh token and device."""
        refresh_token = attrs.get('refreshToken')
        device_id = attrs.get('deviceId')
        token_hash = hash_token(refresh_token)
        
        try:
            refresh_token_obj = RefreshToken.objects.get(
                token_hash=token_hash,
                device_id=device_id,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now()
            )
        except RefreshToken.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired refresh token.")
        
        attrs['refresh_token_obj'] = refresh_token_obj
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout endpoint."""
    refreshToken = serializers.CharField(required=True)
    deviceId = serializers.UUIDField(required=True)
    
    def validate(self, attrs):
        """Validate refresh token and device."""
        refresh_token = attrs.get('refreshToken')
        device_id = attrs.get('deviceId')
        token_hash = hash_token(refresh_token)
        
        try:
            refresh_token_obj = RefreshToken.objects.get(
                token_hash=token_hash,
                device_id=device_id,
                revoked_at__isnull=True
            )
        except RefreshToken.DoesNotExist:
            # Still allow logout even if token not found (idempotent)
            attrs['refresh_token_obj'] = None
            return attrs
        
        attrs['refresh_token_obj'] = refresh_token_obj
        return attrs


class UserResponseSerializer(serializers.ModelSerializer):
    """Serializer for user response."""
    emailVerified = serializers.BooleanField(source='email_verified', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'emailVerified']


class OnboardingResponseSerializer(serializers.Serializer):
    """Serializer for onboarding response."""
    currentStep = serializers.CharField()
    lockMethod = serializers.CharField(allow_null=True)
    lockEnabled = serializers.BooleanField()
    biometricEnabled = serializers.BooleanField()
    completed = serializers.BooleanField()
    
    def to_representation(self, instance):
        """Convert model instance to response format."""
        return {
            'currentStep': instance.current_step,
            'lockMethod': instance.lock_method,
            'lockEnabled': instance.lock_enabled,
            'biometricEnabled': instance.biometric_enabled,
            'completed': instance.completed,
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""
    email = serializers.EmailField(required=True)


class PasswordResetVerifySerializer(serializers.Serializer):
    """Serializer for password reset OTP verification."""
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=4, max_length=6)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation."""
    resetToken = serializers.CharField(required=True)
    newPassword = serializers.CharField(write_only=True, required=True, min_length=8)


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification."""
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=4, max_length=6)
    
    def validate(self, attrs):
        """Validate email exists."""
        email = attrs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "email": "Invalid email."
            })
        
        attrs['user'] = user
        return attrs


class ResendVerificationSerializer(serializers.Serializer):
    """Serializer for resending email verification."""
    email = serializers.EmailField(required=True)
    
    def validate(self, attrs):
        """Validate email exists."""
        email = attrs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "email": "Invalid email."
            })
        
        attrs['user'] = user
        return attrs


class BiometricLoginSerializer(serializers.Serializer):
    """Serializer for biometric/PIN login."""
    email = serializers.EmailField(required=True)
    loginMethod = serializers.ChoiceField(
        choices=['BIOMETRIC', 'PIN'],
        required=True,
        help_text="Login method: BIOMETRIC or PIN"
    )
    device = DeviceSerializer(required=True)
    
    def validate(self, attrs):
        """Validate email exists."""
        email = attrs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "email": "Invalid email or device."
            })
        
        attrs['user'] = user
        return attrs
