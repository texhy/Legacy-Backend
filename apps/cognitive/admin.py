"""
Admin configuration for cognitive app.
"""
from django.contrib import admin
from apps.cognitive.models import FriendProfile, Entity, EntityMention


@admin.register(FriendProfile)
class FriendProfileAdmin(admin.ModelAdmin):
    """Admin interface for FriendProfile model."""
    list_display = ['user', 'created_at', 'updated_at']
    search_fields = ['user__email', 'user__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    """Admin interface for Entity model."""
    list_display = ['name', 'entity_type', 'user', 'relationship_to_user', 'mention_count', 'importance_score']
    list_filter = ['entity_type', 'first_mentioned_at']
    search_fields = ['name', 'user__email']
    readonly_fields = ['id', 'first_mentioned_at', 'last_mentioned_at', 'mention_count']


@admin.register(EntityMention)
class EntityMentionAdmin(admin.ModelAdmin):
    """Admin interface for EntityMention model."""
    list_display = ['entity', 'fact_preview', 'confidence', 'sentiment', 'created_at']
    list_filter = ['entity__entity_type', 'created_at']
    search_fields = ['fact_snippet', 'entity__name']
    readonly_fields = ['id', 'created_at']
    
    def fact_preview(self, obj):
        return obj.fact_snippet[:50] + '...' if len(obj.fact_snippet) > 50 else obj.fact_snippet
    fact_preview.short_description = 'Fact'
