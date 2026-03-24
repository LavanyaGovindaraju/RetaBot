"""JSON-based conversation storage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from models.schemas import ConversationRecord
import config


class ConversationStore:
    """Persist and retrieve conversation records as JSON files."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or config.DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, conversation_id: str) -> Path:
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)
        return self.data_dir / f"{safe_id}.json"

    def save(self, record: ConversationRecord) -> Path:
        """Save a conversation record to disk."""
        path = self._path(record.conversation_id)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, conversation_id: str) -> ConversationRecord | None:
        """Load a conversation record from disk."""
        path = self._path(conversation_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ConversationRecord(**data)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return None

    def list_conversations(self) -> list[dict]:
        """Return metadata for all stored conversations."""
        results = []
        for p in sorted(self.data_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                results.append({
                    "conversation_id": data.get("conversation_id"),
                    "started_at": data.get("started_at"),
                    "message_count": len(data.get("messages", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return results

    def delete(self, conversation_id: str) -> bool:
        path = self._path(conversation_id)
        if path.exists():
            path.unlink()
            return True
        return False
