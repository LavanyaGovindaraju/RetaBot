"""Structured data extraction from conversations using LLM."""

from __future__ import annotations

import json
import logging
import re
from openai import OpenAI

import config
from agent.prompts import EXTRACTION_PROMPT, SUMMARY_PROMPT
from models.schemas import CustomerIssue, ConversationSummary, ChatMessage

logger = logging.getLogger(__name__)


def _format_conversation(messages: list[ChatMessage]) -> str:
    lines = []
    for m in messages:
        role = "Customer" if m.role == "user" else "Agent"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


def _parse_json_response(raw: str) -> dict:
    """Robustly extract JSON from LLM response, handling markdown fences."""
    raw = raw.strip()
    # Try extracting from markdown code fences
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find any JSON object in the response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}


def extract_customer_issue(client: OpenAI, messages: list[ChatMessage]) -> CustomerIssue:
    """Extract structured customer issue data from conversation messages."""
    conversation_text = _format_conversation(messages)
    prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        data = _parse_json_response(raw)
        if not data:
            return CustomerIssue()
        return CustomerIssue(**{k: v for k, v in data.items() if v is not None})
    except Exception as e:
        logger.warning("Extraction failed: %s", e)
        return CustomerIssue()


def generate_summary(client: OpenAI, messages: list[ChatMessage]) -> ConversationSummary:
    """Generate a conversation summary with key points."""
    conversation_text = _format_conversation(messages)
    prompt = SUMMARY_PROMPT.format(conversation=conversation_text)

    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        data = _parse_json_response(raw)
        if not data:
            return ConversationSummary(summary="Summary generation failed.")
        return ConversationSummary(**data)
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return ConversationSummary(summary="Summary generation failed.")
