"""Conversation memory & user knowledge model using Redis + PostgreSQL."""
import json
import redis
from datetime import datetime, timedelta
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# ── Conversation Memory ──
def save_conversation(session_id: str, messages: list):
    """Save conversation history to Redis with 24h TTL."""
    key = f"conv:{session_id}"
    data = json.dumps(messages[-50:], ensure_ascii=False)  # Keep last 50 turns
    r.setex(key, 86400, data)

def load_conversation(session_id: str) -> list:
    """Load conversation history from Redis."""
    data = r.get(f"conv:{session_id}")
    return json.loads(data) if data else []


# ── User Knowledge Model ──
def get_user_model(user_id: str = "default") -> dict:
    """Get user's knowledge model: strengths, weaknesses, level, history."""
    data = r.get(f"user_model:{user_id}")
    if data:
        return json.loads(data)
    return {
        "level": 1,              # 1-5 overall level
        "modules": {},           # {module: {avg_score, count, streak}}
        "total_answered": 0,
        "total_correct": 0,
        "weak_topics": [],       # Topics scoring <6
        "strong_topics": [],     # Topics scoring >=8
        "preferred_difficulty": 2,
        "learning_pace": "normal",  # slow/normal/fast
    }

def update_user_model(user_id: str, module: str, score: int, topics: list):
    """Update user model after each answer."""
    model = get_user_model(user_id)
    model["total_answered"] += 1
    if score >= 7:
        model["total_correct"] += 1

    # Module stats
    if module not in model["modules"]:
        model["modules"][module] = {"avg_score": 0, "count": 0, "streak": 0}
    m = model["modules"][module]
    m["avg_score"] = round((m["avg_score"] * m["count"] + score) / (m["count"] + 1), 1)
    m["count"] += 1
    m["streak"] = m["streak"] + 1 if score >= 7 else 0

    # Update weak/strong topics
    for t in topics:
        if score < 6 and t not in model["weak_topics"]:
            model["weak_topics"].append(t)
        if score >= 8 and t in model["weak_topics"]:
            model["weak_topics"].remove(t)
        if score >= 8 and t not in model["strong_topics"]:
            model["strong_topics"].append(t)

    # Adapt difficulty
    avg = model["total_correct"] / max(1, model["total_answered"])
    if avg > 0.8:
        model["preferred_difficulty"] = min(3, model["preferred_difficulty"] + 1)
    elif avg < 0.5:
        model["preferred_difficulty"] = max(1, model["preferred_difficulty"] - 1)

    # Overall level
    model["level"] = min(5, 1 + model["total_answered"] // 20)

    # Learning pace
    recent = model.get("_recent_scores", [])
    recent.append(score)
    if len(recent) > 10:
        recent.pop(0)
    model["_recent_scores"] = recent
    if len(recent) >= 5:
        avg_recent = sum(recent) / len(recent)
        if avg_recent > 7.5: model["learning_pace"] = "fast"
        elif avg_recent < 5: model["learning_pace"] = "slow"
        else: model["learning_pace"] = "normal"

    r.setex(f"user_model:{user_id}", 604800, json.dumps(model, ensure_ascii=False))  # 7 day TTL
    return model


def get_adaptive_difficulty(user_id: str = "default") -> int:
    """Get recommended difficulty based on user model."""
    model = get_user_model(user_id)
    return model.get("preferred_difficulty", 2)


def get_weak_modules(user_id: str = "default") -> list:
    """Get user's weakest modules for targeted practice."""
    model = get_user_model(user_id)
    modules = model.get("modules", {})
    if not modules:
        return []
    sorted_mods = sorted(modules.items(), key=lambda x: x[1].get("avg_score", 0))
    return [m[0] for m in sorted_mods if m[1].get("avg_score", 10) < 7]


def format_user_context(user_id: str = "default") -> str:
    """Generate a context string for the agent's system prompt."""
    model = get_user_model(user_id)
    weak = get_weak_modules(user_id)
    return (
        f"User Level: {model['level']}/5 | "
        f"Answered: {model['total_answered']} | "
        f"Accuracy: {round(model['total_correct']/max(1,model['total_answered'])*100)}% | "
        f"Preferred Difficulty: {model['preferred_difficulty']} | "
        f"Weak Modules: {', '.join(weak[:3]) if weak else 'none'}"
    )
