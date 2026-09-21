import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessments (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    created_by INTEGER REFERENCES users(id),
    time_limit INTEGER DEFAULT 60,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER REFERENCES assessments(id),
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    difficulty TEXT DEFAULT 'Medium'
);

CREATE TABLE IF NOT EXISTS question_bank (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    difficulty TEXT DEFAULT 'Medium'
);

CREATE TABLE IF NOT EXISTS responses (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES users(id),
    assessment_id INTEGER REFERENCES assessments(id),
    question_id INTEGER REFERENCES questions(id),
    selected_option TEXT,
    is_correct INTEGER,
    time_taken INTEGER DEFAULT 0,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES users(id),
    assessment_id INTEGER REFERENCES assessments(id),
    total_score INTEGER DEFAULT 0,
    max_score INTEGER DEFAULT 0,
    percentage REAL DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    avg_time_per_q REAL DEFAULT 0,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

""")

conn.commit()

cur.close()
conn.close()

print("✅ PostgreSQL tables created successfully!")