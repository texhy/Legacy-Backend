"""
Chat Graph - Synchronous LangGraph for AI Response Generation.

This is Graph A: The synchronous chat engine that generates immediate responses.
"""
from typing import TypedDict, List, Dict, Any, Optional
from django.conf import settings
from django.db.models import F
from openai import OpenAI

from langgraph.graph import StateGraph, END

from apps.ai.services.context_loader import get_llm_context, LLMContext
from apps.ai.services.emotion_detector import (
    detect_emotion, 
    detect_life_event, 
    get_emotion_response_guidance,
    analyze_message
)
from apps.chat.models import Message
from apps.libraries.models import Chapter


# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


class ChatState(TypedDict):
    """State for the chat generation graph."""
    
    # Input
    user_message: str
    chapter_id: str
    library_id: str
    user_id: str
    
    # Context (populated by retrieve_context)
    llm_context: Optional[LLMContext]
    messages: List[Dict]
    context_summary: str
    project_context: str
    friend_profile: Dict[str, Any]
    entity_facts: List[str]
    is_new_project: bool
    is_new_chat: bool
    session_primer: str
    
    # Analysis (populated by analyze_input)
    detected_emotion: str
    detected_life_event: Optional[str]
    message_analysis: Dict
    
    # Prompt (populated by assemble_prompt)
    assembled_prompt: Dict[str, str]
    
    # Output
    ai_response: str
    response_metadata: Dict
    user_message_id: Optional[int]
    ai_message_id: Optional[int]


def retrieve_context(state: ChatState) -> ChatState:
    """
    Fetch all context using the Context Loader Engine.
    This handles all three scenarios: Cold Start, New Chapter, Deep Dive.
    """
    
    context: LLMContext = get_llm_context(
        user_id=state['user_id'],
        library_id=state['library_id'],
        chapter_id=state['chapter_id'],
        user_message=state['user_message']
    )
    
    return {
        **state,
        'llm_context': context,
        'messages': context['recent_messages'],
        'context_summary': context['chat_memory'],
        'project_context': context['project_context'],
        'friend_profile': context['global_context'],
        'entity_facts': [
            f"{e['name']}: {e['summary']}" 
            for e in context['relevant_entities']
            if e.get('summary')
        ],
        'is_new_project': context['is_new_project'],
        'is_new_chat': context['is_new_chat'],
        'session_primer': context['session_primer']
    }


def analyze_input(state: ChatState) -> ChatState:
    """Analyze user's emotional state and intent."""
    
    # Quick sentiment analysis
    emotion = detect_emotion(state['user_message'])
    
    # Check for life events
    life_event = detect_life_event(state['user_message'])
    
    # Full message analysis
    analysis = analyze_message(state['user_message'])
    
    return {
        **state,
        'detected_emotion': emotion,
        'detected_life_event': life_event,
        'message_analysis': analysis
    }


def assemble_prompt(state: ChatState) -> ChatState:
    """
    Build the 'Prompt Sandwich' for the LLM.
    The system instruction already handles scenario-specific behavior.
    """
    
    context = state['llm_context']
    
    # Build memory context
    memory_sections = []
    
    # Add session primer if this is start of conversation
    if context['session_primer'] and not state['messages']:
        memory_sections.append(f"[SESSION BRIDGE]\n{context['session_primer']}")
    
    # Add project context
    if context['project_context']:
        memory_sections.append(f"[PROJECT: {context['project_title']}]\n{context['project_context']}")
    
    # Add chat memory (compressed older messages)
    if context['chat_memory']:
        memory_sections.append(f"[PREVIOUS IN THIS CHAPTER]\n{context['chat_memory']}")
    
    # Add entity facts
    if state['entity_facts']:
        memory_sections.append(f"[RELEVANT MEMORIES]\n" + "\n".join(state['entity_facts']))
    
    # Add emotion guidance
    emotion_guidance = get_emotion_response_guidance(state['detected_emotion'])
    if state['detected_emotion'] != 'neutral':
        memory_sections.append(f"[EMOTIONAL CONTEXT]\nUser seems {state['detected_emotion']}. {emotion_guidance}")
    
    # Add life event context if detected
    if state['detected_life_event']:
        memory_sections.append(f"[LIFE EVENT DETECTED]\nType: {state['detected_life_event']}. This is significant - acknowledge it appropriately.")
    
    return {
        **state,
        'assembled_prompt': {
            'system': context['system_instruction'],
            'memory': "\n\n".join(memory_sections),
            'user_message': state['user_message']
        }
    }


