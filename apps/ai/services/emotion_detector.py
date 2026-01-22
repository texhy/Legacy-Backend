"""
Emotion and Life Event Detection Service.

Fast, synchronous analysis for immediate use in chat responses.
More sophisticated analysis happens asynchronously.
"""
from typing import Optional, Dict, List
import re


# Emotion keyword mappings (simple but effective)
EMOTION_KEYWORDS = {
    'excited': ['excited', 'thrilled', 'amazing', 'awesome', 'fantastic', 'incredible', 'pumped', 'stoked', 'hyped'],
    'happy': ['happy', 'great', 'good', 'wonderful', 'pleased', 'glad', 'delighted', 'content', 'joyful'],
    'stressed': ['stressed', 'overwhelmed', 'anxious', 'worried', 'nervous', 'tense', 'pressure', 'deadline'],
    'sad': ['sad', 'down', 'upset', 'depressed', 'unhappy', 'disappointed', 'heartbroken', 'miserable'],
    'frustrated': ['frustrated', 'annoyed', 'irritated', 'angry', 'mad', 'furious', 'pissed'],
    'tired': ['tired', 'exhausted', 'drained', 'burnt out', 'fatigued', 'sleepy', 'worn out'],
    'confused': ['confused', 'lost', 'unsure', 'uncertain', 'puzzled', 'bewildered'],
    'hopeful': ['hopeful', 'optimistic', 'looking forward', 'excited about', 'can\'t wait'],
    'grateful': ['grateful', 'thankful', 'appreciate', 'blessed', 'lucky'],
    'proud': ['proud', 'accomplished', 'achieved', 'succeeded', 'did it', 'nailed it'],
}

# Life event patterns
LIFE_EVENT_PATTERNS = {
    'job_change': [
        r'got (?:the|a) job', r'new job', r'starting (?:at|work)', r'hired', r'promotion', 
        r'got promoted', r'fired', r'laid off', r'quit (?:my )?job', r'resigned'
    ],
    'relationship': [
        r'broke up', r'breaking up', r'got engaged', r'getting married', r'divorce', 
        r'started dating', r'new relationship', r'proposed'
    ],
    'health': [
        r'diagnosed', r'surgery', r'hospital', r'sick', r'recovered', r'health issue',
        r'doctor said', r'test results'
    ],
    'achievement': [
        r'graduated', r'passed (?:the|my) exam', r'got accepted', r'won', r'published',
        r'launched', r'finished (?:the|my) project', r'milestone'
    ],
    'loss': [
        r'passed away', r'died', r'lost (?:my|a) (?:mom|dad|friend|pet|grandmother|grandfather)',
        r'funeral', r'grieving'
    ],
    'move': [
        r'moving to', r'moved to', r'new apartment', r'new house', r'relocating'
    ],
    'financial': [
        r'got (?:a )?raise', r'bonus', r'promotion', r'debt', r'paid off', 
        r'investment', r'savings goal'
    ],
    'family': [
        r'pregnant', r'having a baby', r'new baby', r'birth', r'born'
    ]
}


def detect_emotion(text: str) -> str:
    """
    Detect the primary emotion in a message.
    Returns the most likely emotion or 'neutral'.
    """
    text_lower = text.lower()
    
    emotion_scores: Dict[str, int] = {}
    
    for emotion, keywords in EMOTION_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            emotion_scores[emotion] = score
    
    if not emotion_scores:
        return 'neutral'
    
    # Return emotion with highest score
    return max(emotion_scores, key=emotion_scores.get)


def detect_life_event(text: str) -> Optional[str]:
    """
    Detect if the message mentions a significant life event.
    Returns the event type or None.
    """
    text_lower = text.lower()
    
    for event_type, patterns in LIFE_EVENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return event_type
    
    return None


def analyze_message(text: str) -> Dict:
    """
    Complete message analysis for the chat graph.
    """
    return {
        'emotion': detect_emotion(text),
        'life_event': detect_life_event(text),
        'is_question': '?' in text,
        'is_short': len(text.split()) < 10,
        'mentions_time': bool(re.search(
            r'\b(?:today|tomorrow|yesterday|next week|last week|soon|later)\b', 
            text.lower()
        )),
    }


def get_emotion_response_guidance(emotion: str) -> str:
    """
    Get guidance for responding to a specific emotion.
    Used to fine-tune the AI's response style.
    """
    guidance = {
        'excited': "Match their enthusiasm! Use exclamation points, ask for details, celebrate with them.",
        'happy': "Be warm and positive. Share in their joy and ask what's making them feel good.",
        'stressed': "Be calm and grounding. Validate their feelings first, then gently offer perspective.",
        'sad': "Be gentle and empathetic. Listen more than advise. It's okay to sit in the sadness.",
        'frustrated': "Acknowledge the frustration without dismissing it. Ask what they need - venting or solutions?",
        'tired': "Be understanding. Keep your response concise. Maybe suggest rest or self-care.",
        'confused': "Be clear and patient. Help organize their thoughts. Ask clarifying questions.",
        'hopeful': "Encourage their optimism while keeping them grounded. Explore their plans.",
        'grateful': "Celebrate what they're grateful for. Help them savor the moment.",
        'proud': "Celebrate their achievement! Ask how they feel about it, what they learned.",
        'neutral': "Follow their lead. Be present and curious about what's on their mind."
    }
    return guidance.get(emotion, guidance['neutral'])
