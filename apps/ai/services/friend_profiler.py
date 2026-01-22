"""
Friend Profile Service - Emotional Intelligence for Legacy.

Analyzes conversations and updates the friend profile to make
Legacy feel like a friend who truly knows and understands the user.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from openai import OpenAI

from apps.cognitive.models import FriendProfile
from apps.ai.services.emotion_detector import detect_emotion, detect_life_event

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


class FriendProfiler:
    """
    Analyzes exchanges and updates the FriendProfile.
    
    Updates include:
    - Emotional context (mood, energy, stressors)
    - Interaction metrics (conversation depth, trust level)
    - Important dates (birthdays, achievements, losses)
    - Interests and topics
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile = self._get_or_create_profile()
    
    def _get_or_create_profile(self) -> FriendProfile:
        """Get or create the user's friend profile."""
        profile, created = FriendProfile.objects.get_or_create(
            user_id=self.user_id,
            defaults={
                'meta': {},
                'emotional_context': {
                    'current_mood': 'neutral',
                    'energy_level': 'normal',
                    'mood_trend': 'stable',
                    'active_stressors': [],
                    'recent_wins': [],
                },
                'life_narrative': {},
                'interaction_style': {
                    'persona': 'Supportive Friend',
                    'communication_preference': 'warm and friendly',
                },
                'important_dates': [],
                'relationship_metrics': {
                    'first_interaction': timezone.now().isoformat(),
                    'total_conversations': 0,
                    'total_messages': 0,
                    'trust_level': 0.3,
                    'conversation_depth': 'surface',
                    'achieved_milestones': ['first_steps'],
                },
            }
        )
        return profile
    
    def analyze_and_update(self, exchange: str, emotion: str = None) -> Dict[str, Any]:
        """
        Analyze an exchange and update the profile.
        
        Args:
            exchange: The conversation exchange (User: ... AI: ...)
            emotion: Pre-detected emotion (optional)
        
        Returns:
            Dict of updates made
        """
        updates = {}
        
        # 1. Update emotional context
        emotion_updates = self._update_emotional_context(exchange, emotion)
        if emotion_updates:
            updates['emotional'] = emotion_updates
        
        # 2. Check for life events
        event_updates = self._check_life_events(exchange)
        if event_updates:
            updates['life_event'] = event_updates
        
        # 3. Extract topics/interests
        topic_updates = self._extract_topics(exchange)
        if topic_updates:
            updates['topics'] = topic_updates
        
        # 4. Update relationship metrics
        metric_updates = self._update_relationship_metrics(exchange, emotion)
        if metric_updates:
            updates['metrics'] = metric_updates
        
        # 5. Check for milestones
        milestone_updates = self._check_milestones()
        if milestone_updates:
            updates['milestones'] = milestone_updates
        
        # Save profile
        self.profile.save()
        
        return updates
    
    def _update_emotional_context(self, exchange: str, emotion: str = None) -> Dict:
        """Update emotional context based on exchange."""
        updates = {}
        
        # Detect emotion if not provided
        if not emotion:
            # Extract user message from exchange
            user_part = exchange.split('AI:')[0].replace('User:', '').strip()
            emotion = detect_emotion(user_part)
        
        emotional_context = self.profile.emotional_context or {}
        old_mood = emotional_context.get('current_mood', 'neutral')
        
        # Update current mood
        if emotion != old_mood:
            emotional_context['current_mood'] = emotion
            updates['mood_changed'] = {'from': old_mood, 'to': emotion}
            
            # Track mood history
            mood_history = emotional_context.get('mood_history', [])
            mood_history.append({
                'from': old_mood,
                'to': emotion,
                'timestamp': timezone.now().isoformat()
            })
            # Keep last 20 entries
            emotional_context['mood_history'] = mood_history[-20:]
        
        # Detect energy level from language
        energy = self._detect_energy(exchange)
        if energy:
            emotional_context['energy_level'] = energy
            updates['energy'] = energy
        
        # Update mood trend
        mood_trend = self._calculate_mood_trend(emotional_context.get('mood_history', []))
        emotional_context['mood_trend'] = mood_trend
        
        self.profile.emotional_context = emotional_context
        return updates
    
    def _detect_energy(self, exchange: str) -> Optional[str]:
        """Detect energy level from language patterns."""
        low_energy_words = ['tired', 'exhausted', 'drained', 'sleepy', 'worn out', 'low energy']
        high_energy_words = ['excited', 'pumped', 'energized', 'motivated', 'ready', 'can\'t wait']
        
        text_lower = exchange.lower()
        
        if any(word in text_lower for word in low_energy_words):
            return 'low'
        elif any(word in text_lower for word in high_energy_words):
            return 'high'
        return None
    
    def _calculate_mood_trend(self, mood_history: List[Dict]) -> str:
        """Calculate mood trend from history."""
        if len(mood_history) < 3:
            return 'stable'
        
        positive_moods = {'excited', 'happy', 'hopeful', 'grateful', 'proud'}
        negative_moods = {'stressed', 'sad', 'frustrated', 'anxious', 'tired'}
        
        recent = mood_history[-5:]
        positive_count = sum(1 for m in recent if m.get('to') in positive_moods)
        negative_count = sum(1 for m in recent if m.get('to') in negative_moods)
        
        if positive_count > negative_count + 1:
            return 'improving'
        elif negative_count > positive_count + 1:
            return 'declining'
        return 'stable'
    
    def _check_life_events(self, exchange: str) -> Optional[Dict]:
        """Check for significant life events."""
        # Extract user message
        user_part = exchange.split('AI:')[0].replace('User:', '').strip()
        life_event = detect_life_event(user_part)
        
        if not life_event:
            return None
        
        event_data = {
            'type': life_event,
            'date': timezone.now().date().isoformat(),
            'note': self._extract_event_description(user_part, life_event),
            'timestamp': timezone.now().isoformat()
        }
        
        # Add to important dates
        important_dates = self.profile.important_dates or []
        important_dates.append(event_data)
        self.profile.important_dates = important_dates
        
        # Update relationship metrics for achievements
        if life_event == 'achievement':
            metrics = self.profile.relationship_metrics or {}
            metrics['milestones_celebrated'] = metrics.get('milestones_celebrated', 0) + 1
            self.profile.relationship_metrics = metrics
        
        # Add to recent wins or stressors
        emotional_context = self.profile.emotional_context or {}
        if life_event in ['achievement', 'job_change']:
            recent_wins = emotional_context.get('recent_wins', [])
            recent_wins.insert(0, event_data['note'])
            emotional_context['recent_wins'] = recent_wins[:5]  # Keep last 5
        elif life_event in ['loss', 'health']:
            stressors = emotional_context.get('active_stressors', [])
            stressors.insert(0, event_data['note'])
            emotional_context['active_stressors'] = stressors[:5]
        
        self.profile.emotional_context = emotional_context
        
        return event_data
    
    def _extract_event_description(self, text: str, event_type: str) -> str:
        """Extract a brief description of the life event."""
        # Simple extraction - first 100 chars
        description = text[:100]
        if len(text) > 100:
            description += '...'
        return description
    
    def _extract_topics(self, exchange: str) -> List[str]:
        """Extract topics/interests from exchange."""
        # Common topic indicators
        topic_patterns = {
            'work': ['job', 'work', 'office', 'boss', 'colleague', 'project', 'meeting'],
            'family': ['mom', 'dad', 'sister', 'brother', 'family', 'parent', 'child'],
            'health': ['exercise', 'workout', 'diet', 'sleep', 'doctor', 'health'],
            'travel': ['travel', 'trip', 'vacation', 'flight', 'hotel', 'country'],
            'tech': ['coding', 'programming', 'app', 'software', 'computer', 'tech'],
            'finance': ['money', 'savings', 'investment', 'budget', 'expense'],
            'relationships': ['dating', 'relationship', 'partner', 'boyfriend', 'girlfriend'],
            'hobbies': ['hobby', 'game', 'music', 'movie', 'book', 'sport'],
            'education': ['study', 'university', 'course', 'learning', 'exam', 'degree'],
        }
        
        text_lower = exchange.lower()
        detected_topics = []
        
        for topic, keywords in topic_patterns.items():
            if any(kw in text_lower for kw in keywords):
                detected_topics.append(topic)
        
        if detected_topics:
            # Update profile interests
            interaction_style = self.profile.interaction_style or {}
            current_interests = set(interaction_style.get('interests', []))
            new_interests = set(detected_topics) - current_interests
            
            if new_interests:
                interaction_style['interests'] = list(current_interests | new_interests)
                self.profile.interaction_style = interaction_style
                return list(new_interests)
        
        return []
    
    def _update_relationship_metrics(self, exchange: str, emotion: str) -> Dict:
        """Update relationship depth metrics."""
        updates = {}
        metrics = self.profile.relationship_metrics or {}
        
        # Increment conversation count
        metrics['total_messages'] = metrics.get('total_messages', 0) + 2  # User + AI
        
        # Check for emotional sharing (increases trust)
        emotional_words = ['feel', 'feeling', 'scared', 'worried', 'love', 'hate', 'afraid', 'hope']
        user_part = exchange.split('AI:')[0].lower()
        
        if any(word in user_part for word in emotional_words):
            metrics['emotional_moments_shared'] = metrics.get('emotional_moments_shared', 0) + 1
            # Increase trust level
            current_trust = metrics.get('trust_level', 0.3)
            metrics['trust_level'] = min(1.0, current_trust + 0.02)
            updates['trust_increased'] = True
        
        # Update conversation depth based on message length and content
        if len(user_part) > 200:
            metrics['conversation_depth'] = 'deep'
        elif len(user_part) > 50:
            metrics['conversation_depth'] = 'moderate'
        else:
            metrics['conversation_depth'] = 'surface'
        
        self.profile.relationship_metrics = metrics
        return updates
    
    def _check_milestones(self) -> List[str]:
        """Check if any relationship milestones have been achieved."""
        metrics = self.profile.relationship_metrics or {}
        achieved = set(metrics.get('achieved_milestones', ['first_steps']))
        new_milestones = []
        
        # Define milestone thresholds
        milestones = {
            'getting_to_know_you': {'messages': 20},
            'regular_conversations': {'messages': 100},
            'trusted_friend': {'trust_level': 0.6, 'emotional_moments': 5},
            'deep_connection': {'trust_level': 0.8, 'emotional_moments': 15},
            'life_partner': {'trust_level': 0.95, 'messages': 1000},
        }
        
        total_messages = metrics.get('total_messages', 0)
        trust_level = metrics.get('trust_level', 0.3)
        emotional_moments = metrics.get('emotional_moments_shared', 0)
        
        for milestone, requirements in milestones.items():
            if milestone in achieved:
                continue
            
            meets_requirements = True
            if 'messages' in requirements and total_messages < requirements['messages']:
                meets_requirements = False
            if 'trust_level' in requirements and trust_level < requirements['trust_level']:
                meets_requirements = False
            if 'emotional_moments' in requirements and emotional_moments < requirements['emotional_moments']:
                meets_requirements = False
            
            if meets_requirements:
                achieved.add(milestone)
                new_milestones.append(milestone)
        
        if new_milestones:
            metrics['achieved_milestones'] = list(achieved)
            self.profile.relationship_metrics = metrics
        
        return new_milestones


def update_friend_profile(user_id: str, exchange: str, emotion: str = None) -> Dict[str, Any]:
    """
    Convenience function to update friend profile.
    
    Args:
        user_id: The user's ID
        exchange: The conversation exchange
        emotion: Pre-detected emotion (optional)
    
    Returns:
        Dict of updates made
    """
    profiler = FriendProfiler(user_id)
    return profiler.analyze_and_update(exchange, emotion)


def get_friend_context(user_id: str) -> Dict[str, Any]:
    """
    Get the active friend context for conversation.
    
    Returns:
        Dict with current mood, energy, stressors, etc.
    """
    try:
        profile = FriendProfile.objects.get(user_id=user_id)
        return profile.get_active_context()
    except FriendProfile.DoesNotExist:
        return {
            'name': 'friend',
            'mood': 'neutral',
            'energy': 'normal',
            'stressors': [],
            'recent_wins': [],
            'persona': 'Supportive Friend',
            'comm_style': 'warm and friendly',
        }
