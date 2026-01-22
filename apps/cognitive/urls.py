"""
URL configuration for cognitive app.
"""
from django.urls import path
from apps.cognitive.views import (
    FriendProfileView,
    EntityListView,
    EntityDetailView
)

app_name = 'cognitive'

urlpatterns = [
    path('me/friend-profile/', FriendProfileView.as_view(), name='friend-profile'),
    path('me/entities/', EntityListView.as_view(), name='entity-list'),
    path('me/entities/<uuid:entity_id>/', EntityDetailView.as_view(), name='entity-detail'),
]
