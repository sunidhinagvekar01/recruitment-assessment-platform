import sqlite3

def init_database():
    conn = sqlite3.connect('assessment.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT NOT NULL,
        email      TEXT UNIQUE NOT NULL,
        password   TEXT NOT NULL,
        role       TEXT NOT NULL DEFAULT 'candidate',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS assessments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT,
        created_by  INTEGER,
        time_limit  INTEGER DEFAULT 60,
        is_active   INTEGER DEFAULT 1,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id  INTEGER NOT NULL,
        question_text  TEXT NOT NULL,
        option_a       TEXT NOT NULL,
        option_b       TEXT NOT NULL,
        option_c       TEXT NOT NULL,
        option_d       TEXT NOT NULL,
        correct_option TEXT NOT NULL,
        category       TEXT DEFAULT 'General',
        difficulty     TEXT DEFAULT 'Medium',
        FOREIGN KEY (assessment_id) REFERENCES assessments(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS question_bank (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text  TEXT NOT NULL,
    option_a       TEXT NOT NULL,
    option_b       TEXT NOT NULL,
    option_c       TEXT NOT NULL,
    option_d       TEXT NOT NULL,
    correct_option TEXT NOT NULL,
    category       TEXT DEFAULT 'General',
    difficulty     TEXT DEFAULT 'Medium'
)''')

    c.execute('''CREATE TABLE IF NOT EXISTS responses (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id    INTEGER NOT NULL,
        assessment_id   INTEGER NOT NULL,
        question_id     INTEGER NOT NULL,
        selected_option TEXT,
        is_correct      INTEGER,
        time_taken      INTEGER DEFAULT 0,
        answered_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (candidate_id)  REFERENCES users(id),
        FOREIGN KEY (assessment_id) REFERENCES assessments(id),
        FOREIGN KEY (question_id)   REFERENCES questions(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS scores (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id    INTEGER NOT NULL,
        assessment_id   INTEGER NOT NULL,
        total_score     INTEGER DEFAULT 0,
        max_score       INTEGER DEFAULT 0,
        percentage      REAL DEFAULT 0,
        correct_count   INTEGER DEFAULT 0,
        wrong_count     INTEGER DEFAULT 0,
        skipped_count   INTEGER DEFAULT 0,
        avg_time_per_q  REAL DEFAULT 0,
        completed_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (candidate_id)  REFERENCES users(id),
        FOREIGN KEY (assessment_id) REFERENCES assessments(id)
    )''')

    # Seed a recruiter account
    try:
        import hashlib
        pw = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                  ('Admin Recruiter','admin@company.com', pw, 'recruiter'))
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()
    print("Database created successfully!")
    print("Recruiter login: admin@company.com / admin123")

if __name__ == '__main__':
    init_database()
