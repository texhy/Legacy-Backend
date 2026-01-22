"""
Knowledge Graph - Asynchronous LangGraph for Entity Extraction & Friend Learning.

This is Graph C: Extracts knowledge and updates the friend profile.
Triggered after every AI response.

Flow:
1. NER Extract - Extract entities from exchange
2. Resolve Entities - Match to existing or create new
3. Save Entities - Create EntityMentions
4. Analyze Exchange - Detect emotions, life events, topics
5. Update Profile - Update FriendProfile with learnings
"""
from typing import TypedDict, List, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from openai import OpenAI
import json
import re
import logging

from langgraph.graph import StateGraph, END

from apps.ai.services.entity_resolver import resolve_entity
from apps.ai.services.friend_profiler import update_friend_profile
from apps.ai.services.emotion_detector import detect_emotion, detect_life_event

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


class KnowledgeState(TypedDict):
    """State for the knowledge extraction graph."""
    
    # Input
    user_id: str
    chapter_id: str
    message_id: int
    last_exchange: str  # "User: ... AI: ..."
    
    # Extraction
    extracted_entities: List[Dict]
    detected_emotion: str
    detected_life_event: Optional[str]
    detected_topics: List[str]
    
    # Profile updates
    profile_updates: Dict
    
    # Results
    entities_saved: int
    entities_created: int
    profile_updated: bool
    processing_errors: List[str]


