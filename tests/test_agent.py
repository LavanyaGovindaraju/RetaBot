"""Tests for core agent, extraction, storage, and schemas."""

import json
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.schemas import (
    CustomerIssue,
    ProblemCategory,
    UrgencyLevel,
    Sentiment,
    ChatMessage,
    ConversationRecord,
    ConversationSummary,
)
from storage.store import ConversationStore
from agent.core import SupportAgent


# ===================== Schema Tests =====================

class TestCustomerIssue:
    def test_completeness_empty(self):
        issue = CustomerIssue()
        comp = issue.completeness()
        assert comp["pct"] == 0
        assert len(comp["missing"]) == 4

    def test_completeness_partial(self):
        issue = CustomerIssue(order_number="ORD-12345", problem_category=ProblemCategory.SHIPPING)
        comp = issue.completeness()
        assert comp["pct"] == 50
        assert "order_number" in comp["filled"]
        assert "problem_description" in comp["missing"]

    def test_completeness_full(self):
        issue = CustomerIssue(
            order_number="ORD-99999",
            problem_category=ProblemCategory.PAYMENT,
            problem_description="Double charged on my card",
            urgency_level=UrgencyLevel.HIGH,
        )
        comp = issue.completeness()
        assert comp["pct"] == 100
        assert comp["missing"] == []


class TestChatMessage:
    def test_default_timestamp(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.timestamp is not None
        assert msg.role == "user"

    def test_with_sentiment(self):
        msg = ChatMessage(role="user", content="I'm upset!", sentiment=Sentiment.FRUSTRATED)
        assert msg.sentiment == Sentiment.FRUSTRATED


class TestConversationRecord:
    def test_serialization_roundtrip(self):
        record = ConversationRecord(
            conversation_id="test-123",
            messages=[ChatMessage(role="user", content="hi")],
            extracted_data=CustomerIssue(order_number="ORD-00001"),
            summary=ConversationSummary(summary="Test summary", key_points=["point1"]),
        )
        json_str = record.model_dump_json()
        restored = ConversationRecord(**json.loads(json_str))
        assert restored.conversation_id == "test-123"
        assert restored.extracted_data.order_number == "ORD-00001"
        assert restored.summary.key_points == ["point1"]


# ===================== Storage Tests =====================

class TestConversationStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = ConversationStore(data_dir=Path(self.tmpdir))

    def test_save_and_load(self):
        record = ConversationRecord(
            conversation_id="conv-001",
            messages=[ChatMessage(role="user", content="test")],
        )
        self.store.save(record)
        loaded = self.store.load("conv-001")
        assert loaded is not None
        assert loaded.conversation_id == "conv-001"
        assert len(loaded.messages) == 1

    def test_load_nonexistent(self):
        assert self.store.load("nonexistent") is None

    def test_list_conversations(self):
        for i in range(3):
            record = ConversationRecord(
                conversation_id=f"conv-{i:03d}",
                messages=[ChatMessage(role="user", content=f"msg {i}")],
            )
            self.store.save(record)
        convos = self.store.list_conversations()
        assert len(convos) == 3

    def test_delete(self):
        record = ConversationRecord(conversation_id="conv-del")
        self.store.save(record)
        assert self.store.delete("conv-del") is True
        assert self.store.load("conv-del") is None
        assert self.store.delete("conv-del") is False


# ===================== Extraction Tests (mocked LLM) =====================

class TestExtraction:
    @patch("agent.extraction.config")
    def test_extract_customer_issue_happy_path(self, mock_config):
        mock_config.LLM_MODEL = "gpt-4o-mini"
        from agent.extraction import extract_customer_issue

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "order_number": "ORD-12345",
            "problem_category": "shipping",
            "problem_description": "My package hasn't arrived",
            "urgency_level": "medium",
            "customer_name": "John",
            "customer_email": None,
            "product_name": "Wireless Mouse",
        })
        mock_client.chat.completions.create.return_value = mock_response

        messages = [
            ChatMessage(role="user", content="My order ORD-12345 hasn't arrived. It's a wireless mouse."),
            ChatMessage(role="assistant", content="I'll look into that for you."),
        ]
        result = extract_customer_issue(mock_client, messages)
        assert result.order_number == "ORD-12345"
        assert result.problem_category == ProblemCategory.SHIPPING
        assert result.urgency_level == UrgencyLevel.MEDIUM

    @patch("agent.extraction.config")
    def test_extract_handles_llm_failure(self, mock_config):
        mock_config.LLM_MODEL = "gpt-4o-mini"
        from agent.extraction import extract_customer_issue

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        messages = [ChatMessage(role="user", content="help")]
        result = extract_customer_issue(mock_client, messages)
        assert result.order_number is None  # graceful fallback


