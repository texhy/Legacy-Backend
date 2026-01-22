"""
Entity Resolution Service - The 'Jane Logic'

Resolves entity mentions to existing entities or creates new ones.
Uses fuzzy matching to handle name variations and aliases.
"""
from typing import Optional, Tuple
from django.utils import timezone
from django.db.models import F
from fuzzywuzzy import fuzz

from apps.cognitive.models import Entity, EntityMention


class EntityResolver:
    """
    Resolves entity mentions to existing or new entities.
    
    The 'Jane Logic':
    1. Exact match on normalized name
    2. Fuzzy match on name (>85% similarity)
    3. Check aliases for matches
    4. Create new entity if no match found
    """
    
    # Minimum similarity score to consider a match
    SIMILARITY_THRESHOLD = 85
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def resolve(
        self,
        entity_name: str,
        entity_type: str,
        fact: str = "",
        relationship: str = "",
        sentiment_score: float = 0.0
    ) -> Tuple[Entity, bool]:
        """
        Resolve an entity mention to an existing or new entity.
        
        Args:
            entity_name: The name mentioned (e.g., "Jane", "my sister Jane")
            entity_type: Type of entity (PERSON, LOCATION, ORG, etc.)
            fact: Optional fact about the entity
            relationship: Optional relationship to user
            sentiment_score: Sentiment of this mention (-1 to 1)
        
        Returns:
            Tuple of (Entity, was_created: bool)
        """
        normalized_name = self._normalize_name(entity_name)
        
        # 1. Try exact match
        entity = self._exact_match(normalized_name, entity_type)
        if entity:
            self._update_existing(entity, entity_name, fact, relationship, sentiment_score)
            return entity, False
        
        # 2. Try fuzzy match on name
        entity = self._fuzzy_match_name(normalized_name, entity_type)
        if entity:
            self._add_alias_if_new(entity, entity_name)
            self._update_existing(entity, entity_name, fact, relationship, sentiment_score)
            return entity, False
        
        # 3. Try fuzzy match on aliases
        entity = self._fuzzy_match_aliases(normalized_name, entity_type)
        if entity:
            self._add_alias_if_new(entity, entity_name)
            self._update_existing(entity, entity_name, fact, relationship, sentiment_score)
            return entity, False
        
        # 4. Create new entity
        entity = self._create_new(
            entity_name=entity_name,
            normalized_name=normalized_name,
            entity_type=entity_type,
            fact=fact,
            relationship=relationship,
            sentiment_score=sentiment_score
        )
        return entity, True
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a name for matching."""
        # Remove common prefixes
        prefixes = ['my ', 'the ', 'a ', 'our ']
        normalized = name.lower().strip()
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        return normalized.strip()
    
    def _exact_match(self, normalized_name: str, entity_type: str) -> Optional[Entity]:
        """Find exact match on normalized name."""
        return Entity.objects.filter(
            user_id=self.user_id,
            name_normalized=normalized_name,
            entity_type=entity_type
        ).first()
    
    def _fuzzy_match_name(self, normalized_name: str, entity_type: str) -> Optional[Entity]:
        """Find fuzzy match on entity names."""
        entities = Entity.objects.filter(
            user_id=self.user_id,
            entity_type=entity_type
        )
        
        best_match = None
        best_score = 0
        
        for entity in entities:
            score = fuzz.ratio(normalized_name, entity.name_normalized)
            if score > self.SIMILARITY_THRESHOLD and score > best_score:
                best_match = entity
                best_score = score
        
        return best_match
    
    def _fuzzy_match_aliases(self, normalized_name: str, entity_type: str) -> Optional[Entity]:
        """Find fuzzy match on entity aliases."""
        entities = Entity.objects.filter(
            user_id=self.user_id,
            entity_type=entity_type
        )
        
        for entity in entities:
            aliases = entity.aliases or []
            for alias in aliases:
                score = fuzz.ratio(normalized_name, alias.lower())
                if score > self.SIMILARITY_THRESHOLD:
                    return entity
        
        return None
    
    def _add_alias_if_new(self, entity: Entity, entity_name: str):
        """Add entity_name as alias if not already present."""
        aliases = entity.aliases or []
        if entity_name not in aliases and entity_name.lower() not in [a.lower() for a in aliases]:
            aliases.append(entity_name)
            entity.aliases = aliases
            entity.save(update_fields=['aliases'])
    
    def _update_existing(
        self,
        entity: Entity,
        entity_name: str,
        fact: str,
        relationship: str,
        sentiment_score: float
    ):
        """Update an existing entity with new information."""
        # Update mention count and timestamp
        entity.mention_count = F('mention_count') + 1
        entity.last_mentioned_at = timezone.now()
        
        # Update relationship if provided and not already set
        if relationship and not entity.relationship_to_user:
            entity.relationship_to_user = relationship
        
        # Blend sentiment score (moving average)
        if sentiment_score != 0:
            entity.sentiment_score = (entity.sentiment_score + sentiment_score) / 2
        
        # Update summary if fact provides new information
        if fact and fact not in (entity.summary or ''):
            current_summary = entity.summary or ''
            # Append new fact if summary is short enough
            if len(current_summary) < 500:
                entity.summary = f"{current_summary}\n• {fact}".strip()
        
        # Increase importance based on frequency
        entity.importance_score = min(1.0, entity.importance_score + 0.05)
        
        entity.save()
        entity.refresh_from_db()
    
    def _create_new(
        self,
        entity_name: str,
        normalized_name: str,
        entity_type: str,
        fact: str,
        relationship: str,
        sentiment_score: float
    ) -> Entity:
        """Create a new entity."""
        return Entity.objects.create(
            user_id=self.user_id,
            name=entity_name,
            name_normalized=normalized_name,
            entity_type=entity_type,
            aliases=[entity_name],
            summary=fact if fact else '',
            relationship_to_user=relationship or '',
            sentiment_score=sentiment_score,
            importance_score=0.5,
            mention_count=1
        )


def resolve_entity(
    user_id: str,
    entity_name: str,
    entity_type: str,
    fact: str = "",
    relationship: str = "",
    sentiment_score: float = 0.0
) -> Tuple[Entity, bool]:
    """
    Convenience function for entity resolution.
    
    Returns:
        Tuple of (Entity, was_created: bool)
    """
    resolver = EntityResolver(user_id)
    return resolver.resolve(
        entity_name=entity_name,
        entity_type=entity_type,
        fact=fact,
        relationship=relationship,
        sentiment_score=sentiment_score
    )


def find_entity_by_name(user_id: str, name: str) -> Optional[Entity]:
    """
    Find an entity by name (exact or fuzzy match).
    Used for context lookup during chat.
    """
    resolver = EntityResolver(user_id)
    normalized = resolver._normalize_name(name)
    
    # Try exact match first (any type)
    entity = Entity.objects.filter(
        user_id=user_id,
        name_normalized=normalized
    ).first()
    
    if entity:
        return entity
    
    # Try fuzzy match
    entities = Entity.objects.filter(user_id=user_id)
    for entity in entities:
        if fuzz.ratio(normalized, entity.name_normalized) > 85:
            return entity
        for alias in (entity.aliases or []):
            if fuzz.ratio(normalized, alias.lower()) > 85:
                return entity
    
    return None
