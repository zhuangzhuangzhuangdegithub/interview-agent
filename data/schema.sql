-- Interview Agent Database Schema (Development Version)
-- Uses JSON for embeddings (pgvector upgrade: just change column type)

-- 题目主表
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    module VARCHAR(50) NOT NULL,
    difficulty SMALLINT CHECK (difficulty BETWEEN 1 AND 3),
    tags TEXT[] DEFAULT '{}',
    source VARCHAR(50) DEFAULT 'builtin',
    embedding JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questions_module ON questions(module);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);

-- 练习记录
CREATE TABLE IF NOT EXISTS practice_records (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    question_id INTEGER REFERENCES questions(id),
    user_answer TEXT,
    score SMALLINT CHECK (score BETWEEN 0 AND 10),
    feedback TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_practice_session ON practice_records(session_id);

-- 用户画像
CREATE TABLE IF NOT EXISTS user_profile (
    id SERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 训练数据（微调用）
CREATE TABLE IF NOT EXISTS training_data (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id),
    user_answer TEXT NOT NULL,
    score SMALLINT CHECK (score BETWEEN 0 AND 10),
    feedback TEXT,
    reviewed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
