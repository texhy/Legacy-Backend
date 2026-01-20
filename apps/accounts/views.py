"""
Views for authentication endpoints.
"""
import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__)

from apps.accounts.serializers import (
    SignupSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    LogoutSerializer,
    UserResponseSerializer,
    OnboardingResponseSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
    BiometricLoginSerializer,
    EmailVerificationSerializer,
    ResendVerificationSerializer,
)
from apps.accounts.throttles import (
    LoginRateThrottle,
    SignupRateThrottle,
    RefreshTokenRateThrottle,
    OTPRequestRateThrottle,
    OTPVerifyRateThrottle,
)
from django.contrib.auth import get_user_model
from apps.devices.models import Device
from apps.onboarding.models import Onboarding
from apps.accounts.models import RefreshToken, PasswordResetOTP, PasswordResetToken, EmailVerificationOTP
from apps.accounts.utils import hash_token, hash_password, generate_otp, generate_reset_token

User = get_user_model()


class SignupView(APIView):
    """User signup endpoint."""
    permission_classes = [AllowAny]
    throttle_classes = [SignupRateThrottle]
    
    @extend_schema(
        summary="User Signup",
        description="Create a new user account with device registration and onboarding setup.",
        request=SignupSerializer,
        responses={
            200: {
                'description': 'User created successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'user': {'id': 'uuid', 'name': 'John Doe', 'email': 'john@example.com'},
                            'accessToken': 'eyJ...',
                            'refreshToken': 'eyJ...',
                            'deviceId': 'uuid',
                            'onboarding': {
                                'currentStep': 'SECURITY_METHOD',
                                'lockMethod': None,
                                'lockEnabled': False,
                                'biometricEnabled': False,
                                'completed': False
                            }
                        }
                    }
                }
            },
            400: {'description': 'Validation error'}
        }
    )
    def post(self, request):
        """Handle user signup."""
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = serializer.save()
        user = result['user']
        device = result['device']
        onboarding = result['onboarding']
        
        # Generate email verification OTP
        otp = generate_otp(length=6)
        otp_hash = hash_token(otp)
        now = timezone.now()
        expires_at = now + timedelta(minutes=10)
        
        # Expire any existing non-consumed OTPs for this user
        EmailVerificationOTP.objects.filter(
            user=user,
            consumed_at__isnull=True,
            expires_at__gt=now
        ).update(consumed_at=now)
        
        # Store new OTP
        EmailVerificationOTP.objects.create(
            user=user,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0
        )
        
        # Send verification email
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'AI Journal - Verify Your Email'
        message = f'''Hello {user.name},

Welcome to AI Journal!

Please verify your email address by entering this OTP code:

{otp}

This OTP will expire in 10 minutes.

If you did not create this account, please ignore this email.

Best regards,
AI Journal Team'''
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            print(f"[EMAIL VERIFICATION] Email sent successfully to: {user.email}, OTP: {otp}")
        except Exception as e:
            # Log error but continue (user can request resend)
            print(f"[EMAIL VERIFICATION] Error sending email to {user.email}: {str(e)}")
            print(f"[EMAIL VERIFICATION] OTP for manual testing: {otp}")
        
        # Generate JWT tokens
        refresh = JWTRefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Store refresh token (30 days)
        expires_at_token = timezone.now() + timedelta(days=30)
        RefreshToken.objects.create(
            user=user,
            device=device,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at_token
        )
        
        # Serialize response
        user_data = UserResponseSerializer(user).data
        onboarding_data = OnboardingResponseSerializer(onboarding).data
        
        return Response({
            'user': user_data,
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'deviceId': str(device.id),
            'emailVerified': False,
            'onboarding': onboarding_data
        }, status=status.HTTP_200_OK)


