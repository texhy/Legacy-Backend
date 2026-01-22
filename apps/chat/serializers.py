"""
Serializers for chat messages.
"""
from rest_framework import serializers
from apps.chat.models import Message


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for message responses."""
    chapterId = serializers.UUIDField(source='chapter_id', read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'chapterId', 'sender', 'content', 
            'metadata', 'is_complete', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']
