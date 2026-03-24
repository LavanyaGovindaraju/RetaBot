"""Sentiment analysis for customer messages."""

from __future__ import annotations

import logging
from openai import OpenAI

import config
from agent.prompts import SENTIMENT_PROMPT
from models.schemas import Sentiment

logger = logging.getLogger(__name__)

VALID_SENTIMENTS = {s.value for s in Sentiment}


def analyze_sentiment(client: OpenAI, message: str) -> Sentiment:
    """Classify a single customer message sentiment."""
    prompt = SENTIMENT_PROMPT.format(message=message)
    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip().lower()
        if result in VALID_SENTIMENTS:
            return Sentiment(result)
        return Sentiment.NEUTRAL
    except Exception as e:
        logger.warning("Sentiment analysis failed: %s", e)
        return Sentiment.NEUTRAL
