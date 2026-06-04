"""Practice tools: save records, user profile, analytics."""
import json
import psycopg2
import redis
from datetime import datetime
from config import (
    PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD,
    REDIS_HOST, REDIS_PORT, REDIS_DB
)

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return _redis


def save_practice_record(session_id: str, question_id: int, user_answer: str, score: int, feedback: str):
    """Save a practice record to PostgreSQL."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO practice_records (session_id, question_id, user_answer, score, feedback)
           VALUES (%s, %s, %s, %s, %s)""",
        (session_id, question_id, user_answer, score, feedback)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_user_profile() -> dict:
    """Get user profile from Redis (hot) or PostgreSQL (cold)."""
    r = _get_redis()
    profile = r.get("user_profile")
    if profile:
        return json.loads(profile)

    # Fallback to PG
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()
    cur.execute("SELECT value FROM user_profile WHERE key = 'default'")
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return row[0]
    return {
        "weak_modules": {},
        "mastered_topics": [],
        "total_practiced": 0,
        "total_correct": 0,
        "avg_score": 0,
    }


def update_user_profile(module: str, tags: list, score: int):
    """Update user profile based on practice result."""
    r = _get_redis()
    profile = get_user_profile()

    profile["total_practiced"] = profile.get("total_practiced", 0) + 1
    if score >= 7:
        profile["total_correct"] = profile.get("total_correct", 0) + 1
        if module in profile["weak_modules"]:
            profile["weak_modules"][module] = max(0, profile["weak_modules"][module] - 0.5)
    else:
        profile["weak_modules"][module] = profile["weak_modules"].get(module, 0) + 1

    if score >= 8:
        for tag in tags:
            if tag not in profile["mastered_topics"]:
                profile["mastered_topics"].append(tag)

    n = profile["total_practiced"]
    old_avg = profile.get("avg_score", 0)
    profile["avg_score"] = round((old_avg * (n - 1) + score) / n, 2)

    # Save to Redis (TTL 24h) and PG
    r.setex("user_profile", 86400, json.dumps(profile, ensure_ascii=False))

    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO user_profile (key, value, updated_at)
           VALUES ('default', %s, NOW())
           ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()""",
        (json.dumps(profile), json.dumps(profile))
    )
    conn.commit()
    cur.close()
    conn.close()


def get_session_stats(session_id: str) -> dict:
    """Get statistics for a practice session."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()
    cur.execute(
        """SELECT q.module, q.difficulty, pr.score, q.tags
           FROM practice_records pr JOIN questions q ON pr.question_id = q.id
           WHERE pr.session_id = %s ORDER BY pr.created_at""",
        (session_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return {"total": 0, "modules": {}, "avg_score": 0, "weak_areas": []}

    scores = [r[2] for r in rows if r[2] is not None]
    modules = {}
    for r in rows:
        mod = r[0]
        if mod not in modules:
            modules[mod] = {"count": 0, "scores": []}
        modules[mod]["count"] += 1
        if r[2]:
            modules[mod]["scores"].append(r[2])

    weak = [mod for mod, data in modules.items()
            if data["scores"] and sum(data["scores"]) / len(data["scores"]) < 6]

    return {
        "total": len(rows),
        "modules": {m: {"count": d["count"], "avg": round(sum(d["scores"])/len(d["scores"]), 1) if d["scores"] else 0}
                     for m, d in modules.items()},
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "weak_areas": weak,
    }
