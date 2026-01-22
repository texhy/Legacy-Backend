"""
ASGI config for ai-journal project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import routing after Django setup
from config.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    # Note: AllowedHostsOriginValidator removed because:
    # 1. Mobile apps don't send Origin headers
    # 2. JWT authentication provides security
    # 3. Postman testing doesn't send correct Origin
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

