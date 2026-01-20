"""
URL configuration for onboarding app.
"""
from django.urls import path
from apps.onboarding.views import (
    OnboardingStatusView,
    SetLockMethodView,
    SetPasscodeView,
    SetBiometricView,
    CompleteOnboardingView,
)

app_name = 'onboarding'

urlpatterns = [
    path('status', OnboardingStatusView.as_view(), name='status'),
    path('security/method', SetLockMethodView.as_view(), name='set-lock-method'),
    path('security/passcode', SetPasscodeView.as_view(), name='set-passcode'),
    path('security/biometric', SetBiometricView.as_view(), name='set-biometric'),
    path('complete', CompleteOnboardingView.as_view(), name='complete'),
]
