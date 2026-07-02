"""
Core SHL Assessment Recommendation Agent
Handles conversation state, intent classification, and response generation
"""
import json
import os
import re
import random
from typing import List, Dict, Optional, Tuple

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Use new google-genai package
try:
    from google import genai
    from google.genai import types as genai_types
    _USE_NEW_SDK = True
except ImportError:
    import google.generativeai as genai_old
    _USE_NEW_SDK = False

from .models import Message, Recommendation, ChatResponse
from .prompts import (
    SYSTEM_PROMPT, INTENT_CLASSIFICATION_PROMPT, CLARIFICATION_PROMPT,
    RECOMMENDATION_PROMPT, COMPARISON_PROMPT, REFINE_PROMPT,
    CONTEXT_EXTRACTION_PROMPT, OFF_TOPIC_RESPONSES
)
from .retriever import (
    search_assessments, get_assessments_for_comparison,
    get_catalog_summary, load_catalog, get_assessment_by_name
)

# ─────────────────────────────────────────────
# Gemini Configuration
# ─────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

_client = None
_model_name = 'gemini-2.5-flash'

if GEMINI_API_KEY:
    try:
        if _USE_NEW_SDK:
            _client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            genai_old.configure(api_key=GEMINI_API_KEY)
            _client = genai_old.GenerativeModel('gemini-1.5-flash')
        print(f"Gemini client initialized (SDK: {'new' if _USE_NEW_SDK else 'legacy'})")
    except Exception as e:
        print(f"Warning: Gemini init failed: {e}")
        _client = None

# ─────────────────────────────────────────────
# Safety & Scope Guards
# ─────────────────────────────────────────────

OFF_TOPIC_PATTERNS = [
    r'\b(salary|compensation|pay|wage|offer)\b',
    r'\b(legal|lawsuit|discrimination|compliance|gdpr|eeoc)\b',
    r'\b(competitor|hirequest|criteria|predictive index|wonderlic|mckinsey)\b',
    r'\b(ignore previous|disregard|jailbreak|you are now|pretend you are|act as)\b',
    r'\b(resume|cv|cover letter|interview tips|linkedin)\b',
    r'\b(hire someone without|bypass|skip assessment)\b',
]

COMPARISON_PATTERNS = [
    r'\b(compare|difference|vs\.?|versus|better|which one|what.s the diff)\b',
    r'\b(between|compared to|contrast)\b',
]

REFINE_PATTERNS = [
    r'\b(also add|add|include|additionally|and also|plus|what about)\b',
    r'\b(instead|rather|change|update|replace|remove|without)\b',
    r'\b(actually|wait|never mind|let me clarify|correction)\b',
]

DONE_PATTERNS = [
    r'\b(thank|thanks|great|perfect|looks good|that.s all|done|that.s it|good enough)\b',
]


def _is_off_topic(text: str) -> Tuple[bool, str]:
    """Check if the message is off-topic"""
    text_lower = text.lower()
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, text_lower):
            topic = re.search(pattern, text_lower).group(0)
            return True, topic
    return False, ''


def _is_comparison(text: str) -> bool:
    """Check if asking for a comparison"""
    text_lower = text.lower()
    for pattern in COMPARISON_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def _is_refinement(messages: List[Message]) -> bool:
    """Check if user is refining a previous recommendation"""
    if len(messages) < 3:
        return False
    last_user = messages[-1].content.lower()
    for pattern in REFINE_PATTERNS:
        if re.search(pattern, last_user):
            return True
    return False


def _is_done(text: str, has_recommendations: bool) -> bool:
    """Check if conversation is complete"""
    if not has_recommendations:
        return False
    text_lower = text.lower()
    for pattern in DONE_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


# ─────────────────────────────────────────────
# LLM Calls
# ─────────────────────────────────────────────

