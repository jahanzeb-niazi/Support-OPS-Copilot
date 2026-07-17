"""
Pydantic models for validated AI responses.
Used by instructor to enforce structured output from Gemini.
Stage 3 adds SourceCitation for RAG-grounded answers.
Stage 4 adds ToolCallRequest and AgentPlan for tool-calling agent.
"""

from typing import Any, Optional, Union, Literal
from pydantic import BaseModel, Field, model_validator


import json as _json
import logging; logger = logging.getLogger(__name__)
# Confidence threshold — below this, results are flagged for human review
CONFIDENCE_THRESHOLD = 0.7


# =============================================================================
# CLASSIFICATION
# =============================================================================

class ClassificationResult(BaseModel):
    """Validated schema for ticket classification output."""

    category: Literal[
        "billing", "shipping", "technical", "account", "product", "general"
    ] = Field(
        description="The single best category for this ticket."
    )
    urgency: Literal["critical", "high", "medium", "low"] = Field(
        description="How urgent this ticket is based on actual impact."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How certain you are about this classification (0.0 to 1.0). "
                    "Use below 0.7 if the ticket is vague, ambiguous, or nonsensical."
    )
    reasoning: str = Field(
        description="Brief explanation of why you chose this category and urgency."
    )
    flagged_for_review: bool = Field(
        default=False,
        description="Set to true if you are uncertain and this should be reviewed by a human."
    )

    @model_validator(mode="after")
    def enforce_flag(self):
        """Server-side enforcement: always flag low-confidence results."""
        if self.confidence < CONFIDENCE_THRESHOLD:
            self.flagged_for_review = True
        return self


# =============================================================================
# SOURCE CITATION (RAG)
# =============================================================================

class SourceCitation(BaseModel):
    """A citation linking an AI answer to the knowledge base chunk it came from."""

    doc_name: str = Field(
        description="Name of the source document."
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page number in the source document."
    )
    chunk_id: str = Field(
        description="ID of the chunk in the knowledge base."
    )
    chunk_preview: str = Field(
        description="First ~100 characters of the chunk content for verification."
    )


# =============================================================================
# AGENT TOOL CALLING (Stage 4)
# =============================================================================

class ToolCallRequest(BaseModel):
    """A single tool the agent wants to call."""

    tool_name: str = Field(
        description="Name of the tool to call. Must match one of the available tools."
    )
    arguments_json: str = Field(
        default="{}",
        description=(
            "Arguments to pass to the tool, encoded as a JSON object string. "
            'Example: \'{"order_id": "12345", "reason": "customer requested refund"}\'. '
            'Use "{}" if the tool takes no arguments.'
        )
    )
    reason: str = Field(
        description="Brief explanation of why this tool should be called."
    )

    @property
    def arguments(self) -> dict[str, Any]:
        """Parsed arguments dict, for backward compatibility with existing callers."""
        try:
            parsed = _json.loads(self.arguments_json)
            return parsed if isinstance(parsed, dict) else {}
        except (_json.JSONDecodeError, TypeError):
            logger.warning(f"Could not parse arguments_json: {self.arguments_json!r}")
            return {}


class AgentPlan(BaseModel):
    """The agent's plan of which tools to invoke for a ticket."""

    tool_calls: list[ToolCallRequest] = Field(
        default_factory=list,
        description="Ordered list of tools to call. Empty if no tools are needed."
    )
    reasoning: str = Field(
        description="Overall reasoning for why these tools were chosen (or why none are needed)."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident you are in this plan (0.0 to 1.0)."
    )


# =============================================================================
# DRAFT REPLY
# =============================================================================

class DraftReplyResult(BaseModel):
    """Validated schema for drafted customer reply with source citations."""

    subject: str = Field(
        min_length=1,
        description="Email subject line for the reply."
    )
    body: str = Field(
        min_length=1,
        description="The full reply body to send to the customer."
    )
    tone: str = Field(
        description="The tone used in the reply (e.g. friendly, urgent-empathetic, professional)."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident you are that this reply is appropriate (0.0 to 1.0). "
                    "Use below 0.7 if the ticket was vague or you had to guess."
    )
    flagged_for_review: bool = Field(
        default=False,
        description="Set to true if a human should review this reply before sending."
    )
    sources: list[SourceCitation] = Field(
        default_factory=list,
        description="Citations for knowledge base chunks used to generate this reply. "
                    "MUST include at least one source if knowledge base context was provided."
    )

    @model_validator(mode="after")
    def enforce_flag(self):
        """Server-side enforcement: always flag low-confidence results."""
        if self.confidence < CONFIDENCE_THRESHOLD:
            self.flagged_for_review = True
        return self


# =============================================================================
# DATA EXTRACTION
# =============================================================================

class ExtractedDataResult(BaseModel):
    """Validated schema for extracted ticket data."""

    name: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Customer name(s) if mentioned. Use a list if multiple names appear."
    )
    email: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Customer email(s) if mentioned. Use a list if multiple emails appear."
    )
    order_id: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Order/reference number(s) if mentioned. Use a list if multiple. "
                    "Do NOT extract phone numbers, zip codes, or years as order IDs."
    )
    issue: str = Field(
        description="One-sentence summary of the core issue."
    )
    product: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Product name(s) if mentioned. Use a list if multiple."
    )
    date_mentioned: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Any dates referenced in the ticket. Null if none."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident you are in the extracted data (0.0 to 1.0). "
                    "Use below 0.7 if the ticket was vague or information was ambiguous."
    )
    flagged_for_review: bool = Field(
        default=False,
        description="Set to true if the extraction is uncertain and needs human verification."
    )

    @model_validator(mode="after")
    def enforce_flag(self):
        """Server-side enforcement: always flag low-confidence results."""
        if self.confidence < CONFIDENCE_THRESHOLD:
            self.flagged_for_review = True
        return self
