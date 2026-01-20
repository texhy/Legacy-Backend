"""
Rate limiting throttle classes for authentication endpoints.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """
    Throttle for login endpoint.
    Limits: 10 requests per minute per IP address.
    """
    rate = '10/min'
    scope = 'login'


class OTPRequestRateThrottle(AnonRateThrottle):
    """
    Throttle for OTP request endpoint.
    Limits: 3 requests per minute per email+IP combination.
    """
    rate = '3/min'
    scope = 'otp_request'
    
    def get_cache_key(self, request, view):
        """
        Generate cache key based on email and IP address.
        This ensures rate limiting per email+IP combination.
        """
        if request.user.is_authenticated:
            ident = request.user.id
        else:
            # Use email from request body + IP address
            email = getattr(request, 'data', {}).get('email', '')
            ident = f"{email}:{self.get_ident(request)}"
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class OTPVerifyRateThrottle(AnonRateThrottle):
    """
    Throttle for OTP verification endpoint.
    Limits: 5 requests per minute per email+IP combination.
    """
    rate = '5/min'
    scope = 'otp_verify'
    
    def get_cache_key(self, request, view):
        """
        Generate cache key based on email and IP address.
        This ensures rate limiting per email+IP combination.
        """
        if request.user.is_authenticated:
            ident = request.user.id
        else:
            # Use email from request body + IP address
            email = getattr(request, 'data', {}).get('email', '')
            ident = f"{email}:{self.get_ident(request)}"
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class SignupRateThrottle(AnonRateThrottle):
    """
    Throttle for signup endpoint.
    Limits: 5 requests per minute per IP address.
    """
    rate = '5/min'
    scope = 'signup'


class RefreshTokenRateThrottle(UserRateThrottle):
    """
    Throttle for refresh token endpoint.
    Limits: 20 requests per minute per user.
    """
    rate = '20/min'
    scope = 'refresh_token'
