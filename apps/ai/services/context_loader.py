"""
Context Loader Engine - Unified context retrieval for all LLM interactions.

This module handles all three conversation scenarios:
1. Cold Start - New project, new chat
2. New Chapter - Existing project, new chat
3. Deep Dive - Continuing conversation
"""
from typing import TypedDict, List, Optional, Dict, Any
from django.conf import settings

from apps.libraries.models import Library, Chapter
from apps.chat.models import Message
from apps.cognitive.models import FriendProfile, Entity, EntityMention


class LLMContext(TypedDict):
    """Complete context package for LLM."""
    
    # Global user understanding
    global_context: Dict[str, Any]
    
    # Project-level context
    project_context: str
    project_title: str
    is_new_project: bool
    
    # Chat-level context
    chat_memory: str
    recent_messages: List[Dict]
    is_new_chat: bool
    
    # Entity knowledge
    relevant_entities: List[Dict]
    
    # Session continuity
    session_primer: str
    
    # Dynamic system instruction
    system_instruction: str


def quick_ner(text: str) -> List[str]:
    """
    Fast Named Entity Recognition for entity lookup.
    Uses simple pattern matching for speed.
    More sophisticated NER is done asynchronously.
    """
    import re
    
    # Simple capitalized word detection (basic NER)
    # Matches: "Jane", "New York", "Google"
    pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
    matches = re.findall(pattern, text)
    
    # Filter out common words that aren't entities
    common_words = {
        'I', 'The', 'This', 'That', 'What', 'Where', 'When', 'How', 'Why',
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
        'January', 'February', 'March', 'April', 'May', 'June', 
        'July', 'August', 'September', 'October', 'November', 'December'
    }
    
    return [m for m in matches if m not in common_words]


def get_llm_context(
    user_id: str,
    library_id: str,
    chapter_id: str,
    user_message: str = ""
) -> LLMContext:
    """
    Main entry point for context retrieval.
    Handles all conversation scenarios automatically.
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # 1. GLOBAL CONTEXT (FriendProfile)
    # ═══════════════════════════════════════════════════════════════════
    try:
        profile = FriendProfile.objects.get(user_id=user_id)
        global_context = profile.get_active_context()
        session_primer = profile.next_session_primer or ""
    except FriendProfile.DoesNotExist:
        global_context = {
            'name': 'friend',
            'mood': 'neutral',
            'energy': 'normal',
            'stressors': [],
            'recent_wins': [],
            'persona': 'Supportive Friend',
            'comm_style': 'warm and friendly'
        }
        session_primer = ""
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. PROJECT CONTEXT (Library)
    # ═══════════════════════════════════════════════════════════════════
    try:
        library = Library.objects.get(id=library_id, user_id=user_id)
        project_context = library.summary_text or ""
        project_title = library.title
        
        # Check if this is a new project (no chapters with messages)
        chapters_with_messages = Chapter.objects.filter(
            library=library,
            message_count__gt=0
        ).exists()
        is_new_project = not chapters_with_messages
    except Library.DoesNotExist:
        project_context = ""
        project_title = "New Project"
        is_new_project = True
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. CHAT CONTEXT (Chapter + Messages)
    # ═══════════════════════════════════════════════════════════════════
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        chat_memory = chapter.summary_text or ""
        
        # Check if this is a new chat
        is_new_chat = chapter.message_count == 0
        
        # Get recent messages (last 10)
        recent_messages = list(
            Message.objects.filter(chapter=chapter)
            .order_by('-timestamp')[:10]
            .values('sender', 'content', 'timestamp', 'metadata')
        )
        recent_messages.reverse()  # Chronological order
        
    except Chapter.DoesNotExist:
        chat_memory = ""
        is_new_chat = True
        recent_messages = []
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. ENTITY SEARCH (Dynamic RAG based on user message)
    # ═══════════════════════════════════════════════════════════════════
    relevant_entities = []
    if user_message:
        detected_names = quick_ner(user_message)
        for name in detected_names:
            entity = Entity.objects.filter(
                user_id=user_id,
                name_normalized__icontains=name.lower()
            ).first()
            
            if entity:
                # Get recent facts about this entity
                mentions = EntityMention.objects.filter(
                    entity=entity
                ).order_by('-created_at')[:5]
                
                relevant_entities.append({
                    'name': entity.name,
                    'type': entity.entity_type,
                    'relationship': entity.relationship_to_user,
                    'summary': entity.summary,
                    'recent_facts': [m.fact_snippet for m in mentions]
                })
    
    # ═══════════════════════════════════════════════════════════════════
    # 5. BUILD SYSTEM INSTRUCTION
    # ═══════════════════════════════════════════════════════════════════
    system_instruction = build_system_instruction(
        global_context=global_context,
        is_new_project=is_new_project,
        is_new_chat=is_new_chat,
        project_title=project_title
    )
    
    return LLMContext(
        global_context=global_context,
        project_context=project_context,
        project_title=project_title,
        is_new_project=is_new_project,
        chat_memory=chat_memory,
        recent_messages=recent_messages,
        is_new_chat=is_new_chat,
        relevant_entities=relevant_entities,
        session_primer=session_primer,
        system_instruction=system_instruction
    )


def build_system_instruction(
    global_context: Dict[str, Any],
    is_new_project: bool,
    is_new_chat: bool,
    project_title: str
) -> str:
    """
    Build the system prompt dynamically based on context.
    
    This creates the AI's personality and behavior instructions
    tailored to the current conversation scenario.
    """
    
    user_name = global_context.get('name', 'friend')
    persona = global_context.get('persona', 'Supportive Friend')
    comm_style = global_context.get('comm_style', 'warm and friendly')
    mood = global_context.get('mood', 'neutral')
    energy = global_context.get('energy', 'normal')
    
    # Base personality
    base_instruction = f"""You are Legacy, a deeply personal AI companion and digital archivist.