class TestSummary:
    @patch("agent.extraction.config")
    def test_generate_summary_happy_path(self, mock_config):
        mock_config.LLM_MODEL = "gpt-4o-mini"
        from agent.extraction import generate_summary

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "summary": "Customer reported a shipping delay for order ORD-12345.",
            "key_points": ["Order not arrived", "Wireless mouse product"],
            "resolution": "Offered reshipment",
            "overall_sentiment": "neutral",
        })
        mock_client.chat.completions.create.return_value = mock_response

        messages = [
            ChatMessage(role="user", content="Where is my order?"),
            ChatMessage(role="assistant", content="Let me check."),
        ]
        result = generate_summary(mock_client, messages)
        assert "shipping" in result.summary.lower()
        assert len(result.key_points) == 2


# ===================== Sentiment Tests (mocked) =====================

class TestSentiment:
    @patch("agent.sentiment.config")
    def test_analyze_sentiment(self, mock_config):
        mock_config.LLM_MODEL = "gpt-4o-mini"
        from agent.sentiment import analyze_sentiment

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "frustrated"
        mock_client.chat.completions.create.return_value = mock_response

        result = analyze_sentiment(mock_client, "This is ridiculous! I've been waiting forever!")
        assert result == Sentiment.FRUSTRATED

    @patch("agent.sentiment.config")
    def test_analyze_sentiment_fallback(self, mock_config):
        mock_config.LLM_MODEL = "gpt-4o-mini"
        from agent.sentiment import analyze_sentiment

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("fail")
        result = analyze_sentiment(mock_client, "test")
        assert result == Sentiment.NEUTRAL


# ===================== Order Number Validation Tests =====================

class TestOrderNumberValidation:
    def test_valid_order_number(self):
        issue = CustomerIssue(order_number="ORD-12345")
        assert issue.order_number == "ORD-12345"

    def test_valid_order_number_longer(self):
        issue = CustomerIssue(order_number="ORD-1234567890")
        assert issue.order_number == "ORD-1234567890"

    def test_invalid_order_number_letters(self):
        issue = CustomerIssue(order_number="ORD-abcde")
        assert issue.order_number is None

    def test_invalid_order_number_no_prefix(self):
        issue = CustomerIssue(order_number="12345")
        assert issue.order_number is None

    def test_invalid_order_number_too_short(self):
        issue = CustomerIssue(order_number="ORD-12")
        assert issue.order_number is None

    def test_none_order_number(self):
        issue = CustomerIssue(order_number=None)
        assert issue.order_number is None


# ===================== JSON Parsing Tests =====================

class TestJsonParsing:
    def test_parse_clean_json(self):
        from agent.extraction import _parse_json_response
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_in_markdown_fences(self):
        from agent.extraction import _parse_json_response
        raw = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parse_json_in_fences_no_lang(self):
        from agent.extraction import _parse_json_response
        raw = '```\n{"key": "value"}\n```'
        result = _parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parse_json_with_surrounding_text(self):
        from agent.extraction import _parse_json_response
        raw = 'Here is the result:\n{"key": "value"}\nDone.'
        result = _parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parse_invalid_json_returns_empty(self):
        from agent.extraction import _parse_json_response
        result = _parse_json_response("not json at all")
        assert result == {}

    def test_parse_empty_string(self):
        from agent.extraction import _parse_json_response
        result = _parse_json_response("")
        assert result == {}


# ===================== Storage Edge Case Tests =====================

