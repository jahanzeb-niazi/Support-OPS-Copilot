"""
AI Service module — Stage 2: Reliability.
Uses instructor + Pydantic for validated, structured output from Gemini.
Every call retries up to 3 times on validation failure, then fails gracefully.
Low-confidence results are flagged for human review.
"""

import os
import json
import logging
from typing import TypeVar, cast, Any
from google import genai
from dotenv import load_dotenv
import instructor
from typing import Optional

from src.models import (
    ClassificationResult,
    ExtractedDataResult,
    DraftReplyResult,
    CONFIDENCE_THRESHOLD,
)
from src.prompts import (
    CLASSIFY_SYSTEM_PROMPT, CLASSIFY_FEW_SHOT,
    REPLY_SYSTEM_PROMPT, REPLY_FEW_SHOT,
    EXTRACT_SYSTEM_PROMPT, EXTRACT_FEW_SHOT,
)

load_dotenv()

raw_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
client = instructor.from_genai(raw_client, mode=instructor.Mode.JSON)

MODEL_NAME = "gemini-3.1-flash-lite"
MAX_RETRIES = 3

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT", ClassificationResult, DraftReplyResult, ExtractedDataResult)


def _call_gemini(
    system_prompt: str,
    few_shot: list,
    user_input: str,
    response_model: type[ResultT],
) -> ResultT:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    for content in few_shot:
        role = content.role
        text = content.parts[0].text
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role == "model":
            messages.append({"role": "model", "content": text})

    messages.append({"role": "user", "content": user_input})

    try:
        result = client.chat.completions.create(
            model=MODEL_NAME,
            messages=cast(Any, messages),
            response_model=response_model,
            max_retries=MAX_RETRIES,
        )
        if result.confidence < CONFIDENCE_THRESHOLD:
            result.flagged_for_review = True
        return result

    except Exception as e:
        logger.error(f"All {MAX_RETRIES} retries failed: {e}")
        return _graceful_fallback(response_model, str(e))


def _graceful_fallback(response_model: type[ResultT], error_msg: str) -> ResultT:
    if response_model is ClassificationResult:
        return cast(ResultT, ClassificationResult(
            category="general",
            urgency="low",
            confidence=0.0,
            reasoning=f"Failed after {MAX_RETRIES} retries: {error_msg}",
            flagged_for_review=True,
        ))
    elif response_model is DraftReplyResult:
        return cast(ResultT, DraftReplyResult(
            subject="Re: Your Support Request",
            body=(
                "Hi there,\n\n"
                "We received your message but need a human agent to review it. "
                "A team member will follow up with you shortly.\n\n"
                "Best regards,\nSupport Team"
            ),
            tone="professional",
            confidence=0.0,
            flagged_for_review=True,
        ))
    elif response_model is ExtractedDataResult:
        return cast(ResultT, ExtractedDataResult(
            issue=f"Extraction failed after {MAX_RETRIES} retries: {error_msg}",
            confidence=0.0,
            flagged_for_review=True,
        ))
    else:
        raise ValueError(f"Unknown response model: {response_model}")


def classify_ticket(ticket_text: str) -> ClassificationResult:
    """
    Classify an incoming support ticket by category and urgency.
    Returns a validated ClassificationResult with confidence scoring.
    """
    if not ticket_text or not ticket_text.strip():
        return ClassificationResult(
            category="general",
            urgency="low",
            confidence=0.0,
            reasoning="Empty or blank ticket — cannot classify.",
            flagged_for_review=True,
        )

    return _call_gemini(CLASSIFY_SYSTEM_PROMPT, CLASSIFY_FEW_SHOT, ticket_text, ClassificationResult)


def draft_reply(ticket_text: str, classification: Optional[ClassificationResult] = None) -> DraftReplyResult:
    """
    Draft a professional reply based on ticket text and its classification.
    Returns a validated DraftReplyResult with confidence scoring.
    """
    if not ticket_text or not ticket_text.strip():
        return DraftReplyResult(
            subject="Re: Your Support Request",
            body=(
                "Hi there,\n\n"
                "It looks like your message was empty. "
                "Could you please describe your issue so we can help?\n\n"
                "Best regards,\nSupport Team"
            ),
            tone="friendly",
            confidence=0.0,
            flagged_for_review=True,
        )

    # Combine ticket + classification as context for the reply
    if classification is not None:
        classification_data = json.dumps(classification.model_dump())
    else:
        classification_data = json.dumps({"error": "Classification failed"})

    combined_input = (
        f'Ticket: "{ticket_text}"\n'
        f'Classification: {classification_data}'
    )
    return _call_gemini(REPLY_SYSTEM_PROMPT, REPLY_FEW_SHOT, combined_input, DraftReplyResult)


def extract_data(ticket_text: str) -> ExtractedDataResult:
    """
    Extract structured data from a raw support ticket message.
    Returns a validated ExtractedDataResult with confidence scoring.
    """
    if not ticket_text or not ticket_text.strip():
        return ExtractedDataResult(
            issue="Empty or blank ticket — nothing to extract.",
            confidence=0.0,
            flagged_for_review=True,
        )

    return _call_gemini(EXTRACT_SYSTEM_PROMPT, EXTRACT_FEW_SHOT, ticket_text, ExtractedDataResult)
