"""
Serializers for onboarding endpoints.
"""
from rest_framework import serializers
from apps.onboarding.models import Onboarding


class OnboardingStatusSerializer(serializers.Serializer):
    """Serializer for onboarding status response."""
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


class SetLockMethodSerializer(serializers.Serializer):
    """Serializer for setting lock method."""
    lockMethod = serializers.ChoiceField(
        choices=Onboarding.LOCK_METHOD_CHOICES,
        required=True
    )


class SetPasscodeSerializer(serializers.Serializer):
    """Serializer for setting passcode created."""
    lockEnabled = serializers.BooleanField(required=True)


class SetBiometricSerializer(serializers.Serializer):
    """Serializer for enabling/disabling biometric."""
    enabled = serializers.BooleanField(required=True)
    deviceId = serializers.UUIDField(required=True)
    biometricType = serializers.ChoiceField(
        choices=[
            ('FACE_ID', 'Face ID'),
            ('FINGERPRINT', 'Fingerprint'),
            ('UNKNOWN', 'Unknown'),
        ],
        required=False,
        allow_null=True
    )


class CompleteOnboardingSerializer(serializers.Serializer):
    """Serializer for completing onboarding."""
    completed = serializers.BooleanField(required=True)
