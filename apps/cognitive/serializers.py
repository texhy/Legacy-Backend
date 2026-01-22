"""
Serializers for cognitive models (FriendProfile, Entity).
"""
from rest_framework import serializers
from apps.cognitive.models import FriendProfile, Entity, EntityMention


class FriendProfileSerializer(serializers.ModelSerializer):
    """Serializer for FriendProfile."""
    
    class Meta:
        model = FriendProfile
        fields = [
            'meta', 'emotional_context', 'life_narrative',
            'interaction_style', 'next_session_primer',
            'important_dates', 'relationship_metrics',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class EntityMentionSerializer(serializers.ModelSerializer):
    """Serializer for EntityMention."""
    
    class Meta:
        model = EntityMention
        fields = [
            'id', 'fact_snippet', 'confidence', 
            'sentiment', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class EntitySerializer(serializers.ModelSerializer):
    """Serializer for Entity."""
    mentions = EntityMentionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Entity
        fields = [
            'id', 'name', 'entity_type', 'aliases',
            'summary', 'relationship_to_user',
            'sentiment_score', 'importance_score',
            'first_mentioned_at', 'last_mentioned_at',
            'mention_count', 'mentions'
        ]
        read_only_fields = [
            'id', 'first_mentioned_at', 'last_mentioned_at',
            'mention_count'
        ]
