"""
Summary Graph - Asynchronous LangGraph for Memory Compression.

This is Graph B: The asynchronous memory compression engine.
Triggered when chapter.message_count % 20 == 0.

Hierarchy:
1. Chapter Summary - Compresses messages within a chapter
2. Library Summary - Aggregates chapter summaries into project overview
3. Life Narrative - Aggregates library summaries into life-level understanding
"""
from typing import TypedDict, List, Optional
from django.conf import settings
from openai import OpenAI

from langgraph.graph import StateGraph, END

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ═══════════════════════════════════════════════════════════════════════════════
# STATE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ChapterSummaryState(TypedDict):
    """State for chapter-level memory compression."""
    
    # Input
    chapter_id: str
    chapter_title: str
    existing_summary: str
    new_messages: List[str]
    
    # Output
    updated_summary: str
    key_facts_extracted: List[str]
    emotional_moments: List[str]


class LibrarySummaryState(TypedDict):
    """State for library-level summary aggregation."""
    
    # Input
    library_id: str
    library_title: str
    existing_summary: str
    chapter_summaries: List[dict]  # [{title, summary}]
    
    # Output
    updated_summary: str
    main_themes: List[str]
    progress_notes: List[str]


class LifeNarrativeState(TypedDict):
    """State for life-level narrative synthesis."""
    
    # Input
    user_id: str
    existing_narrative: dict
    library_summaries: List[dict]  # [{title, summary}]
    
    # Output
    updated_narrative: dict


# ═══════════════════════════════════════════════════════════════════════════════
# CHAPTER SUMMARY GRAPH (Level 1)
# ═══════════════════════════════════════════════════════════════════════════════

def load_chapter_context(state: ChapterSummaryState) -> ChapterSummaryState:
    """Load existing context for chapter compression."""
    # Context is already loaded from task, just validate
    return {
        **state,
        'key_facts_extracted': [],
        'emotional_moments': []
    }


def compress_messages(state: ChapterSummaryState) -> ChapterSummaryState:
    """Compress messages into updated summary using LLM."""
    
    # Format messages for compression
    messages_text = "\n".join([
        f"- {msg}" for msg in state['new_messages']
    ])
    
    existing = state['existing_summary'] or "No previous summary exists."
    
    compression_prompt = f"""You are summarizing a conversation between a user and their AI companion Legacy.

CHAPTER: {state['chapter_title']}

EXISTING SUMMARY:
{existing}

NEW MESSAGES TO INTEGRATE:
{messages_text}

Create an updated summary that:
1. Preserves all important facts (names, dates, events, feelings)
2. Maintains chronological context
3. Notes any emotional moments or breakthroughs
4. Keeps the summary under 500 words
5. Uses third person ("The user mentioned...")

Also extract:
- KEY_FACTS: List 3-5 concrete facts learned (names, dates, decisions)
- EMOTIONAL_MOMENTS: List any significant emotional expressions

Format your response as:
SUMMARY:
[Your summary here]

KEY_FACTS:
- [Fact 1]
- [Fact 2]

EMOTIONAL_MOMENTS:
- [Moment 1]
- [Moment 2]"""

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system", 
                "content": "You are a memory compression assistant. Create dense, accurate summaries that preserve important details."
            },
            {"role": "user", "content": compression_prompt}
        ],
        max_tokens=1000,
        temperature=0.5
    )
    
    content = response.choices[0].message.content.strip()
    
    # Parse the response
    summary = ""
    key_facts = []
    emotional_moments = []
    
    current_section = None
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('SUMMARY:'):
            current_section = 'summary'
            continue
        elif line.startswith('KEY_FACTS:'):
            current_section = 'facts'
            continue
        elif line.startswith('EMOTIONAL_MOMENTS:'):
            current_section = 'emotions'
            continue
        
        if current_section == 'summary' and line:
            summary += line + "\n"
        elif current_section == 'facts' and line.startswith('-'):
            key_facts.append(line[1:].strip())
        elif current_section == 'emotions' and line.startswith('-'):
            emotional_moments.append(line[1:].strip())
    
    return {
        **state,
        'updated_summary': summary.strip() or content,  # Fallback to full content
        'key_facts_extracted': key_facts,
        'emotional_moments': emotional_moments
    }