def generate_response(state: ChatState) -> ChatState:
    """Invoke the LLM to generate response."""
    
    # Construct messages for the LLM
    messages = [
        {"role": "system", "content": state['assembled_prompt']['system']},
    ]
    
    # Add memory as a system context
    if state['assembled_prompt']['memory']:
        messages.append({
            "role": "system", 
            "content": f"CONTEXT & MEMORY:\n{state['assembled_prompt']['memory']}"
        })
    
    # Add conversation history
    for msg in state['messages']:
        role = "user" if msg['sender'] == 'USER' else "assistant"
        messages.append({"role": role, "content": msg['content']})
    
    # Add current user message
    messages.append({"role": "user", "content": state['user_message']})
    
    # Generate response
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        
    except Exception as e:
        ai_response = f"I'm having trouble responding right now. Let me try again in a moment. (Error: {str(e)[:100]})"
        tokens_used = 0
    
    return {
        **state,
        'ai_response': ai_response,
        'response_metadata': {
            'model': settings.OPENAI_MODEL,
            'tokens_used': tokens_used,
            'emotion_detected': state['detected_emotion'],
            'life_event_detected': state['detected_life_event'],
            'is_new_project': state['is_new_project'],
            'is_new_chat': state['is_new_chat'],
            'entities_referenced': [
                e['name'] for e in state['llm_context']['relevant_entities']
            ] if state['llm_context'] else []
        }
    }


def save_messages(state: ChatState) -> ChatState:
    """
    Save messages to database and trigger async tasks.
    """
    # Save user message
    user_msg = Message.objects.create(
        chapter_id=state['chapter_id'],
        sender='USER',
        content=state['user_message'],
        metadata={
            'emotion': state['detected_emotion'],
            'life_event': state['detected_life_event'],
            'analysis': state['message_analysis']
        }
    )
    
    # Save AI message
    ai_msg = Message.objects.create(
        chapter_id=state['chapter_id'],
        sender='AI',
        content=state['ai_response'],
        metadata=state['response_metadata']
    )
    
    # Update message count
    Chapter.objects.filter(id=state['chapter_id']).update(
        message_count=F('message_count') + 2
    )
    
    return {
        **state,
        'user_message_id': user_msg.id,
        'ai_message_id': ai_msg.id
    }


def trigger_async_tasks(state: ChatState) -> ChatState:
    """
    Queue async tasks for background processing.
    These tasks handle knowledge extraction, memory compression, etc.
    """
    # Import here to avoid circular imports
    from apps.ai.tasks import (
        process_knowledge_extraction,
        check_memory_compression,
        update_session_primer
    )
    
    # Queue knowledge extraction
    process_knowledge_extraction.delay(
        user_id=state['user_id'],
        chapter_id=state['chapter_id'],
        message_id=state['user_message_id'],
        exchange=f"User: {state['user_message']}\nAI: {state['ai_response']}"
    )
    
    # Queue memory compression check
    check_memory_compression.delay(chapter_id=state['chapter_id'])
    
    # Queue session primer update
    update_session_primer.delay(
        user_id=state['user_id'],
        last_exchange=f"User: {state['user_message']}\nAI: {state['ai_response']}",
        emotion=state['detected_emotion']
    )
    
    return state


# Build the graph
def build_chat_graph():
    """
    Construct the LangGraph for chat processing.
    
    Flow:
    retrieve_context -> analyze_input -> assemble_prompt -> generate_response -> save_messages -> trigger_async_tasks
    """
    workflow = StateGraph(ChatState)
    
    # Add nodes
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("analyze_input", analyze_input)
    workflow.add_node("assemble_prompt", assemble_prompt)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("save_messages", save_messages)
    workflow.add_node("trigger_async_tasks", trigger_async_tasks)
    
    # Define edges
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "analyze_input")
    workflow.add_edge("analyze_input", "assemble_prompt")
    workflow.add_edge("assemble_prompt", "generate_response")
    workflow.add_edge("generate_response", "save_messages")
    workflow.add_edge("save_messages", "trigger_async_tasks")
    workflow.add_edge("trigger_async_tasks", END)
    
    return workflow.compile()


# Create the compiled graph (singleton)
chat_graph = build_chat_graph()


def process_chat_message(
    user_message: str,
    chapter_id: str,
    library_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Main entry point for processing a chat message.
    
    Args:
        user_message: The user's input message
        chapter_id: UUID of the chapter
        library_id: UUID of the library
        user_id: ID of the user
    
    Returns:
        Dict containing ai_response, metadata, and message IDs
    """
    # Initialize state
    initial_state: ChatState = {
        'user_message': user_message,
        'chapter_id': chapter_id,
        'library_id': library_id,
        'user_id': user_id,
        'llm_context': None,
        'messages': [],
        'context_summary': '',
        'project_context': '',
        'friend_profile': {},
        'entity_facts': [],
        'is_new_project': False,
        'is_new_chat': False,
        'session_primer': '',
        'detected_emotion': 'neutral',
        'detected_life_event': None,
        'message_analysis': {},
        'assembled_prompt': {},
        'ai_response': '',
        'response_metadata': {},
        'user_message_id': None,
        'ai_message_id': None,
    }
    
    # Run the graph
    final_state = chat_graph.invoke(initial_state)
    
    return {
        'ai_response': final_state['ai_response'],
        'metadata': final_state['response_metadata'],
        'user_message_id': final_state['user_message_id'],
        'ai_message_id': final_state['ai_message_id'],
        'detected_emotion': final_state['detected_emotion'],
        'detected_life_event': final_state['detected_life_event'],
    }
