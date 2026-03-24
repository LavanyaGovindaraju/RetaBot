"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "conversations"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# --- Speech ---
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() == "true"
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")  # edge-tts voice
STT_ENABLED = os.getenv("STT_ENABLED", "true").lower() == "true"

# --- RAG ---
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.2"))

# --- Conversation ---
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))

# --- Agent ---
AGENT_NAME = os.getenv("AGENT_NAME", "TechMart Support")
COMPANY_NAME = os.getenv("COMPANY_NAME", "TechMart")