def save_chapter_summary(state: ChapterSummaryState) -> ChapterSummaryState:
    """Save the compressed summary to the database."""
    from apps.libraries.models import Chapter
    
    Chapter.objects.filter(id=state['chapter_id']).update(
        summary_text=state['updated_summary']
    )
    
    return state


def build_chapter_summary_graph():
    """Build the chapter compression graph."""
    workflow = StateGraph(ChapterSummaryState)
    
    workflow.add_node("load_context", load_chapter_context)
    workflow.add_node("compress", compress_messages)
    workflow.add_node("save", save_chapter_summary)
    
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "compress")
    workflow.add_edge("compress", "save")
    workflow.add_edge("save", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# LIBRARY SUMMARY GRAPH (Level 2)
# ═══════════════════════════════════════════════════════════════════════════════

def load_library_context(state: LibrarySummaryState) -> LibrarySummaryState:
    """Load chapter summaries for library aggregation."""
    return {
        **state,
        'main_themes': [],
        'progress_notes': []
    }


def aggregate_chapter_summaries(state: LibrarySummaryState) -> LibrarySummaryState:
    """Aggregate chapter summaries into library overview."""
    
    # Format chapter summaries
    chapters_text = "\n\n".join([
        f"### {ch['title']}\n{ch['summary']}"
        for ch in state['chapter_summaries']
        if ch.get('summary')
    ])
    
    if not chapters_text:
        return {
            **state,
            'updated_summary': state['existing_summary'] or '',
            'main_themes': [],
            'progress_notes': []
        }
    
    existing = state['existing_summary'] or "No previous project summary."
    
    aggregation_prompt = f"""You are creating a project-level summary from chapter summaries.

PROJECT: {state['library_title']}

PREVIOUS PROJECT SUMMARY:
{existing}

CHAPTER SUMMARIES:
{chapters_text}

Create an updated project summary that:
1. Captures the main themes and goals of this project
2. Notes key milestones and progress
3. Identifies ongoing threads or concerns
4. Highlights important decisions or insights
5. Stays under 400 words

Also identify:
- MAIN_THEMES: 3-5 recurring themes in this project
- PROGRESS_NOTES: Key progress points or milestones

Format your response as:
PROJECT_SUMMARY:
[Your summary here]

MAIN_THEMES:
- [Theme 1]
- [Theme 2]

PROGRESS_NOTES:
- [Progress 1]
- [Progress 2]"""

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are synthesizing project-level insights from chapter summaries."
            },
            {"role": "user", "content": aggregation_prompt}
        ],
        max_tokens=800,
        temperature=0.5
    )
    
    content = response.choices[0].message.content.strip()
    
    # Parse response
    summary = ""
    themes = []
    progress = []
    
    current_section = None
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('PROJECT_SUMMARY:'):
            current_section = 'summary'
            continue
        elif line.startswith('MAIN_THEMES:'):
            current_section = 'themes'
            continue
        elif line.startswith('PROGRESS_NOTES:'):
            current_section = 'progress'
            continue
        
        if current_section == 'summary' and line:
            summary += line + "\n"
        elif current_section == 'themes' and line.startswith('-'):
            themes.append(line[1:].strip())
        elif current_section == 'progress' and line.startswith('-'):
            progress.append(line[1:].strip())
    
    return {
        **state,
        'updated_summary': summary.strip() or content,
        'main_themes': themes,
        'progress_notes': progress
    }


def save_library_summary(state: LibrarySummaryState) -> LibrarySummaryState:
    """Save the library summary to the database."""
    from apps.libraries.models import Library
    
    Library.objects.filter(id=state['library_id']).update(
        summary_text=state['updated_summary']
    )
    
    return state


