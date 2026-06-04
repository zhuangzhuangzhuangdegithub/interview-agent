"""Application configuration. Reads .env directly to avoid env-var issues."""
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")


def _read_env():
    """Parse .env file directly, return dict."""
    config = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    config[key.strip()] = value.strip()
    return config


_env = _read_env()

# ── LLM ──
LLM_API_KEY = _env.get("DEEPSEEK_API_KEY", "")
LLM_API_BASE = _env.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
LLM_MODEL = _env.get("LLM_MODEL", "deepseek-chat")
EMBEDDING_MODEL = _env.get("EMBEDDING_MODEL", "text-embedding-3-small")

# ── Database ──
PG_HOST = _env.get("PG_HOST", "localhost")
PG_PORT = int(_env.get("PG_PORT", "5432"))
PG_DATABASE = _env.get("PG_DATABASE", "interview_agent")
PG_USER = _env.get("PG_USER", "postgres")
PG_PASSWORD = _env.get("PG_PASSWORD", "postgres")

REDIS_HOST = _env.get("REDIS_HOST", "localhost")
REDIS_PORT = int(_env.get("REDIS_PORT", "6379"))
REDIS_DB = int(_env.get("REDIS_DB", "0"))

# ── Agent ──
AGENT_MAX_ITERATIONS = int(_env.get("AGENT_MAX_ITERATIONS", "10"))
AGENT_VERBOSE = _env.get("AGENT_VERBOSE", "true").lower() == "true"
SESSION_TTL = int(_env.get("SESSION_TTL", "3600"))

# ── Paths ──
PG_DATA_DIR = _env.get("PG_DATA_DIR", "D:/PostgreSQL/15/data")
REDIS_DATA_DIR = _env.get("REDIS_DATA_DIR", "D:/Redis/data")
FINE_TUNED_MODEL_PATH = _env.get("FINE_TUNED_MODEL_PATH", "./models/qwen-interview-lora")