class LoginView(APIView):
    """User login endpoint."""
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    
    @extend_schema(
        summary="User Login",
        description="Authenticate user and return JWT tokens with device and onboarding info.",
        request=LoginSerializer,
        responses={
            200: {
                'description': 'Login successful',
                'content': {
                    'application/json': {
                        'example': {
                            'user': {'id': 'uuid', 'name': 'John Doe', 'email': 'john@example.com'},
                            'accessToken': 'eyJ...',
                            'refreshToken': 'eyJ...',
                            'deviceId': 'uuid',
                            'onboarding': {
                                'currentStep': 'SECURITY_METHOD',
                                'lockMethod': None,
                                'lockEnabled': False,
                                'biometricEnabled': False,
                                'completed': False
                            }
                        }
                    }
                }
            },
            400: {'description': 'Invalid credentials'}
        }
    )
    def post(self, request):
        """Handle user login."""
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        user = validated_data['user']
        device_data = validated_data['device']
        remember_me = validated_data.get('rememberMe', True)
        
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
        
        # Update last_seen_at
        device.update_last_seen()
        
        # Get or create onboarding
        onboarding, _ = Onboarding.objects.get_or_create(
            user=user,
            defaults={'current_step': 'SECURITY_METHOD'}
        )
        
        # Generate JWT tokens
        refresh = JWTRefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Store refresh token (30 days if rememberMe, else 7 days)
        expires_days = 30 if remember_me else 7
        expires_at = timezone.now() + timedelta(days=expires_days)
        RefreshToken.objects.create(
            user=user,
            device=device,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at
        )
        
        # Serialize response
        user_data = UserResponseSerializer(user).data
        onboarding_data = OnboardingResponseSerializer(onboarding).data
        
        return Response({
            'user': user_data,
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'deviceId': str(device.id),
            'onboarding': onboarding_data
        }, status=status.HTTP_200_OK)