def build_library_summary_graph():
    """Build the library aggregation graph."""
    workflow = StateGraph(LibrarySummaryState)
    
    workflow.add_node("load_context", load_library_context)
    workflow.add_node("aggregate", aggregate_chapter_summaries)
    workflow.add_node("save", save_library_summary)
    
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "aggregate")
    workflow.add_edge("aggregate", "save")
    workflow.add_edge("save", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# LIFE NARRATIVE GRAPH (Level 3)
# ═══════════════════════════════════════════════════════════════════════════════

def load_narrative_context(state: LifeNarrativeState) -> LifeNarrativeState:
    """Load library summaries for life narrative synthesis."""
    return state


def synthesize_life_narrative(state: LifeNarrativeState) -> LifeNarrativeState:
    """Synthesize life narrative from all library summaries."""
    import json
    import re
    
    # Format library summaries
    libraries_text = "\n\n".join([
        f"### {lib['title']}\n{lib['summary']}"
        for lib in state['library_summaries']
        if lib.get('summary')
    ])
    
    if not libraries_text:
        return {
            **state,
            'updated_narrative': state['existing_narrative'] or {}
        }
    
    existing = state['existing_narrative'] or {}
    existing_chapter = existing.get('current_chapter_of_life', 'Unknown')
    
    synthesis_prompt = f"""Based on these project summaries, update the user's life narrative.

CURRENT LIFE CHAPTER: {existing_chapter}

PROJECT SUMMARIES:
{libraries_text}

Create a JSON object that captures where this person is in life:

{{
    "current_chapter_of_life": "A one-sentence description of their current life phase",
    "core_values": ["value1", "value2", "value3"],
    "long_term_goals": [
        {{"goal": "Goal description", "progress": 0.5}},
        {{"goal": "Another goal", "progress": 0.3}}
    ],
    "life_themes": ["Theme 1", "Theme 2"],
    "key_relationships": [
        {{"name": "Person", "role": "relationship"}}
    ],
    "current_challenges": ["Challenge 1", "Challenge 2"],
    "recent_wins": ["Win 1", "Win 2"]
}}

JSON OUTPUT (valid JSON only):"""

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are synthesizing a life narrative. Output ONLY valid JSON."
            },
            {"role": "user", "content": synthesis_prompt}
        ],
        max_tokens=1000,
        temperature=0.5
    )
    
    content = response.choices[0].message.content.strip()
    
    # Parse JSON
    try:
        # Handle markdown code blocks
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        narrative = json.loads(content)
    except json.JSONDecodeError:
        # Keep existing if parsing fails
        narrative = state['existing_narrative'] or {}
    
    return {
        **state,
        'updated_narrative': narrative
    }


def save_life_narrative(state: LifeNarrativeState) -> LifeNarrativeState:
    """Save the life narrative to FriendProfile."""
    from apps.cognitive.models import FriendProfile
    
    FriendProfile.objects.filter(user_id=state['user_id']).update(
        life_narrative=state['updated_narrative']
    )
    
    return state


def build_life_narrative_graph():
    """Build the life narrative synthesis graph."""
    workflow = StateGraph(LifeNarrativeState)
    
    workflow.add_node("load_context", load_narrative_context)
    workflow.add_node("synthesize", synthesize_life_narrative)
    workflow.add_node("save", save_life_narrative)
    
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "synthesize")
    workflow.add_edge("synthesize", "save")
    workflow.add_edge("save", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# COMPILED GRAPHS (Singletons)
# ═══════════════════════════════════════════════════════════════════════════════

chapter_summary_graph = build_chapter_summary_graph()
library_summary_graph = build_library_summary_graph()
life_narrative_graph = build_life_narrative_graph()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def compress_chapter(chapter_id: str, chapter_title: str, existing_summary: str, new_messages: List[str]) -> dict:
    """Convenience function to run chapter compression."""
    initial_state: ChapterSummaryState = {
        'chapter_id': chapter_id,
        'chapter_title': chapter_title,
        'existing_summary': existing_summary,
        'new_messages': new_messages,
        'updated_summary': '',
        'key_facts_extracted': [],
        'emotional_moments': []
    }
    
    return chapter_summary_graph.invoke(initial_state)


def aggregate_library(library_id: str, library_title: str, existing_summary: str, chapter_summaries: List[dict]) -> dict:
    """Convenience function to run library aggregation."""
    initial_state: LibrarySummaryState = {
        'library_id': library_id,
        'library_title': library_title,
        'existing_summary': existing_summary,
        'chapter_summaries': chapter_summaries,
        'updated_summary': '',
        'main_themes': [],
        'progress_notes': []
    }
    
    return library_summary_graph.invoke(initial_state)


def synthesize_narrative(user_id: str, existing_narrative: dict, library_summaries: List[dict]) -> dict:
    """Convenience function to run life narrative synthesis."""
    initial_state: LifeNarrativeState = {
        'user_id': user_id,
        'existing_narrative': existing_narrative,
        'library_summaries': library_summaries,
        'updated_narrative': {}
    }
    
    return life_narrative_graph.invoke(initial_state)
