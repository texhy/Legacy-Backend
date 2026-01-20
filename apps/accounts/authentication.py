"""
Custom JWT authentication backend.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that extracts user_id from token payload.
    
    This extends the default JWTAuthentication to ensure proper user
    identification from JWT tokens.
    """
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        
        Args:
            validated_token: The validated token payload
            
        Returns:
            User instance
            
        Raises: 
            InvalidToken: If user cannot be found or token is invalid
        """
        try:
            user_id = validated_token.get('user_id')
        except KeyError:
            raise InvalidToken(_('Token contained no recognizable user identification'))
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise InvalidToken(_('User not found'))
        
        if not user.is_active:
            raise InvalidToken(_('User is inactive'))
        
        return user
