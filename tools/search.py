"""PGVector-style search using numpy + PostgreSQL JSONB."""
import json
import numpy as np
import psycopg2
from config import PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD


def cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def search_questions(
    query_embedding: list = None,
    module: str = None,
    difficulty: int = None,
    tags: list = None,
    keyword: str = None,
    top_k: int = 5
) -> list[dict]:
    """
    Hybrid search: optional vector similarity + structured filters + keyword.
    Returns list of question dicts sorted by relevance.
    """
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()

    # Build query
    conditions = []
    params = []

    if module:
        conditions.append("module = %s")
        params.append(module)

    if difficulty:
        conditions.append("difficulty = %s")
        params.append(difficulty)

    if tags:
        conditions.append("tags && %s")
        params.append(tags)

    if keyword:
        conditions.append("(question ILIKE %s OR answer ILIKE %s)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where = " AND ".join(conditions) if conditions else "TRUE"
    cur.execute(f"SELECT id, question, answer, module, difficulty, tags, embedding FROM questions WHERE {where}", params)
    rows = cur.fetchall()

    results = []
    for row in rows:
        qid, question, answer, mod, diff, qtags, emb_json = row
        score = 0.0
        if query_embedding and emb_json:
            emb = json.loads(emb_json) if isinstance(emb_json, str) else emb_json
            score = cosine_similarity(query_embedding, emb)
        results.append({
            "id": qid,
            "question": question,
            "answer": answer,
            "module": mod,
            "difficulty": diff,
            "tags": qtags,
            "score": round(score, 4)
        })

    # Sort by score descending, then by id
    results.sort(key=lambda x: (-x["score"], x["id"]))
    results = results[:top_k]

    cur.close()
    conn.close()
    return results


def get_question_by_id(question_id: int) -> dict:
    """Get full question detail by ID."""
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT id, question, answer, module, difficulty, tags FROM questions WHERE id = %s", (question_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "id": row[0], "question": row[1], "answer": row[2],
            "module": row[3], "difficulty": row[4], "tags": row[5]
        }
    return None


def add_question(question: str, answer: str, module: str, difficulty: int, tags: list = None) -> int:
    """Add a new question to the database. Returns the new question ID."""
    import json, numpy as np
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()
    tag_str = "{" + ",".join(tags) + "}" if tags else "{}"
    cur.execute(
        """INSERT INTO questions (question, answer, module, difficulty, tags)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (question, answer, module, difficulty, tag_str)
    )
    qid = cur.fetchone()[0]
    emb = np.random.randn(1536).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    cur.execute("UPDATE questions SET embedding = %s WHERE id = %s", (json.dumps(emb.tolist()), qid))
    conn.commit()
    cur.close()
    conn.close()
    return qid


def get_all_modules() -> list:
    """Get distinct module names."""
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT module FROM questions ORDER BY module")
    rows = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows
