"""
URL configuration for accounts app.
"""
from django.urls import path
from apps.accounts.views import (
    SignupView,
    LoginView,
    BiometricLoginView,
    RefreshTokenView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
    EmailVerificationView,
    ResendVerificationView,
)

app_name = 'accounts'

urlpatterns = [
    path('signup', SignupView.as_view(), name='signup'),
    path('login', LoginView.as_view(), name='login'),
    path('login/biometric', BiometricLoginView.as_view(), name='login-biometric'),
    path('refresh', RefreshTokenView.as_view(), name='refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('password-reset/request', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/verify', PasswordResetVerifyView.as_view(), name='password-reset-verify'),
    path('password-reset/confirm', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-email', EmailVerificationView.as_view(), name='verify-email'),
    path('resend-verification', ResendVerificationView.as_view(), name='resend-verification'),
]