def extract_entities(state: KnowledgeState) -> KnowledgeState:
    """
    Extract entities from the exchange using LLM.
    
    Uses GPT to identify people, places, organizations, events, and topics.
    """
    
    extraction_prompt = f"""Extract entities and facts from this conversation exchange.

EXCHANGE:
{state['last_exchange']}

Return a JSON array of entities found. For each entity include:
- name: The entity's proper name (e.g., "Jane" not "my sister Jane")
- type: One of PERSON, LOCATION, ORG, EVENT, TOPIC, GOAL, DATE
- fact: A specific fact learned about this entity from this exchange
- relationship: (for PERSON only) their relationship to the user (e.g., "sister", "boss", "friend")
- sentiment: positive, neutral, or negative (how the user feels about this entity in this context)

Example output:
[
  {{"name": "Jane", "type": "PERSON", "fact": "Got promoted to VP at her company", "relationship": "sister", "sentiment": "positive"}},
  {{"name": "Google", "type": "ORG", "fact": "User is applying for a job there", "relationship": null, "sentiment": "hopeful"}},
  {{"name": "Machine Learning Course", "type": "GOAL", "fact": "User wants to complete it by March", "relationship": null, "sentiment": "motivated"}}
]

IMPORTANT:
- Only extract entities that are clearly mentioned
- Extract specific, concrete facts (not vague statements)
- If no entities found, return: []

JSON OUTPUT:"""

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an entity extraction assistant. Output only valid JSON arrays."
                },
                {"role": "user", "content": extraction_prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        
        # Handle markdown code blocks
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        entities = json.loads(content)
        
        if not isinstance(entities, list):
            entities = []
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse entity extraction response: {e}")
        entities = []
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        entities = []
        state['processing_errors'] = state.get('processing_errors', []) + [str(e)]
    
    return {
        **state,
        'extracted_entities': entities
    }


def analyze_exchange(state: KnowledgeState) -> KnowledgeState:
    """
    Analyze the exchange for emotions, life events, and topics.
    """
    
    # Extract user message for analysis
    user_part = state['last_exchange'].split('AI:')[0].replace('User:', '').strip()
    
    # Detect emotion
    emotion = detect_emotion(user_part)
    
    # Detect life events
    life_event = detect_life_event(user_part)
    
    # Detect topics (simple keyword matching)
    topics = _extract_topics(user_part)
    
    return {
        **state,
        'detected_emotion': emotion,
        'detected_life_event': life_event,
        'detected_topics': topics
    }


def _extract_topics(text: str) -> List[str]:
    """Extract topics from text using keyword matching."""
    topic_keywords = {
        'work': ['job', 'work', 'office', 'boss', 'project', 'meeting', 'career'],
        'family': ['mom', 'dad', 'sister', 'brother', 'family', 'parent'],
        'health': ['exercise', 'gym', 'diet', 'sleep', 'doctor', 'health', 'sick'],
        'finance': ['money', 'savings', 'investment', 'budget', 'salary'],
        'relationships': ['dating', 'relationship', 'partner', 'friend'],
        'education': ['study', 'university', 'course', 'learning', 'exam'],
        'tech': ['coding', 'programming', 'app', 'software', 'computer'],
        'creativity': ['writing', 'art', 'music', 'design', 'creative'],
    }
    
    text_lower = text.lower()
    detected = []
    
    for topic, keywords in topic_keywords.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(topic)
    
    return detected


def resolve_and_save_entities(state: KnowledgeState) -> KnowledgeState:
    """
    Resolve entities and save EntityMentions.
    """
    from apps.cognitive.models import EntityMention
    from apps.chat.models import Message
    from apps.libraries.models import Chapter
    
    entities_saved = 0
    entities_created = 0
    
    try:
        chapter = Chapter.objects.get(id=state['chapter_id'])
        message = Message.objects.get(id=state['message_id'])
        
        for entity_data in state['extracted_entities']:
            name = entity_data.get('name', '').strip()
            if not name:
                continue
            
            entity_type = entity_data.get('type', 'TOPIC')
            fact = entity_data.get('fact', '')
            relationship = entity_data.get('relationship')
            sentiment = entity_data.get('sentiment', 'neutral')
            
            # Map sentiment to score
            sentiment_map = {'positive': 0.5, 'neutral': 0.0, 'negative': -0.5, 'hopeful': 0.3, 'motivated': 0.4}
            sentiment_score = sentiment_map.get(sentiment, 0.0)
            
            # Resolve entity (creates or finds existing)
            entity, was_created = resolve_entity(
                user_id=state['user_id'],
                entity_name=name,
                entity_type=entity_type,
                fact=fact,
                relationship=relationship or '',
                sentiment_score=sentiment_score
            )
            
            if was_created:
                entities_created += 1
            
            # Create EntityMention
            if fact:
                EntityMention.objects.create(
                    entity=entity,
                    message=message,
                    chapter=chapter,
                    fact_snippet=fact,
                    confidence=0.9,
                    sentiment=sentiment_score
                )
                entities_saved += 1
        
        logger.info(
            f"Knowledge extraction: saved {entities_saved} mentions, "
            f"created {entities_created} new entities"
        )
        
    except Exception as e:
        logger.error(f"Failed to save entities: {e}")
        state['processing_errors'] = state.get('processing_errors', []) + [str(e)]
    
    return {
        **state,
        'entities_saved': entities_saved,
        'entities_created': entities_created
    }


def update_profile(state: KnowledgeState) -> KnowledgeState:
    """
    Update the friend profile with learnings from this exchange.
    """
    
    try:
        updates = update_friend_profile(
            user_id=state['user_id'],
            exchange=state['last_exchange'],
            emotion=state['detected_emotion']
        )
        
        profile_updated = bool(updates)
        
        logger.info(f"Profile updates: {updates}")
        
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        updates = {}
        profile_updated = False
        state['processing_errors'] = state.get('processing_errors', []) + [str(e)]
    
    return {
        **state,
        'profile_updates': updates,
        'profile_updated': profile_updated
    }


def build_knowledge_graph():
    """
    Construct the LangGraph for knowledge extraction.
    
    Flow:
    extract_entities -> analyze_exchange -> resolve_and_save_entities -> update_profile
    """
    workflow = StateGraph(KnowledgeState)
    
    # Add nodes
    workflow.add_node("extract_entities", extract_entities)
    workflow.add_node("analyze_exchange", analyze_exchange)
    workflow.add_node("resolve_and_save", resolve_and_save_entities)
    workflow.add_node("update_profile", update_profile)
    
    # Define edges
    workflow.set_entry_point("extract_entities")
    workflow.add_edge("extract_entities", "analyze_exchange")
    workflow.add_edge("analyze_exchange", "resolve_and_save")
    workflow.add_edge("resolve_and_save", "update_profile")
    workflow.add_edge("update_profile", END)
    
    return workflow.compile()


# Create the compiled graph (singleton)
knowledge_graph = build_knowledge_graph()


def process_knowledge(
    user_id: str,
    chapter_id: str,
    message_id: int,
    exchange: str
) -> Dict[str, Any]:
    """
    Main entry point for processing knowledge from an exchange.
    
    Args:
        user_id: The user's ID
        chapter_id: The chapter ID
        message_id: The message ID
        exchange: The exchange text ("User: ... AI: ...")
    
    Returns:
        Dict with extraction results
    """
    initial_state: KnowledgeState = {
        'user_id': user_id,
        'chapter_id': chapter_id,
        'message_id': message_id,
        'last_exchange': exchange,
        'extracted_entities': [],
        'detected_emotion': 'neutral',
        'detected_life_event': None,
        'detected_topics': [],
        'profile_updates': {},
        'entities_saved': 0,
        'entities_created': 0,
        'profile_updated': False,
        'processing_errors': [],
    }
    
    final_state = knowledge_graph.invoke(initial_state)
    
    return {
        'entities_extracted': len(final_state['extracted_entities']),
        'entities_saved': final_state['entities_saved'],
        'entities_created': final_state['entities_created'],
        'emotion': final_state['detected_emotion'],
        'life_event': final_state['detected_life_event'],
        'topics': final_state['detected_topics'],
        'profile_updated': final_state['profile_updated'],
        'profile_updates': final_state['profile_updates'],
        'errors': final_state['processing_errors'],
    }
