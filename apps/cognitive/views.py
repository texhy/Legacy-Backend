"""
Views for cognitive models (FriendProfile, Entity).
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.cognitive.models import FriendProfile, Entity
from apps.cognitive.serializers import FriendProfileSerializer, EntitySerializer


class FriendProfileView(APIView):
    """Get AI's understanding of the user."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Friend Profile",
        description="Get the AI's global understanding of the user across all libraries.",
        responses={
            200: FriendProfileSerializer,
            404: {'description': 'Friend profile not found'}
        }
    )
    def get(self, request):
        """Get friend profile."""
        try:
            profile = FriendProfile.objects.get(user=request.user)
        except FriendProfile.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Friend profile not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = FriendProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EntityListView(APIView):
    """List all remembered entities."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List Entities",
        description="Get all entities the AI remembers about the user.",
        responses={
            200: EntitySerializer(many=True)
        }
    )
    def get(self, request):
        """List entities."""
        entities = Entity.objects.filter(user=request.user).order_by('-importance_score', '-last_mentioned_at')
        serializer = EntitySerializer(entities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EntityDetailView(APIView):
    """Get entity details with mentions."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Entity Detail",
        description="Get entity details including all mentions.",
        responses={
            200: EntitySerializer,
            404: {'description': 'Entity not found'}
        }
    )
    def get(self, request, entity_id):
        """Get entity detail."""
        try:
            entity = Entity.objects.get(id=entity_id, user=request.user)
        except Entity.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Entity not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = EntitySerializer(entity)
        return Response(serializer.data, status=status.HTTP_200_OK)
