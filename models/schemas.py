"""Pydantic models for conversation data, extracted info, and API schemas."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---- Enums ----

class ProblemCategory(str, Enum):
    ORDER_ISSUE = "order_issue"
    PAYMENT = "payment"
    SHIPPING = "shipping"
    PRODUCT_DEFECT = "product_defect"
    RETURNS_REFUNDS = "returns_refunds"
    ACCOUNT = "account"
    TECHNICAL = "technical"
    OTHER = "other"


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"


# ---- Chat Messages ----

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sentiment: Optional[Sentiment] = None


# ---- Extracted Customer Data ----

class CustomerIssue(BaseModel):
    """Structured information extracted from the conversation."""
    order_number: Optional[str] = Field(None, description="Customer order number, e.g. ORD-12345")
    problem_category: Optional[ProblemCategory] = None
    problem_description: Optional[str] = None
    urgency_level: Optional[UrgencyLevel] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    product_name: Optional[str] = None

    @field_validator("order_number")
    @classmethod
    def validate_order_number(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^ORD-\d{3,10}$", v):
            return None
        return v

    def completeness(self) -> dict:
        """Return which required fields are filled vs missing."""
        required = ["order_number", "problem_category", "problem_description", "urgency_level"]
        filled = [f for f in required if getattr(self, f) is not None]
        missing = [f for f in required if getattr(self, f) is None]
        return {"filled": filled, "missing": missing, "pct": len(filled) / len(required) * 100}


# ---- Conversation Record ----

class ConversationSummary(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    resolution: Optional[str] = None
    overall_sentiment: Optional[str] = None


class ConversationRecord(BaseModel):
    """Full persisted conversation with extracted data."""
    conversation_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    messages: list[ChatMessage] = Field(default_factory=list)
    extracted_data: CustomerIssue = Field(default_factory=CustomerIssue)
    summary: Optional[ConversationSummary] = None
    language: str = "en"
