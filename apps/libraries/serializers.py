"""
Serializers for library and chapter endpoints.
"""
from rest_framework import serializers
from apps.libraries.models import Library, Chapter


class LibrarySerializer(serializers.ModelSerializer):
    """Serializer for library responses."""
    colorTheme = serializers.CharField(source='color_theme', read_only=True)
    isArchived = serializers.BooleanField(source='is_archived', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    class Meta:
        model = Library
        fields = ['id', 'title', 'colorTheme', 'isArchived', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdAt', 'updatedAt']


class LibraryCreateSerializer(serializers.Serializer):
    """Serializer for creating a library."""
    title = serializers.CharField(max_length=255, required=True)
    colorTheme = serializers.CharField(
        max_length=7,
        required=False,
        default='#000000',
        help_text='Hex color code (e.g., #f3242a)'
    )
    
    def validate_colorTheme(self, value):
        """Validate hex color format."""
        if not value.startswith('#'):
            raise serializers.ValidationError("Color must start with #")
        if len(value) != 7:
            raise serializers.ValidationError("Color must be 7 characters (e.g., #f3242a)")
        # Basic hex validation
        try:
            int(value[1:], 16)
        except ValueError:
            raise serializers.ValidationError("Invalid hex color format")
        return value
    
    def create(self, validated_data):
        """Create a new library."""
        user = self.context['request'].user
        color_theme = validated_data.pop('colorTheme', '#000000')
        return Library.objects.create(
            user=user,
            title=validated_data['title'],
            color_theme=color_theme
        )


class LibraryUpdateSerializer(serializers.Serializer):
    """Serializer for updating a library."""
    title = serializers.CharField(max_length=255, required=False)
    colorTheme = serializers.CharField(max_length=7, required=False)
    isArchived = serializers.BooleanField(required=False)
    
    def validate_colorTheme(self, value):
        """Validate hex color format."""
        if value and not value.startswith('#'):
            raise serializers.ValidationError("Color must start with #")
        if value and len(value) != 7:
            raise serializers.ValidationError("Color must be 7 characters (e.g., #f3242a)")
        if value:
            try:
                int(value[1:], 16)
            except ValueError:
                raise serializers.ValidationError("Invalid hex color format")
        return value


class ChapterSerializer(serializers.ModelSerializer):
    """Serializer for chapter responses (list view - without full content)."""
    contentPreview = serializers.CharField(source='content_preview', read_only=True)
    isArchived = serializers.BooleanField(source='is_archived', read_only=True)
    libraryId = serializers.UUIDField(source='library_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    class Meta:
        model = Chapter
        fields = [
            'id', 'libraryId', 'title', 'contentPreview',
            'isArchived', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['id', 'libraryId', 'createdAt', 'updatedAt']


class ChapterDetailSerializer(serializers.ModelSerializer):
    """Serializer for chapter detail view (includes full content)."""
    contentPreview = serializers.CharField(source='content_preview', read_only=True)
    contentFull = serializers.CharField(source='content_full', read_only=True)
    isArchived = serializers.BooleanField(source='is_archived', read_only=True)
    libraryId = serializers.UUIDField(source='library_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    class Meta:
        model = Chapter
        fields = [
            'id', 'libraryId', 'title', 'contentPreview', 'contentFull',
            'isArchived', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['id', 'libraryId', 'createdAt', 'updatedAt']


class ChapterCreateSerializer(serializers.Serializer):
    """Serializer for creating a chapter."""
    title = serializers.CharField(max_length=255, required=True)
    contentFull = serializers.CharField(required=True)
    contentPreview = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Optional preview text. If not provided, will be auto-generated from contentFull.'
    )
    
    def create(self, validated_data):
        """Create a new chapter."""
        library = self.context['library']
        content_full = validated_data.pop('contentFull')
        content_preview = validated_data.pop('contentPreview', None)
        
        # Auto-generate preview if not provided (first 100 chars)
        if not content_preview:
            content_preview = content_full[:100] + '...' if len(content_full) > 100 else content_full
        
        return Chapter.objects.create(
            library=library,
            title=validated_data['title'],
            content_full=content_full,
            content_preview=content_preview
        )


class ChapterUpdateSerializer(serializers.Serializer):
    """Serializer for updating a chapter."""
    title = serializers.CharField(max_length=255, required=False)
    contentFull = serializers.CharField(required=False)
    contentPreview = serializers.CharField(required=False, allow_blank=True)
    isArchived = serializers.BooleanField(required=False)
