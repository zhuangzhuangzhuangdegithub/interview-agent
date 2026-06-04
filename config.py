"""Application configuration. Loads from environment variables with sensible defaults."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ──
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ── Paths (D drive) ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
D_DRIVE_ROOT = os.getenv("D_DRIVE_ROOT", "D:/")
PG_DATA_DIR = os.getenv("PG_DATA_DIR", "D:/PostgreSQL/15/data")
REDIS_DATA_DIR = os.getenv("REDIS_DATA_DIR", "D:/Redis/data")
REDIS_CONFIG = os.getenv("REDIS_CONFIG", "D:/Redis/redis.conf")

# ── Database ──
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "interview_agent")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# ── Agent ──
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
AGENT_VERBOSE = os.getenv("AGENT_VERBOSE", "true").lower() == "true"
SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))  # Redis TTL: 1 hour

# ── Fine-tuning (future) ──
FINE_TUNED_MODEL_PATH = os.getenv("FINE_TUNED_MODEL_PATH", "./models/qwen-interview-lora")