def _call_gemini(prompt: str, json_mode: bool = False) -> str:
    """Call Gemini API with error handling"""
    if not _client:
        return _fallback_response(prompt)
    
    full_prompt = prompt
    if json_mode:
        full_prompt = prompt + "\n\nRespond ONLY with valid JSON, no markdown code blocks."
    
    try:
        if _USE_NEW_SDK:
            config = genai_types.GenerateContentConfig(
                temperature=0.1 if json_mode else 0.3,
                max_output_tokens=2048,
            )
            response = _client.models.generate_content(
                model=_model_name,
                contents=full_prompt,
                config=config
            )
            return response.text.strip()
        else:
            # Legacy SDK
            response = _client.generate_content(full_prompt)
            return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return _fallback_response(prompt)


def _fallback_response(prompt: str) -> str:
    """Basic fallback when API is unavailable"""
    return "I need more information about the role you're hiring for. Could you tell me the job title and the key skills you need to assess?"


def _classify_intent(conversation: str, turn_count: int) -> str:
    """Classify conversation intent"""
    prompt = INTENT_CLASSIFICATION_PROMPT.format(conversation=conversation)
    result = _call_gemini(prompt).strip().upper()
    
    valid = {'VAGUE', 'SPECIFIC', 'REFINE', 'COMPARE', 'OFF_TOPIC', 'DONE'}
    if result not in valid:
        # Default to VAGUE on first turn, SPECIFIC otherwise
        return 'VAGUE' if turn_count <= 1 else 'SPECIFIC'
    return result


def _extract_context(conversation: str) -> Dict:
    """Extract structured context from conversation"""
    prompt = CONTEXT_EXTRACTION_PROMPT.format(conversation=conversation)
    result = _call_gemini(prompt, json_mode=True)
    
    try:
        # Clean JSON
        result = re.sub(r'```(?:json)?\s*', '', result)
        result = result.strip().rstrip('`')
        return json.loads(result)
    except Exception:
        return {
            'job_role': None,
            'seniority_level': None,
            'skills_needed': [],
            'technical_domain': None,
            'assessment_goal': None,
            'industries': [],
            'has_enough_context': False
        }


def _build_search_query(context: Dict, messages: List[Message]) -> str:
    """Build a rich search query from extracted context"""
    parts = []
    
    if context.get('job_role'):
        parts.append(context['job_role'])
    if context.get('technical_domain'):
        parts.append(context['technical_domain'])
    if context.get('skills_needed'):
        parts.extend(context['skills_needed'][:5])
    if context.get('seniority_level'):
        parts.append(context['seniority_level'])
    
    # Also include the last user message
    last_user_msg = next((m.content for m in reversed(messages) if m.role == 'user'), '')
    if last_user_msg:
        parts.append(last_user_msg)
    
    return ' '.join(parts) if parts else ' '.join(m.content for m in messages[-2:] if m.role == 'user')


def _format_conv(messages: List[Message]) -> str:
    """Format conversation history as text"""
    lines = []
    for m in messages:
        role = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role}: {m.content}")
    return '\n'.join(lines)


def _format_context_summary(context: Dict) -> str:
    """Format extracted context as readable summary"""
    parts = []
    if context.get('job_role'):
        parts.append(f"Role: {context['job_role']}")
    if context.get('seniority_level'):
        parts.append(f"Seniority: {context['seniority_level']}")
    if context.get('technical_domain'):
        parts.append(f"Technical domain: {context['technical_domain']}")
    if context.get('skills_needed'):
        parts.append(f"Skills needed: {', '.join(context['skills_needed'])}")
    if context.get('assessment_goal'):
        parts.append(f"Goal: {context['assessment_goal']}")
    if context.get('industries'):
        parts.append(f"Industry: {', '.join(context['industries'])}")
    return ' | '.join(parts) if parts else "Unclear hiring need"


def _format_assessments_for_prompt(assessments: List[Dict]) -> str:
    """Format assessment list for LLM prompt"""
    lines = []
    for a in assessments:
        types = ', '.join(a.get('product_types', [])) or a.get('test_type', '')
        desc = a.get('description', '')[:200]
        url = a.get('url', '')
        lines.append(
            f"- Name: {a['name']}\n"
            f"  URL: {url}\n"
            f"  Test Type: {a['test_type']} ({types})\n"
            f"  Description: {desc}\n"
        )
    return '\n'.join(lines)