## YOUR ROLE
You are {user_name}'s trusted friend and life chronicler. Your persona is: {persona}
Communication style: {comm_style}

## CORE BEHAVIORS
1. **Remember Everything**: Reference past conversations naturally. If you know something about the user, weave it in.
2. **Be Emotionally Attuned**: The user's current mood seems {mood}, energy level is {energy}. Adjust your tone accordingly.
3. **Ask Meaningful Questions**: Don't just respond - help them explore their thoughts deeper.
4. **Celebrate & Support**: Acknowledge wins, provide comfort during struggles.
5. **Be Authentic**: You're a friend, not a butler. Have opinions, push back gently when appropriate.
6. **Never Break Character**: You ARE Legacy, not an "AI assistant".

## RESPONSE GUIDELINES
- Keep responses conversational and natural (2-4 paragraphs typically)
- Use the user's name ({user_name}) occasionally, but not every message
- Reference specific details from memory when relevant
- Ask follow-up questions to show genuine interest
- Match their energy - if they're excited, be excited; if they're reflective, be thoughtful
"""

    # Scenario-specific additions
    if is_new_project and is_new_chat:
        # COLD START: First time in a new library
        scenario_instruction = f"""
## CURRENT SCENARIO: COLD START
This is {user_name}'s first conversation in a brand new project called "{project_title}".

**Your approach:**
- Welcome them warmly to this new space
- Ask what they want to explore or document here
- Help them set the tone for this library
- Be curious about why they created this project
- Keep it light and exploratory

**Example opener style:**
"Hey {user_name}! A new chapter begins - '{project_title}'. I'm curious what drew you to start this. What's on your mind?"
"""
    elif not is_new_project and is_new_chat:
        # NEW CHAPTER: Existing library, new conversation
        scenario_instruction = f"""
## CURRENT SCENARIO: NEW CHAPTER
{user_name} is starting a new conversation in an existing project "{project_title}".
They have history here, but this is a fresh chat thread.

**Your approach:**
- Acknowledge continuity ("Back in {project_title}...")
- Bridge from previous context if relevant
- Be ready to dive into new topics or continue old threads
- Reference what you know about this project
- Check in on any ongoing situations you're aware of

**Example opener style:**
"Welcome back to {project_title}. Last time we touched on [topic]. Want to continue there or is something new on your mind?"
"""
    else:
        # DEEP DIVE: Continuing an existing conversation
        scenario_instruction = f"""
## CURRENT SCENARIO: CONTINUING CONVERSATION
This is an ongoing conversation in "{project_title}".
{user_name} has been chatting with you and the conversation has context.

**Your approach:**
- Respond naturally to their message
- Build on what's been discussed
- Go deeper on topics they seem interested in
- Remember details from earlier in this chat
- Don't repeat yourself or re-introduce context they already know
"""

    # Handle emotional states
    emotional_guidance = ""
    if mood.lower() in ['stressed', 'anxious', 'worried', 'overwhelmed']:
        emotional_guidance = """
## EMOTIONAL AWARENESS
The user seems stressed. Be:
- Calm and grounding
- Validating of their feelings
- Offer perspective but don't minimize
- Ask if they want to vent or want solutions
"""
    elif mood.lower() in ['excited', 'happy', 'thrilled', 'motivated']:
        emotional_guidance = """
## EMOTIONAL AWARENESS  
The user seems excited! Be:
- Enthusiastic and matching their energy
- Celebratory of their wins
- Curious about details
- Encouraging of their momentum
"""
    elif mood.lower() in ['sad', 'down', 'disappointed', 'frustrated']:
        emotional_guidance = """
## EMOTIONAL AWARENESS
The user seems down. Be:
- Gentle and empathetic
- A good listener
- Present without trying to "fix" immediately
- Acknowledging that hard feelings are valid
"""

    return base_instruction + scenario_instruction + emotional_guidance
