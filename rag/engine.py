"""RAG engine — embeds a JSON knowledge base and retrieves relevant articles."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from openai import OpenAI

import config

logger = logging.getLogger(__name__)

KB_PATH = Path(__file__).resolve().parent / "knowledge_base.json"


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class RAGEngine:
    """Simple in-memory vector-search RAG over the support knowledge base."""

    def __init__(self, client: OpenAI | None = None, kb_path: Path | None = None):
        self.client = client or OpenAI(api_key=config.OPENAI_API_KEY)
        self.kb_path = kb_path or KB_PATH
        self.articles: list[dict] = []
        self.embeddings: list[np.ndarray] = []
        self._loaded = False

    def load(self) -> None:
        """Load and embed the knowledge base articles."""
        data = json.loads(self.kb_path.read_text(encoding="utf-8"))
        self.articles = data.get("articles", [])
        if not self.articles:
            logger.warning("Knowledge base is empty.")
            return

        texts = [f"{a['title']}\n{a['content']}" for a in self.articles]
        try:
            response = self.client.embeddings.create(
                model=config.EMBEDDING_MODEL,
                input=texts,
            )
            self.embeddings = [np.array(e.embedding) for e in response.data]
            self._loaded = True
            logger.info("RAG engine loaded %d articles.", len(self.articles))
        except Exception as e:
            logger.error("Failed to embed knowledge base: %s", e)

    def query(self, question: str, top_k: int | None = None) -> str:
        """Retrieve the most relevant KB articles for a question."""
        if not self._loaded:
            self.load()
        if not self.embeddings:
            return ""

        top_k = top_k or config.RAG_TOP_K
        try:
            q_resp = self.client.embeddings.create(
                model=config.EMBEDDING_MODEL,
                input=[question],
            )
            q_emb = np.array(q_resp.data[0].embedding)
        except Exception as e:
            logger.warning("Query embedding failed: %s", e)
            return ""

        scores = [_cosine_similarity(q_emb, emb) for emb in self.embeddings]
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] < config.RAG_SIMILARITY_THRESHOLD:
                continue
            a = self.articles[idx]
            results.append(f"[{a['id']}] {a['title']}\n{a['content']}")

        return "\n\n---\n\n".join(results)
