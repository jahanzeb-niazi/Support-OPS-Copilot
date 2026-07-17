"""
AI Service module — the core of the Support OPS Copilot.
Three functions powered by Google Gemini with role-based and few-shot prompting.
"""

import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

from src.prompts import (
    CLASSIFY_SYSTEM_PROMPT, CLASSIFY_FEW_SHOT,
    REPLY_SYSTEM_PROMPT, REPLY_FEW_SHOT,
    EXTRACT_SYSTEM_PROMPT, EXTRACT_FEW_SHOT,
)

# Load API key from .env
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_NAME = "gemini-3.1-flash-lite"


def _call_gemini(system_prompt: str, few_shot: list, user_input: str) -> dict:
    """
    Shared helper to call Gemini with a system prompt, few-shot examples, and user input.
    Returns parsed JSON dict from the model response.
    """
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        temperature=0.3,  # Low temp for consistency
    )

    # Build conversation history: few-shot examples + the actual user input
    history = list(few_shot)  # copy so we don't mutate the original

    chat = client.chats.create(
        model=MODEL_NAME,
        config=config,
        history=history,
    )
    response = chat.send_message(user_input)

    # Parse the JSON response
    text = response.text

    if text is None:
        return {
            "error": "Gemini returned no text."
        }

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse model response as JSON",
            "raw": text,
        }


def classify_ticket(ticket_text: str) -> dict:
    """
    Classify an incoming support ticket by category and urgency.
    
    Args:
        ticket_text: The raw customer message.
    
    Returns:
        dict with keys: category, urgency, confidence, reasoning
    """
    if not ticket_text or not ticket_text.strip():
        return {
            "category": "unclassifiable",
            "urgency": "low",
            "confidence": 0.0,
            "reasoning": "Empty or blank ticket — cannot classify.",
        }

    return _call_gemini(CLASSIFY_SYSTEM_PROMPT, CLASSIFY_FEW_SHOT, ticket_text)


def draft_reply(ticket_text: str, classification: dict) -> dict:
    """
    Draft a professional reply to the customer based on ticket text and classification.
    
    Args:
        ticket_text: The raw customer message.
        classification: Output from classify_ticket().
    
    Returns:
        dict with keys: subject, body, tone
    """
    if not ticket_text or not ticket_text.strip():
        return {
            "subject": "Re: Your Support Request",
            "body": "Hi there,\n\nIt looks like your message was empty. Could you please describe your issue so we can help?\n\nBest regards,\nSupport Team",
            "tone": "friendly",
        }

    # Combine ticket + classification as input
    combined_input = f'Ticket: "{ticket_text}"\nClassification: {json.dumps(classification)}'
    return _call_gemini(REPLY_SYSTEM_PROMPT, REPLY_FEW_SHOT, combined_input)


def extract_data(ticket_text: str) -> dict:
    """
    Extract structured data from a raw support ticket message.
    
    Args:
        ticket_text: The raw customer message.
    
    Returns:
        dict with keys: name, email, order_id, issue, product, date_mentioned
    """
    if not ticket_text or not ticket_text.strip():
        return {
            "name": None,
            "email": None,
            "order_id": None,
            "issue": None,
            "product": None,
            "date_mentioned": None,
        }

    return _call_gemini(EXTRACT_SYSTEM_PROMPT, EXTRACT_FEW_SHOT, ticket_text)
