"""
Proactive Engagement Service - Making Legacy feel like a friend who thinks about you.

This service enables Legacy to:
1. Remember important dates (birthdays, anniversaries)
2. Check in when user seems stressed
3. Follow up on previous conversations
4. Celebrate achievements and milestones
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from django.utils import timezone

from apps.cognitive.models import FriendProfile, Entity
from apps.chat.models import Message


class ProactiveEngagement:
    """
    Make Legacy feel like a friend who thinks about you.
    
    Generates contextual check-ins based on:
    - Important dates (birthdays, anniversaries, losses)
    - Recent emotional state
    - Unfinished conversations
    - Achievements and goals
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile = self._get_profile()
    
    def _get_profile(self) -> Optional[FriendProfile]:
        """Get the user's friend profile."""
        try:
            return FriendProfile.objects.get(user_id=self.user_id)
        except FriendProfile.DoesNotExist:
            return None
    
    def should_check_in(self) -> Optional[Dict[str, Any]]:
        """
        Determine if Legacy should proactively reach out.
        
        Returns:
            Dict with 'message' and 'reason' if check-in warranted, else None
        """
        if not self.profile:
            return None
        
        today = timezone.now().date()
        
        # 1. Check important dates
        date_check = self._check_important_dates(today)
        if date_check:
            return date_check
        
        # 2. Check if user was stressed and hasn't been back
        stress_check = self._check_stress_followup()
        if stress_check:
            return stress_check
        
        # 3. Check for goal deadlines
        goal_check = self._check_goal_deadlines(today)
        if goal_check:
            return goal_check
        
        # 4. Check for long absence
        absence_check = self._check_long_absence()
        if absence_check:
            return absence_check
        
        return None
    
    def _check_important_dates(self, today: date) -> Optional[Dict[str, Any]]:
        """Check for important dates (birthdays, anniversaries, etc.)."""
        
        important_dates = self.profile.important_dates or []
        user_name = self._get_user_name()
        
        for date_entry in important_dates:
            try:
                entry_date = datetime.fromisoformat(date_entry.get('date', '')).date()
            except (ValueError, TypeError):
                continue
            
            date_type = date_entry.get('type', '')
            note = date_entry.get('note', '')
            
            # Check if today matches (month and day)
            if entry_date.month == today.month and entry_date.day == today.day:
                
                if date_type == 'birthday':
                    return {
                        'message': f"🎂 Happy Birthday, {user_name}! I hope you have an amazing day filled with joy and celebration!",
                        'reason': 'birthday',
                        'priority': 'high'
                    }
                
                elif date_type == 'loss':
                    years_since = today.year - entry_date.year
                    if years_since > 0:
                        return {
                            'message': f"I was thinking about you today. It's been {years_since} year{'s' if years_since > 1 else ''} since {note}. I'm here if you want to talk.",
                            'reason': 'loss_anniversary',
                            'priority': 'high'
                        }
                
                elif date_type == 'achievement':
                    years_since = today.year - entry_date.year
                    if years_since > 0:
                        return {
                            'message': f"Hey! I just remembered - it's been {years_since} year{'s' if years_since > 1 else ''} since {note}. How does it feel looking back?",
                            'reason': 'achievement_anniversary',
                            'priority': 'medium'
                        }
            
            # Check for upcoming events (within 3 days)
            days_until = (date(today.year, entry_date.month, entry_date.day) - today).days
            if 0 < days_until <= 3:
                if date_type == 'deadline':
                    return {
                        'message': f"Just a heads up - {note} is coming up in {days_until} day{'s' if days_until > 1 else ''}. How are you feeling about it?",
                        'reason': 'upcoming_deadline',
                        'priority': 'medium'
                    }
        
        return None
    
    def _check_stress_followup(self) -> Optional[Dict[str, Any]]:
        """Check if user was stressed and hasn't been back."""
        
        emotional_context = self.profile.emotional_context or {}
        current_mood = emotional_context.get('current_mood', 'neutral')
        
        # If user was in a difficult state
        difficult_moods = ['stressed', 'anxious', 'sad', 'overwhelmed', 'frustrated']
        
        if current_mood in difficult_moods:
            # Check last message time
            last_message = Message.objects.filter(
                chapter__library__user_id=self.user_id,
                sender='USER'
            ).order_by('-timestamp').first()
            
            if last_message:
                days_since = (timezone.now() - last_message.timestamp).days
                
                if 2 <= days_since <= 7:
                    user_name = self._get_user_name()
                    stressors = emotional_context.get('active_stressors', [])
                    
                    if stressors:
                        stressor = stressors[0][:50] + '...' if len(stressors[0]) > 50 else stressors[0]
                        return {
                            'message': f"Hey {user_name}, I've been thinking about you. How are things going? Last time you mentioned something about {stressor}",
                            'reason': 'stress_followup',
                            'priority': 'high'
                        }
                    else:
                        return {
                            'message': f"Hey {user_name}, I've been thinking about you. How are you doing? You seemed a bit {current_mood} last time we talked.",
                            'reason': 'stress_followup',
                            'priority': 'medium'
                        }
        
        return None
    
    def _check_goal_deadlines(self, today: date) -> Optional[Dict[str, Any]]:
        """Check for approaching goal deadlines."""
        
        life_narrative = self.profile.life_narrative or {}
        long_term_goals = life_narrative.get('long_term_goals', [])
        
        for goal in long_term_goals:
            if isinstance(goal, dict):
                goal_text = goal.get('goal', '')
                progress = goal.get('progress', 0)
                deadline = goal.get('deadline')
                
                if deadline:
                    try:
                        deadline_date = datetime.fromisoformat(deadline).date()
                        days_until = (deadline_date - today).days
                        
                        if 0 < days_until <= 7 and progress < 0.8:
                            return {
                                'message': f"Hey! Just wanted to check in about your goal: \"{goal_text}\". You're at {int(progress*100)}% with {days_until} days to go. How's it looking?",
                                'reason': 'goal_deadline',
                                'priority': 'medium'
                            }
                    except (ValueError, TypeError):
                        continue
        
        return None
    
    def _check_long_absence(self) -> Optional[Dict[str, Any]]:
        """Check if user has been absent for a while."""
        
        last_message = Message.objects.filter(
            chapter__library__user_id=self.user_id,
            sender='USER'
        ).order_by('-timestamp').first()
        
        if last_message:
            days_since = (timezone.now() - last_message.timestamp).days
            
            if 7 <= days_since <= 14:
                user_name = self._get_user_name()
                return {
                    'message': f"Hey {user_name}! It's been a little while. Just wanted to check in and see how you're doing. 🙂",
                    'reason': 'long_absence',
                    'priority': 'low'
                }
            elif 14 < days_since <= 30:
                user_name = self._get_user_name()
                return {
                    'message': f"Hi {user_name}, I've missed our conversations! Hope everything is going well. I'm here whenever you want to catch up.",
                    'reason': 'very_long_absence',
                    'priority': 'low'
                }
        
        return None
    
    def _get_user_name(self) -> str:
        """Get the user's preferred name."""
        meta = self.profile.meta or {}
        return meta.get('preferred_name', meta.get('user_name', 'friend'))
    
    def get_session_opener(self) -> str:
        """
        Generate a contextual session opener based on the session primer.
        
        Returns:
            A personalized greeting for starting the conversation
        """
        if not self.profile:
            return "Hey! Good to see you. What's on your mind?"
        
        session_primer = self.profile.next_session_primer
        user_name = self._get_user_name()
        emotional_context = self.profile.emotional_context or {}
        current_mood = emotional_context.get('current_mood', 'neutral')
        energy = emotional_context.get('energy_level', 'normal')
        
        # If we have a session primer, it should guide the opener
        if session_primer:
            return session_primer
        
        # Generate contextual opener based on mood/energy
        if current_mood in ['stressed', 'anxious']:
            return f"Hey {user_name}. How are you holding up?"
        elif current_mood in ['excited', 'happy']:
            return f"Hey {user_name}! You were in great spirits last time. What's new?"
        elif energy == 'low':
            return f"Hey {user_name}. How are you doing today?"
        else:
            return f"Hey {user_name}! Good to see you. What's on your mind?"
    
    def get_followup_suggestions(self) -> List[Dict[str, str]]:
        """
        Get suggestions for follow-up topics based on conversation history.
        
        Returns:
            List of suggested topics with reasons
        """
        suggestions = []
        
        if not self.profile:
            return suggestions
        
        emotional_context = self.profile.emotional_context or {}
        
        # Recent wins to celebrate
        recent_wins = emotional_context.get('recent_wins', [])
        for win in recent_wins[:2]:
            suggestions.append({
                'topic': win[:50],
                'reason': 'recent_achievement',
                'prompt': f"How did things go with {win[:30]}...?"
            })
        
        # Active stressors to check on
        stressors = emotional_context.get('active_stressors', [])
        for stressor in stressors[:2]:
            suggestions.append({
                'topic': stressor[:50],
                'reason': 'ongoing_concern',
                'prompt': f"How are things with {stressor[:30]}...?"
            })
        
        # Key relationships to ask about
        life_narrative = self.profile.life_narrative or {}
        key_relationships = life_narrative.get('key_relationships', [])
        for rel in key_relationships[:2]:
            if isinstance(rel, dict):
                name = rel.get('name', '')
                role = rel.get('role', '')
                if name:
                    suggestions.append({
                        'topic': f"{name} ({role})",
                        'reason': 'important_person',
                        'prompt': f"How's {name} doing?"
                    })
        
        return suggestions


def should_proactively_check_in(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to check if Legacy should reach out.
    
    Returns:
        Dict with 'message' and 'reason' if check-in warranted, else None
    """
    engagement = ProactiveEngagement(user_id)
    return engagement.should_check_in()


def get_session_opener(user_id: str) -> str:
    """
    Get a contextual session opener for the user.
    
    Returns:
        Personalized greeting string
    """
    engagement = ProactiveEngagement(user_id)
    return engagement.get_session_opener()


def get_followup_suggestions(user_id: str) -> List[Dict[str, str]]:
    """
    Get follow-up topic suggestions.
    
    Returns:
        List of suggested topics
    """
    engagement = ProactiveEngagement(user_id)
    return engagement.get_followup_suggestions()
