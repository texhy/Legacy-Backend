"""
Utility functions for authentication, password hashing, and token management.
"""
import hashlib
import secrets
from django.contrib.auth.hashers import make_password, check_password
from argon2 import PasswordHasher


# Argon2 password hasher instance
_argon2_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash password using Django's password hashing (Argon2 by default).
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    return make_password(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against hash using Django's password checking.
    
    Args:
        password: Plain text password
        password_hash: Hashed password string
        
    Returns:
        True if password matches, False otherwise
    """
    return check_password(password, password_hash)


def hash_token(token: str) -> str:
    """
    Hash token using SHA256.
    
    This is used for storing refresh tokens, OTPs, and reset tokens
    in the database. We hash them to prevent plaintext storage.
    
    Args:
        token: Plain text token
        
    Returns:
        SHA256 hash of the token (hexadecimal string)
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def generate_otp(length: int = 6) -> str:
    """
    Generate a random OTP (One-Time Password).
    
    Args:
        length: Length of OTP (default: 6)
        
    Returns:
        Random numeric OTP string
    """
    # Generate random digits
    otp = ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    return otp


def generate_reset_token() -> str:
    """
    Generate a random reset token for password reset flow.
    
    Returns:
        Random URL-safe token string
    """
    return secrets.token_urlsafe(32)