class BiometricLoginView(APIView):
    """Biometric/PIN login endpoint."""
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    
    @extend_schema(
        summary="Biometric/PIN Login",
        description="Login using biometric or PIN. Requires valid refresh token from previous password login.",
        request=BiometricLoginSerializer,
        responses={
            200: {
                'description': 'Login successful',
                'content': {
                    'application/json': {
                        'example': {
                            'user': {'id': 'uuid', 'name': 'John Doe', 'email': 'john@example.com'},
                            'accessToken': 'eyJ...',
                            'refreshToken': 'eyJ...',
                            'deviceId': 'uuid',
                            'onboarding': {
                                'currentStep': 'DONE',
                                'lockMethod': 'PIN',
                                'lockEnabled': True,
                                'biometricEnabled': True,
                                'completed': True
                            }
                        }
                    }
                }
            },
            401: {'description': 'No valid session. Please login with password.'},
            400: {'description': 'Biometric/PIN not set up or validation error'}
        }
    )
    def post(self, request):
        """Handle biometric/PIN login."""
        serializer = BiometricLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        user = validated_data['user']
        device_data = validated_data['device']
        login_method = validated_data.get('loginMethod', 'BIOMETRIC')
        
        # Find device
        os_version = device_data.get('osVersion') or device_data.get('os_version')
        app_version = device_data.get('appVersion') or device_data.get('app_version')
        
        device = Device.objects.filter(
            user=user,
            fingerprint=device_data['fingerprint']
        ).first()
        
        if not device:
            return Response(
                {'error': {'code': 'DEVICE_NOT_FOUND', 'message': 'Device not registered. Please login with password first.'}},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if device has valid refresh token (proves previous password login)
        now = timezone.now()
        refresh_token_obj = RefreshToken.objects.filter(
            user=user,
            device=device,
            revoked_at__isnull=True,
            expires_at__gt=now
        ).order_by('-created_at').first()
        
        if not refresh_token_obj:
            # No valid refresh token → Must use password login
            return Response(
                {'error': {'code': 'NO_VALID_SESSION', 'message': 'No valid session found. Please login with password.'}},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if biometric/PIN is enabled
        onboarding = Onboarding.objects.filter(user=user).first()
        if not onboarding:
            return Response(
                {'error': {'code': 'NOT_SETUP', 'message': 'Security not set up. Please login with password.'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify login method is enabled
        if login_method == 'BIOMETRIC':
            if not onboarding.biometric_enabled:
                return Response(
                    {'error': {'code': 'NOT_ENABLED', 'message': 'Biometric not enabled. Please use password login.'}},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif login_method == 'PIN':
            if not onboarding.lock_enabled or onboarding.lock_method != 'PIN':
                return Response(
                    {'error': {'code': 'NOT_ENABLED', 'message': 'PIN not set up. Please use password login.'}},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Revoke old refresh token (token rotation)
        refresh_token_obj.revoked_at = now
        refresh_token_obj.save(update_fields=['revoked_at'])
        
        # Generate new JWT tokens
        refresh = JWTRefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)
        
        # Store new refresh token
        expires_days = 30  # Same as rememberMe
        expires_at = now + timedelta(days=expires_days)
        RefreshToken.objects.create(
            user=user,
            device=device,
            token_hash=hash_token(new_refresh_token),
            expires_at=expires_at
        )
        
        # Update device last_seen_at
        device.update_last_seen()
        
        # Serialize response
        user_data = UserResponseSerializer(user).data
        onboarding_data = OnboardingResponseSerializer(onboarding).data
        
        return Response({
            'user': user_data,
            'accessToken': access_token,
            'refreshToken': new_refresh_token,
            'deviceId': str(device.id),
            'onboarding': onboarding_data
        }, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """Refresh token endpoint with token rotation."""
    permission_classes = [AllowAny]
    throttle_classes = [RefreshTokenRateThrottle]
    
    @extend_schema(
        summary="Refresh Access Token",
        description="Refresh access token and rotate refresh token.",
        request=RefreshTokenSerializer,
        responses={
            200: {
                'description': 'Tokens refreshed successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'accessToken': 'eyJ...',
                            'refreshToken': 'eyJ...'
                        }
                    }
                }
            },
            400: {'description': 'Invalid refresh token'}
        }
    )
    def post(self, request):
        """Handle token refresh with rotation."""
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        refresh_token_obj = validated_data['refresh_token_obj']
        old_refresh_token = validated_data['refreshToken']
        device = refresh_token_obj.device
        user = refresh_token_obj.user
        
        # Revoke old token
        refresh_token_obj.revoked_at = timezone.now()
        refresh_token_obj.save(update_fields=['revoked_at'])
        
        # Generate new tokens
        refresh = JWTRefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)
        
        # Store new refresh token (30 days)
        expires_at = timezone.now() + timedelta(days=30)
        RefreshToken.objects.create(
            user=user,
            device=device,
            token_hash=hash_token(new_refresh_token),
            expires_at=expires_at
        )
        
        return Response({
            'accessToken': access_token,
            'refreshToken': new_refresh_token
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Logout endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="User Logout",
        description="Revoke refresh token and logout user.",
        request=LogoutSerializer,
        responses={
            200: {
                'description': 'Logout successful',
                'content': {
                    'application/json': {
                        'example': {'success': True}
                    }
                }
            },
            400: {'description': 'Invalid request'}
        }
    )
    def post(self, request):
        """Handle user logout."""
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        refresh_token_obj = validated_data.get('refresh_token_obj')
        
        # Revoke token if found
        if refresh_token_obj:
            refresh_token_obj.revoked_at = timezone.now()
            refresh_token_obj.save(update_fields=['revoked_at'])
        
        return Response({'success': True}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """Password reset request endpoint (send OTP)."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRequestRateThrottle]
    
    @extend_schema(
        summary="Request Password Reset OTP",
        description="Request a password reset OTP. Returns error if user does not exist.",
        request=PasswordResetRequestSerializer,
        responses={
            200: {
                'description': 'OTP sent (or cooldown active)',
                'content': {
                    'application/json': {
                        'example': {
                            'sent': True,
                            'cooldownSeconds': 60
                        }
                    }
                }
            },
            404: {
                'description': 'User not found',
                'content': {
                    'application/json': {
                        'example': {
                            'error': {
                                'code': 'USER_NOT_FOUND',
                                'message': 'User with this email does not exist.'
                            }
                        }
                    }
                }
            }
        }
    )
    def post(self, request):
        """Handle password reset request."""
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        cooldown_seconds = 60
        
        # Check if user exists - return error if not found
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': {'code': 'USER_NOT_FOUND', 'message': 'User with this email does not exist.'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check cooldown (60 seconds since last OTP request)
        now = timezone.now()
        recent_otp = PasswordResetOTP.objects.filter(
            user=user,
            created_at__gte=now - timedelta(seconds=cooldown_seconds)
        ).first()
        
        if recent_otp:
            # Still in cooldown
            return Response({
                'sent': True,
                'cooldownSeconds': cooldown_seconds
            }, status=status.HTTP_200_OK)
        
        # Generate OTP (6 digits)
        otp = generate_otp(length=6)
        otp_hash = hash_token(otp)
        
        # Expire any existing non-consumed OTPs for this user
        PasswordResetOTP.objects.filter(
            user=user,
            consumed_at__isnull=True,
            expires_at__gt=now
        ).update(consumed_at=now)
        
        # Store new OTP (expires in 10 minutes)
        expires_at = now + timedelta(minutes=10)
        PasswordResetOTP.objects.create(
            user=user,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0
        )
        
        # Send email with OTP
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'AI Journal - Password Reset OTP'
        message = f'''Hello,

You have requested to reset your password for AI Journal.

Your OTP code is: {otp}

This OTP will expire in 10 minutes.

If you did not request this password reset, please ignore this email.

Best regards,
AI Journal Team'''
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            print(f"[PASSWORD RESET OTP] Email sent successfully to: {email}, OTP: {otp}")
        except Exception as e:
            # Log error and return error response
            print(f"[PASSWORD RESET OTP] Error sending email to {email}: {str(e)}")
            print(f"[PASSWORD RESET OTP] OTP for manual testing: {otp}")
            return Response(
                {'error': {'code': 'EMAIL_SEND_FAILED', 'message': 'Failed to send OTP email. Please try again later.'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'sent': True,
            'cooldownSeconds': cooldown_seconds
        }, status=status.HTTP_200_OK)


class PasswordResetVerifyView(APIView):
    """Password reset OTP verification endpoint."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPVerifyRateThrottle]
    
    @extend_schema(
        summary="Verify Password Reset OTP",
        description="Verify OTP and receive reset token.",
        request=PasswordResetVerifySerializer,
        responses={
            200: {
                'description': 'OTP verified successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'resetToken': 'token_string',
                            'expiresIn': 600
                        }
                    }
                }
            },
            400: {'description': 'Invalid or expired OTP'}
        }
    )
    def post(self, request):
        """Handle OTP verification."""
        serializer = PasswordResetVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Invalid or expired OTP'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for test OTP (only in DEBUG mode)
        from django.conf import settings
        if settings.DEBUG and settings.TEST_OTP and otp == settings.TEST_OTP:
            # Test OTP is valid - generate reset token without checking database
            now = timezone.now()
            reset_token = generate_reset_token()
            token_hash = hash_token(reset_token)
            
            # Expire any existing non-consumed reset tokens for this user
            PasswordResetToken.objects.filter(
                user=user,
                consumed_at__isnull=True,
                expires_at__gt=now
            ).update(consumed_at=now)
            
            # Store reset token (expires in 10 minutes)
            expires_at = now + timedelta(minutes=10)
            PasswordResetToken.objects.create(
                user=user,
                token_hash=token_hash,
                expires_at=expires_at
            )
            
            return Response({
                'resetToken': reset_token,
                'expiresIn': 600
            }, status=status.HTTP_200_OK)
        
        # Find valid OTP (not consumed, not expired)
        now = timezone.now()
        otp_obj = PasswordResetOTP.objects.filter(
            user=user,
            consumed_at__isnull=True,
            expires_at__gt=now
        ).order_by('-created_at').first()
        
        if not otp_obj:
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Invalid or expired OTP'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if attempts exceeded
        if otp_obj.attempts >= otp_obj.max_attempts:
            otp_obj.consumed_at = now
            otp_obj.save(update_fields=['consumed_at'])
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Too many attempts. Please request a new OTP.'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify OTP
        otp_hash = hash_token(otp)
        if otp_obj.otp_hash != otp_hash:
            # Increment attempts
            otp_obj.attempts += 1
            if otp_obj.attempts >= otp_obj.max_attempts:
                otp_obj.consumed_at = now
            otp_obj.save(update_fields=['attempts', 'consumed_at'])
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Invalid or expired OTP'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # OTP is valid - mark as consumed
        otp_obj.consumed_at = now
        otp_obj.save(update_fields=['consumed_at'])
        
        # Generate reset token
        reset_token = generate_reset_token()
        token_hash = hash_token(reset_token)
        
        # Expire any existing non-consumed reset tokens for this user
        PasswordResetToken.objects.filter(
            user=user,
            consumed_at__isnull=True,
            expires_at__gt=now
        ).update(consumed_at=now)
        
        # Store reset token (expires in 10 minutes)
        expires_at = now + timedelta(minutes=10)
        PasswordResetToken.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at
        )
        
        return Response({
            'resetToken': reset_token,
            'expiresIn': 600  # 10 minutes in seconds
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """Password reset confirmation endpoint."""
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Confirm Password Reset",
        description="Reset password using reset token.",
        request=PasswordResetConfirmSerializer,
        responses={
            200: {
                'description': 'Password reset successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'user': {
                                'id': 'uuid',
                                'name': 'John Doe',
                                'email': 'john@example.com',
                                'emailVerified': True
                            },
                            'accessToken': 'eyJ...',
                            'refreshToken': 'eyJ...',
                            'deviceId': 'uuid',
                            'emailVerified': True,
                            'onboarding': {
                                'currentStep': 'SECURITY_METHOD',
                                'lockMethod': None,
                                'lockEnabled': False,
                                'biometricEnabled': False,
                                'completed': False
                            }
                        }
                    }
                }
            },
            400: {'description': 'Invalid or expired reset token'}
        }
    )
    def post(self, request):
        """Handle password reset confirmation."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                f"Password reset confirm validation failed: {serializer.errors}",
                extra={'request_data': request.data}
            )
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reset_token = serializer.validated_data['resetToken']
        new_password = serializer.validated_data['newPassword']
        token_hash = hash_token(reset_token)
        
        # Find valid reset token
        now = timezone.now()
        try:
            reset_token_obj = PasswordResetToken.objects.get(
                token_hash=token_hash,
                consumed_at__isnull=True,
                expires_at__gt=now
            )
        except PasswordResetToken.DoesNotExist:
            # Check if token exists but is consumed or expired
            error_message = 'Invalid or expired reset token.'
            error_code = 'INVALID_TOKEN'
            
            try:
                consumed_token = PasswordResetToken.objects.get(token_hash=token_hash)
                if consumed_token.consumed_at:
                    error_message = 'Reset token has already been used. Please request a new password reset.'
                    error_code = 'TOKEN_ALREADY_USED'
                    logger.warning(
                        f"Password reset token already consumed for user {consumed_token.user.email}",
                        extra={'token_hash': token_hash[:10] + '...'}
                    )
                elif consumed_token.expires_at <= now:
                    error_message = 'Reset token has expired. Please request a new password reset.'
                    error_code = 'TOKEN_EXPIRED'
                    logger.warning(
                        f"Password reset token expired for user {consumed_token.user.email}",
                        extra={'token_hash': token_hash[:10] + '...', 'expires_at': consumed_token.expires_at}
                    )
            except PasswordResetToken.DoesNotExist:
                logger.warning(
                    f"Password reset token not found",
                    extra={'token_hash': token_hash[:10] + '...'}
                )
            
            return Response(
                {'error': {'code': error_code, 'message': error_message}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = reset_token_obj.user
        
        # Update password
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        # Mark token as consumed
        reset_token_obj.consumed_at = now
        reset_token_obj.save(update_fields=['consumed_at'])
        
        # Revoke all refresh tokens for user (recommended for security)
        RefreshToken.objects.filter(
            user=user,
            revoked_at__isnull=True
        ).update(revoked_at=now)
        
        # Get or create onboarding
        onboarding, _ = Onboarding.objects.get_or_create(
            user=user,
            defaults={'current_step': 'SECURITY_METHOD'}
        )
        
        # Get user's most recent device (or first device if multiple)
        device = Device.objects.filter(user=user).order_by('-last_seen_at', '-created_at').first()
        
        # Generate new JWT tokens
        refresh = JWTRefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Store refresh token (30 days) - only if device exists
        if device:
            expires_at_token = timezone.now() + timedelta(days=30)
            RefreshToken.objects.create(
                user=user,
                device=device,
                token_hash=hash_token(refresh_token),
                expires_at=expires_at_token
            )
        
        # Serialize response (same format as signup)
        user_data = UserResponseSerializer(user).data
        onboarding_data = OnboardingResponseSerializer(onboarding).data
        
        return Response({
            'user': user_data,
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'deviceId': str(device.id) if device else None,
            'emailVerified': user.email_verified,
            'onboarding': onboarding_data
        }, status=status.HTTP_200_OK)


class EmailVerificationView(APIView):
    """Email verification endpoint."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPVerifyRateThrottle]
    
    @extend_schema(
        summary="Verify Email with OTP",
        description="Verify user email address using OTP sent during signup.",
        request=EmailVerificationSerializer,
        responses={
            200: {
                'description': 'Email verified successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'verified': True,
                            'message': 'Email verified successfully'
                        }
                    }
                }
            },
            400: {'description': 'Invalid or expired OTP'}
        }
    )
    def post(self, request):
        """Handle email verification."""
        serializer = EmailVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        user = validated_data['user']
        otp = validated_data['otp']
        
        # Check for test OTP (only in DEBUG mode)
        from django.conf import settings
        if settings.DEBUG and settings.TEST_OTP and otp == settings.TEST_OTP:
            # Test OTP is valid - verify email without checking database
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=['email_verified', 'email_verified_at'])
            return Response({
                'verified': True,
                'message': 'Email verified successfully (test OTP)'
            }, status=status.HTTP_200_OK)
        
        # Check if already verified
        if user.email_verified:
            return Response({
                'verified': True,
                'message': 'Email already verified'
            }, status=status.HTTP_200_OK)
        
        # Find valid OTP
        now = timezone.now()
        otp_obj = EmailVerificationOTP.objects.filter(
            user=user,
            consumed_at__isnull=True,
            expires_at__gt=now
        ).order_by('-created_at').first()
        
        if not otp_obj:
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Invalid or expired OTP'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if attempts exceeded
        if otp_obj.attempts >= otp_obj.max_attempts:
            otp_obj.consumed_at = now
            otp_obj.save(update_fields=['consumed_at'])
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Too many attempts. Please request a new OTP.'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify OTP
        otp_hash = hash_token(otp)
        if otp_obj.otp_hash != otp_hash:
            # Increment attempts
            otp_obj.attempts += 1
            if otp_obj.attempts >= otp_obj.max_attempts:
                otp_obj.consumed_at = now
            otp_obj.save(update_fields=['attempts', 'consumed_at'])
            return Response(
                {'error': {'code': 'INVALID_OTP', 'message': 'Invalid or expired OTP'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # OTP is valid - verify email
        otp_obj.consumed_at = now
        otp_obj.save(update_fields=['consumed_at'])
        
        user.email_verified = True
        user.email_verified_at = now
        user.save(update_fields=['email_verified', 'email_verified_at'])
        
        return Response({
            'verified': True,
            'message': 'Email verified successfully'
        }, status=status.HTTP_200_OK)


class ResendVerificationView(APIView):
    """Resend email verification OTP endpoint."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRequestRateThrottle]
    
    @extend_schema(
        summary="Resend Email Verification OTP",
        description="Resend email verification OTP. Always returns 200.",
        request=ResendVerificationSerializer,
        responses={
            200: {
                'description': 'OTP sent (or cooldown active)',
                'content': {
                    'application/json': {
                        'example': {
                            'sent': True,
                            'cooldownSeconds': 60
                        }
                    }
                }
            }
        }
    )
    def post(self, request):
        """Handle resend verification request."""
        serializer = ResendVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        user = validated_data['user']
        email = user.email
        cooldown_seconds = 60
        
        # Check if already verified
        if user.email_verified:
            return Response({
                'sent': True,
                'message': 'Email already verified',
                'cooldownSeconds': 0
            }, status=status.HTTP_200_OK)
        
        # Check cooldown (60 seconds since last OTP request)
        now = timezone.now()
        recent_otp = EmailVerificationOTP.objects.filter(
            user=user,
            created_at__gte=now - timedelta(seconds=cooldown_seconds)
        ).first()
        
        if recent_otp:
            # Still in cooldown
            return Response({
                'sent': True,
                'cooldownSeconds': cooldown_seconds
            }, status=status.HTTP_200_OK)
        
        # Generate OTP (6 digits)
        otp = generate_otp(length=6)
        otp_hash = hash_token(otp)
        
        # Expire any existing non-consumed OTPs for this user
        EmailVerificationOTP.objects.filter(
            user=user,
            consumed_at__isnull=True,
            expires_at__gt=now
        ).update(consumed_at=now)
        
        # Store new OTP (expires in 10 minutes)
        expires_at = now + timedelta(minutes=10)
        EmailVerificationOTP.objects.create(
            user=user,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0
        )
        
        # Send email with OTP
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'AI Journal - Verify Your Email'
        message = f'''Hello {user.name},

You have requested a new verification code for AI Journal.

Your OTP code is: {otp}

This OTP will expire in 10 minutes.

If you did not request this verification code, please ignore this email.

Best regards,
AI Journal Team'''
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            print(f"[EMAIL VERIFICATION] Email sent successfully to: {email}, OTP: {otp}")
        except Exception as e:
            # Log error but still return success
            print(f"[EMAIL VERIFICATION] Error sending email to {email}: {str(e)}")
            print(f"[EMAIL VERIFICATION] OTP for manual testing: {otp}")
        
        return Response({
            'sent': True,
            'cooldownSeconds': cooldown_seconds
        }, status=status.HTTP_200_OK)
