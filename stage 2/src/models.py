"""
Pydantic models for validated AI responses.
Used by instructor to enforce structured output from Gemini.
"""

from typing import Optional, Union
from pydantic import BaseModel, Field, model_validator
from typing import Literal


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
# DRAFT REPLY
# =============================================================================

class DraftReplyResult(BaseModel):
    """Validated schema for drafted customer reply."""

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