def _extract_json_recommendations(llm_response: str, catalog: List[Dict]) -> Tuple[str, List[Recommendation], bool]:
    """
    Parse LLM JSON response and validate recommendations against catalog
    """
    try:
        # Clean markdown code blocks
        cleaned = re.sub(r'```(?:json)?\s*', '', llm_response).strip().rstrip('`')
        data = json.loads(cleaned)
        
        reply = data.get('reply', '')
        end_of_conv = data.get('end_of_conversation', False)
        raw_recs = data.get('recommendations', [])
        
        # Validate and clean recommendations
        # Build a name→product lookup
        catalog_by_name = {p['name'].lower(): p for p in catalog}
        catalog_list = catalog
        
        validated_recs = []
        for rec in raw_recs[:10]:
            name = rec.get('name', '')
            url = rec.get('url', '')
            test_type = rec.get('test_type', 'A')
            
            # Try to find in catalog to validate URL
            match = catalog_by_name.get(name.lower())
            if not match:
                # Fuzzy match
                for p in catalog_list:
                    if name.lower() in p['name'].lower() or p['name'].lower() in name.lower():
                        match = p
                        break
            
            if match:
                # Use catalog data for accuracy
                validated_recs.append(Recommendation(
                    name=match['name'],
                    url=match['url'],
                    test_type=match['test_type']
                ))
            elif url and 'shl.com' in url:
                # Trust the URL if it's from shl.com
                validated_recs.append(Recommendation(
                    name=name,
                    url=url,
                    test_type=test_type
                ))
        
        return reply, validated_recs, end_of_conv
    
    except Exception as e:
        print(f"JSON parse error: {e}\nRaw: {llm_response[:200]}")
        return llm_response, [], False


def _find_comparison_subjects(messages: List[Message]) -> List[str]:
    """Extract assessment names from comparison request"""
    last_msg = messages[-1].content if messages else ''
    catalog = load_catalog()
    
    found = []
    for product in catalog:
        name = product['name']
        if name.lower() in last_msg.lower():
            found.append(name)
    
    # Also check common abbreviations
    abbrev_map = {
        'opq': 'Occupational Personality Questionnaire (OPQ - OPQ32r)',
        'gsa': 'Global Skills Assessment',
        'mq': 'Motivation Questionnaire (MQ)',
        'sjt': 'Situational Judgement Tests',
        'verify': 'Verify',
        'verify g+': 'Verify - Cognitive Ability',
    }
    
    for abbrev, full_name in abbrev_map.items():
        if re.search(r'\b' + re.escape(abbrev) + r'\b', last_msg.lower()):
            product = get_assessment_by_name(full_name)
            if product and product['name'] not in found:
                found.append(product['name'])
    
    return found[:5]


# ─────────────────────────────────────────────
# Turn Counter
# ─────────────────────────────────────────────

def _get_turn_count(messages: List[Message]) -> int:
    """Count total turns (messages)"""
    return len(messages)


def _get_clarification_turns(messages: List[Message]) -> int:
    """Count how many times we've asked for clarification"""
    count = 0
    for m in messages:
        if m.role == 'assistant' and '?' in m.content:
            count += 1
    return count


def _has_previous_recommendations(messages: List[Message]) -> bool:
    """Check if any previous assistant message had recommendations marker"""
    for m in messages:
        if m.role == 'assistant' and ('recommend' in m.content.lower() or 'assessment' in m.content.lower()):
            if len(m.content) > 100:  # substantial response
                return True
    return False


# ─────────────────────────────────────────────
# Main Agent Function
# ─────────────────────────────────────────────

