"""
Views for onboarding endpoints.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.onboarding.models import Onboarding
from apps.onboarding.serializers import (
    OnboardingStatusSerializer,
    SetLockMethodSerializer,
    SetPasscodeSerializer,
    SetBiometricSerializer,
    CompleteOnboardingSerializer,
)
from apps.devices.models import Device


class OnboardingStatusView(APIView):
    """Get onboarding status endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Onboarding Status",
        description="Get current onboarding status for the authenticated user.",
        responses={
            200: {
                'description': 'Onboarding status',
                'content': {
                    'application/json': {
                        'example': {
                            'currentStep': 'SECURITY_METHOD',
                            'lockMethod': None,
                            'lockEnabled': False,
                            'biometricEnabled': False,
                            'completed': False
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        """Get onboarding status."""
        user = request.user
        
        # Get or create onboarding record
        onboarding, _ = Onboarding.objects.get_or_create(
            user=user,
            defaults={'current_step': 'SECURITY_METHOD'}
        )
        
        serializer = OnboardingStatusSerializer(onboarding)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SetLockMethodView(APIView):
    """Set lock method endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Set Lock Method",
        description="Set the lock method (PIN, PATTERN, or PASSWORD) and move to next step.",
        request=SetLockMethodSerializer,
        responses={
            200: {
                'description': 'Updated onboarding status',
                'content': {
                    'application/json': {
                        'example': {
                            'currentStep': 'CREATE_PASSCODE',
                            'lockMethod': 'PIN',
                            'lockEnabled': False,
                            'biometricEnabled': False,
                            'completed': False
                        }
                    }
                }
            },
            400: {'description': 'Validation error'}
        }
    )
    def post(self, request):
        """Set lock method."""
        serializer = SetLockMethodSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        lock_method = serializer.validated_data['lockMethod']
        
        # Get or create onboarding record
        onboarding, _ = Onboarding.objects.get_or_create(
            user=user,
            defaults={'current_step': 'SECURITY_METHOD'}
        )
        
        # Update lock method and step
        onboarding.lock_method = lock_method
        onboarding.current_step = 'CREATE_PASSCODE'
        onboarding.save(update_fields=['lock_method', 'current_step', 'updated_at'])
        
        response_serializer = OnboardingStatusSerializer(onboarding)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SetPasscodeView(APIView):
    """Set passcode created endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Set Passcode Created",
        description="Mark passcode as created (server does NOT store the actual passcode).",
        request=SetPasscodeSerializer,
        responses={
            200: {
                'description': 'Updated onboarding status',
                'content': {
                    'application/json': {
                        'example': {
                            'currentStep': 'BIOMETRIC',
                            'lockMethod': 'PIN',
                            'lockEnabled': True,
                            'biometricEnabled': False,
                            'completed': False
                        }
                    }
                }
            },
            400: {'description': 'Validation error'}
        }
    )
    def post(self, request):
        """Set passcode created."""
        serializer = SetPasscodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        lock_enabled = serializer.validated_data['lockEnabled']
        
        if not lock_enabled:
            return Response(
                {'error': {'code': 400, 'message': 'lockEnabled must be true'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get onboarding record (should exist at this point)
        try:
            onboarding = Onboarding.objects.get(user=user)
        except Onboarding.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Onboarding record not found. Please set lock method first.'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update lock enabled and step
        onboarding.lock_enabled = True
        onboarding.current_step = 'BIOMETRIC'
        onboarding.save(update_fields=['lock_enabled', 'current_step', 'updated_at'])
        
        response_serializer = OnboardingStatusSerializer(onboarding)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SetBiometricView(APIView):
    """Enable/disable biometric endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Enable/Disable Biometric",
        description="Enable or disable biometric authentication for the device.",
        request=SetBiometricSerializer,
        responses={
            200: {
                'description': 'Updated onboarding status',
                'content': {
                    'application/json': {
                        'example': {
                            'currentStep': 'DONE',
                            'lockMethod': 'PIN',
                            'lockEnabled': True,
                            'biometricEnabled': True,
                            'completed': False
                        }
                    }
                }
            },
            400: {'description': 'Validation error'},
            404: {'description': 'Device not found'}
        }
    )
    def post(self, request):
        """Set biometric enabled/disabled."""
        serializer = SetBiometricSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        enabled = serializer.validated_data['enabled']
        device_id = serializer.validated_data['deviceId']
        biometric_type = serializer.validated_data.get('biometricType')
        
        # Get device (must belong to user)
        try:
            device = Device.objects.get(id=device_id, user=user)
        except Device.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Device not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get onboarding record
        try:
            onboarding = Onboarding.objects.get(user=user)
        except Onboarding.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Onboarding record not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update biometric settings
        onboarding.biometric_enabled = enabled
        device.biometric_enabled = enabled
        if biometric_type:
            device.biometric_type = biometric_type
        
        # Move to DONE step if enabled OR if user skips (enabled=false)
        onboarding.current_step = 'DONE'
        
        device.save(update_fields=['biometric_enabled', 'biometric_type', 'updated_at'])
        onboarding.save(update_fields=['biometric_enabled', 'current_step', 'updated_at'])
        
        response_serializer = OnboardingStatusSerializer(onboarding)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class CompleteOnboardingView(APIView):
    """Complete onboarding endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Complete Onboarding",
        description="Mark onboarding as completed.",
        request=CompleteOnboardingSerializer,
        responses={
            200: {
                'description': 'Updated onboarding status',
                'content': {
                    'application/json': {
                        'example': {
                            'currentStep': 'DONE',
                            'lockMethod': 'PIN',
                            'lockEnabled': True,
                            'biometricEnabled': True,
                            'completed': True
                        }
                    }
                }
            },
            400: {'description': 'Validation error'}
        }
    )
    def post(self, request):
        """Complete onboarding."""
        serializer = CompleteOnboardingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        completed = serializer.validated_data['completed']
        
        if not completed:
            return Response(
                {'error': {'code': 400, 'message': 'completed must be true'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        
        # Get onboarding record
        try:
            onboarding = Onboarding.objects.get(user=user)
        except Onboarding.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Onboarding record not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Mark as completed
        onboarding.mark_completed()
        
        response_serializer = OnboardingStatusSerializer(onboarding)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
