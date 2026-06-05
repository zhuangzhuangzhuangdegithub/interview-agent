"""Extract Q&A from desktop interview doc and import to database."""
import psycopg2
import json
import numpy as np
import re
from docx import Document

doc = Document(r"C:\Users\HUAWEI\Desktop\大厂大模型实习面经详解.docx")

# Extract Q&A pairs
qa_pairs = []
current_q = None
current_a = []
current_module = "LLM基础"

module_map = {
    "3.1": "LLM基础",
    "3.2": "RAG与知识库",
    "3.3": "Agent架构",
    "3.4": "微调与部署",
    "3.5": "Prompt工程",
    "3.6": "模型部署与推理",
    "3.7": "系统设计与场景",
}

for para in doc.paragraphs:
    text = para.text.strip()
    if not text:
        continue

    # Detect module
    for key, mod in module_map.items():
        if text.startswith(key):
            current_module = mod
            break

    # Detect Q&A
    q_match = re.match(r"Q[：:]\s*(.+)", text)
    if q_match:
        if current_q and current_a:
            qa_pairs.append({"q": current_q, "a": "\n".join(current_a), "module": current_module})
        current_q = q_match.group(1).strip()
        current_a = []
    elif current_q:
        # Skip non-content lines
        if not any(text.startswith(s) for s in ["��", "��", "��", "��", "Ŀ¼", "�ص�"]):
            current_a.append(text)

# Don't forget the last one
if current_q and current_a:
    qa_pairs.append({"q": current_q, "a": "\n".join(current_a), "module": current_module})

print(f"Extracted {len(qa_pairs)} Q&A pairs")

# Import to database
conn = psycopg2.connect(host="localhost", port=5432, dbname="interview_agent", user="postgres", password="postgres")
cur = conn.cursor()

# Get existing questions to avoid duplicates
cur.execute("SELECT question FROM questions")
existing = {row[0] for row in cur.fetchall()}

count = 0
for qa in qa_pairs:
    if qa["q"] in existing:
        continue
    # Map difficulty based on length and module
    difficulty = 2  # Default medium
    if len(qa["a"]) < 200:
        difficulty = 1
    elif len(qa["a"]) > 800:
        difficulty = 3

    # Extract tags
    tags = []
    for keyword, tag in [
        ("Attention", "Attention"), ("Transformer", "Transformer"), ("RAG", "RAG"),
        ("Agent", "Agent"), ("微调", "微调"), ("LoRA", "LoRA"),
        ("Prompt", "Prompt"), ("向量", "向量"), ("Chunk", "Chunking"),
        ("ReAct", "ReAct"), ("MCP", "MCP"), ("部署", "部署"),
    ]:
        if keyword.lower() in (qa["q"] + qa["a"]).lower():
            tags.append(tag)

    cur.execute(
        "INSERT INTO questions (question, answer, module, difficulty, tags) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (qa["q"], qa["a"], qa["module"], difficulty, "{" + ",".join(tags[:5]) + "}" if tags else "{}")
    )
    qid = cur.fetchone()[0]
    emb = np.random.randn(1536).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    cur.execute("UPDATE questions SET embedding = %s WHERE id = %s", (json.dumps(emb.tolist()), qid))
    count += 1

conn.commit()

# Show final stats
cur.execute("SELECT count(*), module FROM questions GROUP BY module ORDER BY count(*) DESC")
for row in cur.fetchall():
    print(f"  {row[1]}: {row[0]} questions")
cur.close(); conn.close()
print(f"Added {count} new questions from document")
