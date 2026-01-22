"""
Celery Tasks for Legacy AI Processing.

These are asynchronous tasks that run in the background after chat responses.
They handle:
- Knowledge extraction (entities, facts)
- Memory compression (summarization)
- Friend profile updates
- Session primer updates
"""
from celery import shared_task
from django.conf import settings
from django.db.models import F
from openai import OpenAI
import logging
import re

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


@shared_task(bind=True, max_retries=3)
def process_knowledge_extraction(
    self,
    user_id: str,
    chapter_id: str,
    message_id: int,
    exchange: str
):
    """
    Extract entities and facts from the last exchange using Graph C.
    
    This task uses the knowledge_graph to:
    1. Extract entities with LLM
    2. Resolve entities (fuzzy matching to existing or create new)
    3. Create EntityMentions with extracted facts
    4. Update FriendProfile with learnings
    """
    from apps.ai.graphs.knowledge_graph import process_knowledge
    
    try:
        result = process_knowledge(
            user_id=user_id,
            chapter_id=chapter_id,
            message_id=message_id,
            exchange=exchange
        )
        
        logger.info(
            f"Knowledge extraction complete: "
            f"extracted={result['entities_extracted']}, "
            f"saved={result['entities_saved']}, "
            f"created={result['entities_created']}, "
            f"emotion={result['emotion']}, "
            f"profile_updated={result['profile_updated']}"
        )
        
        if result['errors']:
            logger.warning(f"Knowledge extraction had errors: {result['errors']}")
        
    except Exception as e:
        logger.error(f"Knowledge extraction failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True)
def check_memory_compression(self, chapter_id: str):
    """
    Check if chapter needs memory compression and trigger if necessary.
    
    Compression is triggered when message_count % 20 == 0.
    """
    from apps.libraries.models import Chapter
    
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        
        # Check if we should compress
        if chapter.message_count > 0 and chapter.message_count % 20 == 0:
            compress_chapter_memory.delay(chapter_id)
            logger.info(f"Triggered memory compression for chapter {chapter_id}")
    
    except Chapter.DoesNotExist:
        logger.warning(f"Chapter {chapter_id} not found for compression check")


@shared_task(bind=True, max_retries=3)
def compress_chapter_memory(self, chapter_id: str):
    """
    Compress chapter messages into summary using Graph B.
    
    This is the core of the hierarchical summarization:
    - Takes existing summary + messages to compress
    - Runs through summary_graph
    - Saves to Chapter.summary_text
    - Triggers library summary update
    """
    from apps.libraries.models import Chapter
    from apps.chat.models import Message
    from apps.ai.graphs.summary_graph import compress_chapter
    
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        
        # Get messages 11-30 (skip recent 10, get next 20 to compress)
        messages_to_compress = Message.objects.filter(
            chapter=chapter
        ).order_by('-timestamp')[10:30]
        
        if not messages_to_compress:
            logger.info(f"No messages to compress for chapter {chapter_id}")
            return
        
        # Format messages for compression
        new_messages = [
            f"{msg.sender}: {msg.content}"
            for msg in reversed(messages_to_compress)
        ]
        
        # Run the summary graph
        result = compress_chapter(
            chapter_id=str(chapter_id),
            chapter_title=chapter.title,
            existing_summary=chapter.summary_text or '',
            new_messages=new_messages
        )
        
        logger.info(
            f"Compressed memory for chapter {chapter_id}. "
            f"Key facts: {len(result.get('key_facts_extracted', []))}, "
            f"Emotional moments: {len(result.get('emotional_moments', []))}"
        )
        
        # Trigger library summary update (bubble up)
        update_library_summary.delay(str(chapter.library_id))
        
    except Exception as e:
        logger.error(f"Memory compression failed for chapter {chapter_id}: {e}")
        raise self.retry(exc=e, countdown=120)


@shared_task(bind=True, max_retries=2)
def update_library_summary(self, library_id: str):
    """
    Update library summary based on chapter summaries using Graph B.
    
    This aggregates all chapter summaries into a project-level overview.
    Part of the hierarchical "bubble up" summarization.
    """
    from apps.libraries.models import Library, Chapter
    from apps.ai.graphs.summary_graph import aggregate_library
    
    try:
        library = Library.objects.get(id=library_id)
        
        # Get all chapter summaries
        chapters = Chapter.objects.filter(
            library=library,
            is_archived=False
        ).exclude(summary_text='')
        
        if not chapters.exists():
            logger.info(f"No chapters with summaries for library {library_id}")
            return
        
        # Format chapter summaries for the graph
        chapter_summaries = [
            {'title': ch.title, 'summary': ch.summary_text}
            for ch in chapters
        ]
        
        # Run the library aggregation graph
        result = aggregate_library(
            library_id=str(library_id),
            library_title=library.title,
            existing_summary=library.summary_text or '',
            chapter_summaries=chapter_summaries
        )
        
        logger.info(
            f"Updated library summary for {library_id}. "
            f"Themes: {result.get('main_themes', [])}"
        )
        
    except Exception as e:
        logger.error(f"Library summary update failed: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2)
def update_session_primer(self, user_id: str, last_exchange: str, emotion: str):
    """
    Update the session primer for the next conversation.
    
    This creates the "bridge" that makes Legacy feel continuous across sessions.
    """
    from apps.cognitive.models import FriendProfile
    
    try:
        profile, created = FriendProfile.objects.get_or_create(
            user_id=user_id,
            defaults={
                'meta': {},
                'emotional_context': {},
                'life_narrative': {},
                'interaction_style': {},
                'important_dates': [],
                'relationship_metrics': {},
            }
        )
        
        prompt = f"""Based on this last exchange, write a brief primer for the AI's next session.

LAST EXCHANGE:
{last_exchange}

USER'S DETECTED EMOTION: {emotion}

Write a 2-3 sentence primer that:
1. Notes the user's current state
2. Suggests how to open the next conversation
3. Mentions anything that should be followed up on

PRIMER:"""

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are preparing context for a future conversation."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        profile.next_session_primer = response.choices[0].message.content.strip()
        
        # Also update emotional context
        if profile.emotional_context is None:
            profile.emotional_context = {}
        profile.emotional_context['current_mood'] = emotion
        
        profile.save()
        
        logger.info(f"Updated session primer for user {user_id}")
        
    except Exception as e:
        logger.error(f"Session primer update failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task
def update_all_life_narratives():
    """
    Nightly task to update all users' life narratives.
    
    This aggregates all library summaries into a life-level narrative.
    """
    from apps.cognitive.models import FriendProfile
    
    for profile in FriendProfile.objects.all():
        update_life_narrative.delay(str(profile.user_id))
    
    logger.info("Queued life narrative updates for all users")


@shared_task(bind=True, max_retries=2)
def update_life_narrative(self, user_id: str):
    """
    Update a user's life narrative from all their library summaries using Graph B.
    
    This is the highest level of the hierarchical summarization.
    Aggregates all project summaries into a life-level understanding.
    """
    from apps.cognitive.models import FriendProfile
    from apps.libraries.models import Library
    from apps.ai.graphs.summary_graph import synthesize_narrative
    
    try:
        profile = FriendProfile.objects.get(user_id=user_id)
        
        # Get all library summaries
        libraries = Library.objects.filter(
            user_id=user_id,
            is_archived=False
        ).exclude(summary_text='')
        
        if not libraries.exists():
            logger.info(f"No libraries with summaries for user {user_id}")
            return
        
        # Format library summaries for the graph
        library_summaries = [
            {'title': lib.title, 'summary': lib.summary_text}
            for lib in libraries
        ]
        
        # Run the life narrative synthesis graph
        result = synthesize_narrative(
            user_id=str(user_id),
            existing_narrative=profile.life_narrative or {},
            library_summaries=library_summaries
        )
        
        logger.info(
            f"Updated life narrative for user {user_id}. "
            f"Current chapter: {result.get('updated_narrative', {}).get('current_chapter_of_life', 'Unknown')}"
        )
        
    except FriendProfile.DoesNotExist:
        logger.warning(f"FriendProfile not found for user {user_id}")
    except Exception as e:
        logger.error(f"Life narrative update failed: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def cleanup_compressed_messages():
    """
    Weekly cleanup task to remove very old messages that have been compressed.
    
    Keeps the last 100 messages per chapter, deletes older ones.
    """
    from apps.chat.models import Message
    from apps.libraries.models import Chapter
    
    deleted_count = 0
    
    for chapter in Chapter.objects.filter(message_count__gt=100):
        # Get IDs of messages to keep (last 100)
        keep_ids = list(
            Message.objects.filter(chapter=chapter)
            .order_by('-timestamp')[:100]
            .values_list('id', flat=True)
        )
        
        # Delete older messages
        deleted, _ = Message.objects.filter(
            chapter=chapter
        ).exclude(id__in=keep_ids).delete()
        
        deleted_count += deleted
    
    logger.info(f"Cleaned up {deleted_count} old messages")
