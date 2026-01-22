"""
Cognitive models for AI understanding and entity tracking.
"""
import uuid
import json
from django.db import models
from django.utils import timezone


class FriendProfile(models.Model):
    """
    The AI's GLOBAL understanding of the user across ALL libraries.
    This is what makes the AI feel like a friend who knows you everywhere.
    
    KEY INSIGHT: FriendProfile is attached to USER, not Library.
    If user talks about "Jane" in Personal Library, AI knows about her
    when they open Finance Library.
    """
    
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='friend_profile'
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: META (Basic Info)
    # ═══════════════════════════════════════════════════════════════════
    meta = models.JSONField(default=dict, help_text='''
        {
            "user_name": "Jason",
            "preferred_name": "Jay",
            "timezone": "Asia/Karachi",
            "last_updated": "2026-01-20T14:30:00",
            "profile_version": "2.0"
        }
    ''')
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2: EMOTIONAL CONTEXT (The Vibe)
    # Updated after every conversation
    # ═══════════════════════════════════════════════════════════════════
    emotional_context = models.JSONField(default=dict, help_text='''
        {
            "current_mood": "Determined but Tired",
            "energy_level": "Low",
            "mood_trend": "stable",
            "active_stressors": [
                "Final Year Project Deadline",
                "AWS Certification Exam"
            ],
            "recent_wins": [
                "Fixed the WebSocket bug",
                "Met Mom for lunch"
            ],
            "emotional_patterns": {
                "typically_stressed_about": ["deadlines", "finances"],
                "energized_by": ["coding wins", "family time"],
                "calmed_by": ["walks", "music"]
            }
        }
    ''')
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 3: LIFE NARRATIVE (The Big Picture)
    # Aggregated from ALL Library summaries (Daily Cron Job)
    # ═══════════════════════════════════════════════════════════════════
    life_narrative = models.JSONField(default=dict, help_text='''
        {
            "current_chapter_of_life": "Building the Legacy Startup while finishing University",
            "core_values": [
                "Family Legacy",
                "Financial Independence", 
                "Technical Mastery"
            ],
            "long_term_goals": [
                {"goal": "Launch Legacy App by June 2026", "progress": 0.4},
                {"goal": "Save 1 Crore PKR", "progress": 0.15},
                {"goal": "Graduate with Honors", "progress": 0.8}
            ],
            "life_themes": [
                "Balancing ambition with family responsibilities",
                "Building something meaningful",
                "Growth through technical challenges"
            ],
            "key_relationships": [
                {"name": "Mom", "role": "Primary support system"},
                {"name": "Jane", "role": "Sister, confidant"},
                {"name": "Ahmed", "role": "Co-founder, best friend"}
            ]
        }
    ''')
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 4: INTERACTION STYLE (The Friend Settings)
    # How the AI should communicate with this user
    # ═══════════════════════════════════════════════════════════════════
    interaction_style = models.JSONField(default=dict, help_text='''
        {
            "persona": "Supportive Co-founder",
            "communication_preference": "Direct, Technical, No fluff",
            "humor_style": "dry, tech references",
            "encouragement_style": "realistic optimism",
            "challenge_style": "gentle push",
            "forbidden_topics": ["Ex-girlfriend", "Father's business failure"],
            "preferred_greetings": "casual",
            "emoji_tolerance": "moderate"
        }
    ''')
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 5: NEXT SESSION PRIMER (The Bridge)
    # AI-generated summary for next conversation opener
    # Updated at end of each session
    # ═══════════════════════════════════════════════════════════════════
    next_session_primer = models.TextField(
        blank=True, 
        default='', 
        help_text='''
        "User is tired from coding all night. Start with a low-energy greeting. 
        If they mention the Legacy app, acknowledge the recent WebSocket bug fix 
        and ask how the testing is going. They seemed stressed about the deadline 
        last time - check in gently."
        '''
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 6: IMPORTANT DATES (Memory Anchors)
    # ═══════════════════════════════════════════════════════════════════
    important_dates = models.JSONField(default=list, help_text='''
        [
            {"date": "1998-05-15", "type": "birthday", "note": "User's birthday"},
            {"date": "2026-06-01", "type": "deadline", "note": "Legacy App Launch Target"},
            {"date": "2025-11-10", "type": "loss", "note": "Grandfather passed away"},
            {"date": "2026-01-15", "type": "achievement", "note": "Fixed major WebSocket bug"}
        ]
    ''')
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 7: RELATIONSHIP METRICS (Trust & Depth)
    # ═══════════════════════════════════════════════════════════════════
    relationship_metrics = models.JSONField(default=dict, help_text='''
        {
            "first_interaction": "2024-01-15",
            "total_conversations": 147,
            "total_messages": 2523,
            "topics_explored": ["career", "family", "startup", "health"],
            "emotional_moments_shared": 23,
            "milestones_celebrated": 8,
            "trust_level": 0.85,
            "conversation_depth": "deep",
            "achieved_milestones": ["first_steps", "getting_to_know_you", "trusted_friend"]
        }
    ''')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'friend_profiles'
    
    def get_active_context(self) -> dict:
        """Get the most relevant context for current conversation."""
        return {
            'name': self.meta.get('preferred_name', self.meta.get('user_name', 'friend')),
            'mood': self.emotional_context.get('current_mood', 'neutral'),
            'energy': self.emotional_context.get('energy_level', 'normal'),
            'stressors': self.emotional_context.get('active_stressors', []),
            'recent_wins': self.emotional_context.get('recent_wins', []),
            'persona': self.interaction_style.get('persona', 'Supportive Friend'),
            'comm_style': self.interaction_style.get('communication_preference', 'warm'),
        }
    
    def update_emotional_state(self, mood: str, energy: str, stressors: list = None, wins: list = None):
        """Update the emotional context after a conversation."""
        self.emotional_context['current_mood'] = mood
        self.emotional_context['energy_level'] = energy
        if stressors:
            self.emotional_context['active_stressors'] = stressors
        if wins:
            self.emotional_context['recent_wins'] = wins
        self.save()


class Entity(models.Model):
    """
    Named entities the AI remembers across all conversations.
    These are the "people, places, things" in the user's life.
    """
    
    class EntityType(models.TextChoices):
        PERSON = 'PERSON', 'Person'
        LOCATION = 'LOCATION', 'Location'
        ORGANIZATION = 'ORG', 'Organization'
        EVENT = 'EVENT', 'Event'
        TOPIC = 'TOPIC', 'Topic/Interest'
        DATE = 'DATE', 'Important Date'
        GOAL = 'GOAL', 'Goal/Aspiration'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='entities',
        db_index=True
    )
    
    name = models.CharField(max_length=255, db_index=True)
    name_normalized = models.CharField(
        max_length=255, 
        db_index=True,
        help_text='Lowercase, trimmed for matching'
    )
    aliases = models.JSONField(
        default=list,
        help_text='["Jane", "Jane Smith", "my sister Jane"]'
    )
    
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    
    # Consolidated facts about this entity
    summary = models.TextField(
        blank=True,
        help_text='AI-consolidated summary: "Jane is user\'s sister, works in finance..."'
    )
    
    # Relationship to user
    relationship_to_user = models.CharField(
        max_length=100, 
        blank=True,
        help_text='sister, boss, best friend, hometown, etc.'
    )
    
    # Sentiment tracking
    sentiment_score = models.FloatField(
        default=0.0,
        help_text='-1.0 (negative) to 1.0 (positive)'
    )
    
    # Importance ranking
    importance_score = models.FloatField(
        default=0.5,
        help_text='0.0 (rarely mentioned) to 1.0 (core to user\'s life)'
    )
    
    first_mentioned_at = models.DateTimeField(auto_now_add=True)
    last_mentioned_at = models.DateTimeField(auto_now=True)
    mention_count = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'entities'
        indexes = [
            models.Index(fields=['user', 'name_normalized']),
            models.Index(fields=['user', 'entity_type']),
            models.Index(fields=['user', 'importance_score']),
        ]
        unique_together = ['user', 'name_normalized', 'entity_type']
    
    def __str__(self):
        return f"{self.name} ({self.entity_type}) - {self.user.email}"


class EntityMention(models.Model):
    """
    Individual mentions of entities in messages.
    Provides traceability and context for facts.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey(
        Entity, 
        on_delete=models.CASCADE, 
        related_name='mentions',
        db_index=True
    )
    message = models.ForeignKey(
        'chat.Message', 
        on_delete=models.CASCADE, 
        related_name='entity_mentions',
        db_index=True
    )
    chapter = models.ForeignKey(
        'libraries.Chapter', 
        on_delete=models.CASCADE, 
        related_name='entity_mentions',
        db_index=True
    )
    
    # The actual fact extracted
    fact_snippet = models.TextField(help_text='Jane got promoted to VP')
    
    # Confidence score from NER
    confidence = models.FloatField(default=0.9)
    
    # Sentiment of this specific mention
    sentiment = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'entity_mentions'
        indexes = [
            models.Index(fields=['entity', 'created_at']),
            models.Index(fields=['chapter', 'entity']),
        ]
    
    def __str__(self):
        return f"{self.entity.name}: {self.fact_snippet[:50]}..."
