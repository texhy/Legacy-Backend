"""
Views for library and chapter endpoints.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.libraries.models import Library, Chapter
from apps.libraries.serializers import (
    LibrarySerializer,
    LibraryCreateSerializer,
    LibraryUpdateSerializer,
    ChapterSerializer,
    ChapterDetailSerializer,
    ChapterCreateSerializer,
    ChapterUpdateSerializer,
)


class LibraryPagination(PageNumberPagination):
    """Pagination for library list views."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ChapterPagination(PageNumberPagination):
    """Pagination for chapter list views."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LibraryCreateView(APIView):
    """Create a new library."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create Library",
        description="Create a new library with title and theme color.",
        request=LibraryCreateSerializer,
        responses={
            201: LibrarySerializer,
            400: {'description': 'Validation error'}
        }
    )
    def post(self, request):
        """Create a new library."""
        serializer = LibraryCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        library = serializer.save()
        response_serializer = LibrarySerializer(library)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class LibraryListView(APIView):
    """List libraries (active or archived)."""
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination
    
    @extend_schema(
        summary="List Libraries",
        description="Get paginated list of libraries. Filter by status (active/archived).",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by status: "active" or "archived"',
                required=False,
                enum=['active', 'archived']
            ),
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
            200: LibrarySerializer(many=True)
        }
    )
    def get(self, request):
        """List libraries with pagination."""
        user = request.user
        status_filter = request.query_params.get('status', 'active')
        
        # Build queryset
        queryset = Library.objects.filter(user=user)
        
        # Filter by archive status
        if status_filter == 'active':
            queryset = queryset.filter(is_archived=False)
        elif status_filter == 'archived':
            queryset = queryset.filter(is_archived=True)
        # If status is invalid or not provided, default to active
        
        # Paginate
        paginator = LibraryPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = LibrarySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback if pagination is disabled
        serializer = LibrarySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LibraryUpdateView(APIView):
    """Update library (title, color, archive status)."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Update Library",
        description="Update library title, theme color, or archive status.",
        request=LibraryUpdateSerializer,
        responses={
            200: LibrarySerializer,
            400: {'description': 'Validation error'},
            404: {'description': 'Library not found'}
        }
    )
    def patch(self, request, library_id):
        """Update library."""
        try:
            library = Library.objects.get(id=library_id, user=request.user)
        except Library.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Library not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = LibraryUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update fields
        validated_data = serializer.validated_data
        if 'title' in validated_data:
            library.title = validated_data['title']
        if 'colorTheme' in validated_data:
            library.color_theme = validated_data['colorTheme']
        if 'isArchived' in validated_data:
            library.is_archived = validated_data['isArchived']
        
        library.save()
        
        response_serializer = LibrarySerializer(library)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ChapterCreateView(APIView):
    """Create a new chapter in a library."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create Chapter",
        description="Create a new chapter in a library.",
        request=ChapterCreateSerializer,
        responses={
            201: ChapterSerializer,
            400: {'description': 'Validation error'},
            404: {'description': 'Library not found'}
        }
    )
    def post(self, request, library_id):
        """Create a new chapter."""
        try:
            library = Library.objects.get(id=library_id, user=request.user)
        except Library.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Library not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ChapterCreateSerializer(data=request.data, context={'library': library})
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        chapter = serializer.save()
        response_serializer = ChapterSerializer(chapter)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ChapterListView(APIView):
    """List chapters in a library."""
    permission_classes = [IsAuthenticated]
    pagination_class = ChapterPagination
    
    @extend_schema(
        summary="List Chapters by Library",
        description="Get paginated list of chapters in a specific library.",
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
            200: ChapterSerializer(many=True),
            404: {'description': 'Library not found'}
        }
    )
    def get(self, request, library_id):
        """List chapters in a library."""
        try:
            library = Library.objects.get(id=library_id, user=request.user)
        except Library.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Library not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        queryset = Chapter.objects.filter(library=library, is_archived=False)
        
        # Paginate
        paginator = ChapterPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = ChapterSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback if pagination is disabled
        serializer = ChapterSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChapterRecentView(APIView):
    """Get recent chapters across all libraries (for Home Page)."""
    permission_classes = [IsAuthenticated]
    pagination_class = ChapterPagination
    
    @extend_schema(
        summary="Get Recent Chapters",
        description="Get paginated list of recent chapters across all user's libraries, sorted by updated_at.",
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
            200: ChapterSerializer(many=True)
        }
    )
    def get(self, request):
        """Get recent chapters."""
        user = request.user
        
        # Get all libraries for user
        libraries = Library.objects.filter(user=user, is_archived=False)
        
        # Get recent chapters from all active libraries
        queryset = Chapter.objects.filter(
            library__in=libraries,
            is_archived=False
        ).order_by('-updated_at')
        
        # Paginate
        paginator = ChapterPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = ChapterSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback if pagination is disabled
        serializer = ChapterSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChapterDetailView(APIView):
    """Get, update, or delete a chapter."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Chapter Detail",
        description="Get chapter details including full content.",
        responses={
            200: ChapterDetailSerializer,
            404: {'description': 'Chapter not found'}
        }
    )
    def get(self, request, chapter_id):
        """Get chapter detail."""
        try:
            chapter = Chapter.objects.get(id=chapter_id, library__user=request.user)
        except Chapter.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Chapter not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ChapterDetailSerializer(chapter)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Update Chapter",
        description="Update chapter title, content, or archive status.",
        request=ChapterUpdateSerializer,
        responses={
            200: ChapterDetailSerializer,
            400: {'description': 'Validation error'},
            404: {'description': 'Chapter not found'}
        }
    )
    def patch(self, request, chapter_id):
        """Update chapter."""
        try:
            chapter = Chapter.objects.get(id=chapter_id, library__user=request.user)
        except Chapter.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Chapter not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ChapterUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': {'code': 400, 'message': serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update fields
        if 'title' in serializer.validated_data:
            chapter.title = serializer.validated_data['title']
        if 'contentFull' in serializer.validated_data:
            chapter.content_full = serializer.validated_data['contentFull']
        if 'contentPreview' in serializer.validated_data:
            chapter.content_preview = serializer.validated_data['contentPreview']
        elif 'contentFull' in serializer.validated_data:
            # Auto-update preview if content changed but preview not provided
            content_full = serializer.validated_data['contentFull']
            chapter.content_preview = content_full[:100] + '...' if len(content_full) > 100 else content_full
        if 'isArchived' in serializer.validated_data:
            chapter.is_archived = serializer.validated_data['isArchived']
        
        chapter.save()
        
        response_serializer = ChapterDetailSerializer(chapter)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Delete Chapter",
        description="Hard delete a chapter.",
        responses={
            200: {'description': 'Chapter deleted successfully'},
            404: {'description': 'Chapter not found'}
        }
    )
    def delete(self, request, chapter_id):
        """Delete chapter."""
        try:
            chapter = Chapter.objects.get(id=chapter_id, library__user=request.user)
        except Chapter.DoesNotExist:
            return Response(
                {'error': {'code': 404, 'message': 'Chapter not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        chapter.delete()
        return Response(
            {'success': True, 'message': 'Chapter deleted successfully'},
            status=status.HTTP_200_OK
        )
