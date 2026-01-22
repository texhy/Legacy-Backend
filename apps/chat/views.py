"""
Views for chat messages.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.chat.models import Message
from apps.chat.serializers import MessageSerializer
from apps.libraries.models import Chapter


class MessagePagination(PageNumberPagination):
    """Pagination for message list views."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ChapterMessagesView(APIView):
    """List messages in a chapter."""
    permission_classes = [IsAuthenticated]
    pagination_class = MessagePagination
    
    @extend_schema(
        summary="List Messages by Chapter",
        description="Get paginated list of messages in a specific chapter.",
        parameters=[
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Items per page',
                required=False
            ),
        ],
        responses={
            200: MessageSerializer(many=True),
            404: {'description': 'Chapter not found'}
        }
    )
    def get(self, request, chapter_id):
        """List messages in a chapter."""
        try:
            chapter = Chapter.objects.get(id=chapter_id, library__user=request.user)
        except Chapter.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Chapter not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        queryset = Message.objects.filter(chapter=chapter).order_by('timestamp')
        
        # Paginate
        paginator = MessagePagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback if pagination is disabled
        serializer = MessageSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