async def process_chat(messages: List[Message]) -> ChatResponse:
    """
    Main entry point for processing a chat turn.
    
    Args:
        messages: Full conversation history (stateless)
    
    Returns:
        ChatResponse with reply, recommendations, and end_of_conversation flag
    """
    catalog = load_catalog()
    turn_count = _get_turn_count(messages)
    conversation = _format_conv(messages)
    last_user_msg = messages[-1].content if messages else ''
    
    # ── 1. Safety: Off-topic / injection guard ──────────────────────
    is_off_topic, topic = _is_off_topic(last_user_msg)
    if is_off_topic:
        response_template = random.choice(OFF_TOPIC_RESPONSES)
        reply = response_template.format(topic=topic)
        return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)
    
    # ── 2. Check if conversation is done ───────────────────────────
    has_prev_recs = _has_previous_recommendations(messages[:-1])
    if _is_done(last_user_msg, has_prev_recs):
        return ChatResponse(
            reply="Great! I'm glad I could help you find the right SHL assessments. Feel free to return if you need assessment recommendations for other roles.",
            recommendations=[],
            end_of_conversation=True
        )
    
    # ── 3. Comparison request ───────────────────────────────────────
    if _is_comparison(last_user_msg) and has_prev_recs:
        subjects = _find_comparison_subjects(messages)
        if subjects:
            assessment_data = get_assessments_for_comparison(subjects)
            if assessment_data:
                formatted_data = _format_assessments_for_prompt(assessment_data)
                prompt = COMPARISON_PROMPT.format(
                    assessment_data=formatted_data,
                    question=last_user_msg
                )
                reply = _call_gemini(prompt)
                return ChatResponse(
                    reply=reply,
                    recommendations=[],
                    end_of_conversation=False
                )
    
    # ── 4. Extract context from conversation ────────────────────────
    context = _extract_context(conversation)
    context_summary = _format_context_summary(context)
    
    # ── 5. Determine if we should recommend or clarify ─────────────
    clarification_turns = _get_clarification_turns(messages)
    
    # Force recommend if: we've clarified enough OR context is sufficient
    should_recommend = (
        context.get('has_enough_context', False) or
        clarification_turns >= 3 or  # Asked 3 questions, just recommend
        turn_count >= 7  # Approaching turn cap
    )
    
    # Override: refinement always leads to re-recommendation
    if _is_refinement(messages) and has_prev_recs:
        should_recommend = True
    
    # ── 6. Refinement path ──────────────────────────────────────────
    if _is_refinement(messages) and has_prev_recs and should_recommend:
        search_query = _build_search_query(context, messages)
        relevant = search_assessments(search_query, k=20)
        formatted = _format_assessments_for_prompt(relevant)
        
        prompt = REFINE_PROMPT.format(
            conversation=conversation,
            refinement_request=last_user_msg,
            current_recommendations="[See previous assistant messages]",
            relevant_assessments=formatted
        )
        llm_response = _call_gemini(prompt, json_mode=True)
        reply, recs, end_conv = _extract_json_recommendations(llm_response, catalog)
        
        if recs:
            return ChatResponse(reply=reply, recommendations=recs, end_of_conversation=end_conv)
    
    # ── 7. Recommendation path ──────────────────────────────────────
    if should_recommend:
        search_query = _build_search_query(context, messages)
        relevant = search_assessments(search_query, k=20)
        
        if not relevant:
            # Broad fallback search
            relevant = search_assessments(last_user_msg, k=20)
        
        formatted = _format_assessments_for_prompt(relevant)
        
        prompt = RECOMMENDATION_PROMPT.format(
            context_summary=context_summary,
            conversation=conversation,
            relevant_assessments=formatted
        )
        llm_response = _call_gemini(prompt, json_mode=True)
        reply, recs, end_conv = _extract_json_recommendations(llm_response, catalog)
        
        if recs:
            return ChatResponse(reply=reply, recommendations=recs, end_of_conversation=end_conv)
        else:
            # Fallback: use top results directly
            top_recs = [
                Recommendation(name=p['name'], url=p['url'], test_type=p['test_type'])
                for p in relevant[:5]
            ]
            return ChatResponse(
                reply=f"Based on your needs ({context_summary}), here are the most relevant SHL assessments:",
                recommendations=top_recs,
                end_of_conversation=False
            )
    
    # ── 8. Clarification path ───────────────────────────────────────
    prompt = CLARIFICATION_PROMPT.format(
        conversation=conversation,
        context_summary=context_summary
    )
    clarifying_question = _call_gemini(prompt)
    
    return ChatResponse(
        reply=clarifying_question,
        recommendations=[],
        end_of_conversation=False
    )
