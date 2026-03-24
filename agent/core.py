"""Core conversational agent — orchestrates LLM calls, extraction, RAG, and sentiment."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from openai import OpenAI

import config
from agent.prompts import SYSTEM_PROMPT
from agent.extraction import extract_customer_issue, generate_summary
from agent.sentiment import analyze_sentiment
from models.schemas import (
    ChatMessage,
    ConversationRecord,
    CustomerIssue,
    Sentiment,
)
from storage.store import ConversationStore

logger = logging.getLogger(__name__)


class SupportAgent:
    """Stateful customer-support conversational agent."""

    def __init__(
        self,
        api_key: str | None = None,
        rag_engine=None,
        store: ConversationStore | None = None,
    ):
        self.client = OpenAI(api_key=api_key or config.OPENAI_API_KEY)
        self.rag_engine = rag_engine
        self.store = store or ConversationStore()

        self.conversation_id = f"conv-{uuid.uuid4().hex[:12]}"
        self.messages: list[ChatMessage] = []
        self.extracted: CustomerIssue = CustomerIssue()
        self._openai_history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ------ public API ------

    def chat(self, user_text: str) -> str:
        """Process a user message and return the agent reply."""
        if not user_text or not user_text.strip():
            return "I didn't catch that. Could you please repeat?"

        user_text = user_text.strip()

        # 1. Sentiment analysis on user message
        sentiment = analyze_sentiment(self.client, user_text)
        user_msg = ChatMessage(role="user", content=user_text, sentiment=sentiment)
        self.messages.append(user_msg)
        self._openai_history.append({"role": "user", "content": user_text})

        # 2. Prune history if it exceeds the limit (keep system + recent turns)
        self._prune_history()

        # 3. RAG context injection (if available) — inject only for the API call
        rag_messages: list[dict] = []
        if self.rag_engine and config.RAG_ENABLED:
            try:
                rag_context = self.rag_engine.query(user_text)
                if rag_context:
                    rag_messages = [{
                        "role": "system",
                        "content": f"Relevant knowledge base information:\n{rag_context}",
                    }]
            except Exception as e:
                logger.warning("RAG query failed: %s", e)

        # 4. LLM response — pass RAG context without persisting it to history
        messages_for_api = self._openai_history + rag_messages
        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=messages_for_api,
                temperature=config.LLM_TEMPERATURE,
                max_tokens=500,
            )
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            reply = "I'm sorry, I'm experiencing technical difficulties. Please try again in a moment."

        assistant_msg = ChatMessage(role="assistant", content=reply)
        self.messages.append(assistant_msg)
        self._openai_history.append({"role": "assistant", "content": reply})

        # 5. Background extraction (every turn, lightweight)
        try:
            self.extracted = extract_customer_issue(self.client, self.messages)
        except Exception as e:
            logger.warning("Extraction failed: %s", e)

        return reply

    def get_extracted_data(self) -> CustomerIssue:
        return self.extracted

    def end_conversation(self) -> ConversationRecord:
        """Finalise, summarise, persist, and return the conversation record."""
        try:
            summary = generate_summary(self.client, self.messages)
        except Exception as e:
            logger.warning("Summary generation failed: %s", e)
            from models.schemas import ConversationSummary
            summary = ConversationSummary(summary="Summary generation failed.")

        record = ConversationRecord(
            conversation_id=self.conversation_id,
            ended_at=datetime.utcnow(),
            messages=self.messages,
            extracted_data=self.extracted,
            summary=summary,
        )
        try:
            self.store.save(record)
            logger.info("Conversation %s saved.", self.conversation_id)
        except Exception as e:
            logger.error("Failed to save conversation %s: %s", self.conversation_id, e)
        return record

    def _prune_history(self) -> None:
        """Keep conversation history within token-safe limits."""
        max_msgs = config.MAX_HISTORY_MESSAGES
        # Always keep the system message (index 0), prune oldest turns
        if len(self._openai_history) > max_msgs:
            system_msg = self._openai_history[0]
            # Keep the most recent messages
            self._openai_history = [system_msg] + self._openai_history[-(max_msgs - 1):]

    def reset(self):
        """Start a fresh conversation."""
        self.__init__(rag_engine=self.rag_engine, store=self.store)