class TestConversationStoreEdgeCases:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = ConversationStore(data_dir=Path(self.tmpdir))

    def test_special_characters_in_id(self):
        """IDs with special chars should be sanitized."""
        record = ConversationRecord(conversation_id="conv/../evil")
        self.store.save(record)
        loaded = self.store.load("conv/../evil")
        assert loaded is not None
        assert loaded.conversation_id == "conv/../evil"

    def test_empty_messages(self):
        """Should handle conversations with no messages."""
        record = ConversationRecord(conversation_id="conv-empty", messages=[])
        self.store.save(record)
        loaded = self.store.load("conv-empty")
        assert loaded is not None
        assert len(loaded.messages) == 0

    def test_list_conversations_with_corrupt_file(self):
        """Corrupt files should be skipped in listing."""
        self.store.save(ConversationRecord(conversation_id="valid"))
        (Path(self.tmpdir) / "corrupt.json").write_text("{bad", encoding="utf-8")
        convos = self.store.list_conversations()
        assert len(convos) == 1
        assert convos[0]["conversation_id"] == "valid"


# ===================== Core Agent Tests (mocked) =====================

class TestSupportAgent:
    def _make_mock_client(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help you today?"
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    @patch("agent.core.analyze_sentiment")
    @patch("agent.core.extract_customer_issue")
    @patch("agent.core.OpenAI")
    def test_chat_returns_reply(self, mock_openai_cls, mock_extract, mock_sentiment):
        mock_client = self._make_mock_client()
        mock_openai_cls.return_value = mock_client
        mock_sentiment.return_value = Sentiment.NEUTRAL
        mock_extract.return_value = CustomerIssue()

        agent = SupportAgent(api_key="test-key")
        agent.client = mock_client
        reply = agent.chat("Hi there")
        assert reply == "Hello! How can I help you today?"
        assert len(agent.messages) == 2  # user + assistant

    @patch("agent.core.analyze_sentiment")
    @patch("agent.core.extract_customer_issue")
    @patch("agent.core.OpenAI")
    def test_chat_empty_input(self, mock_openai_cls, mock_extract, mock_sentiment):
        mock_client = self._make_mock_client()
        mock_openai_cls.return_value = mock_client

        agent = SupportAgent(api_key="test-key")
        agent.client = mock_client
        reply = agent.chat("")
        assert "didn't catch" in reply.lower()
        assert len(agent.messages) == 0

    @patch("agent.core.analyze_sentiment")
    @patch("agent.core.extract_customer_issue")
    @patch("agent.core.OpenAI")
    def test_chat_llm_failure_graceful(self, mock_openai_cls, mock_extract, mock_sentiment):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        mock_openai_cls.return_value = mock_client
        mock_sentiment.return_value = Sentiment.NEUTRAL
        mock_extract.return_value = CustomerIssue()

        agent = SupportAgent(api_key="test-key")
        agent.client = mock_client
        reply = agent.chat("Help me")
        assert "technical difficulties" in reply.lower()

    @patch("agent.core.analyze_sentiment")
    @patch("agent.core.extract_customer_issue")
    @patch("agent.core.OpenAI")
    def test_multiturn_messages_accumulate(self, mock_openai_cls, mock_extract, mock_sentiment):
        mock_client = self._make_mock_client()
        mock_openai_cls.return_value = mock_client
        mock_sentiment.return_value = Sentiment.NEUTRAL
        mock_extract.return_value = CustomerIssue()

        agent = SupportAgent(api_key="test-key")
        agent.client = mock_client
        agent.chat("First message")
        agent.chat("Second message")
        agent.chat("Third message")
        assert len(agent.messages) == 6  # 3 user + 3 assistant

    @patch("agent.core.generate_summary")
    @patch("agent.core.OpenAI")
    def test_end_conversation_saves(self, mock_openai_cls, mock_summary):
        mock_openai_cls.return_value = MagicMock()
        mock_summary.return_value = ConversationSummary(summary="Test")

        store = ConversationStore(data_dir=Path(tempfile.mkdtemp()))
        agent = SupportAgent(api_key="test-key", store=store)
        record = agent.end_conversation()
        assert record.conversation_id == agent.conversation_id
        assert store.load(record.conversation_id) is not None


# ===================== Audio Validation Tests =====================

class TestSTTValidation:
    def test_empty_audio(self):
        from speech.stt import transcribe_audio
        result = transcribe_audio(b"")
        assert result == ""

    def test_oversized_audio(self):
        from speech.stt import transcribe_audio
        huge = b"\x00" * (26 * 1024 * 1024)  # 26 MB
        result = transcribe_audio(huge)
        assert result == ""
