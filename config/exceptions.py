"""
Custom exception handler for consistent API error responses.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error format.
    
    Returns:
        {
            "error": {
                "code": <status_code>,
                "message": <error_message>
            }
        }
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        # Get the error message
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                # Handle ValidationError with field-specific errors
                error_messages = []
                for field, messages in exc.detail.items():
                    if isinstance(messages, list):
                        error_messages.extend([f"{field}: {msg}" for msg in messages])
                    else:
                        error_messages.append(f"{field}: {messages}")
                error_message = "; ".join(error_messages) if error_messages else str(exc)
            else:
                error_message = str(exc.detail)
        else:
            error_message = str(exc)
        
        custom_response_data = {
            'error': {
                'code': response.status_code,
                'message': error_message
            }
        }
        response.data = custom_response_data
    
    return response

