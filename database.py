import sqlite3
import hashlib

DB = 'assessment.db'

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row   # lets you access columns by name like dict
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ── USER FUNCTIONS ────────────────────────────────────────────────────────

def create_user(name, email, password, role='candidate'):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
            (name, email, hash_password(password), role)
        )
        conn.commit()
        conn.close()
        return True, "Account created!"
    except sqlite3.IntegrityError:
        return False, "Email already registered."

def login_user(email, password):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, hash_password(password))
    ).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

# ── ASSESSMENT FUNCTIONS ──────────────────────────────────────────────────

def get_all_assessments():
    conn = get_conn()
    rows = conn.execute(
        "SELECT a.*, u.name as recruiter_name FROM assessments a JOIN users u ON a.created_by=u.id WHERE a.is_active=1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_assessment(assessment_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_assessment(title, description, created_by, time_limit=60):
    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO assessments (title,description,created_by,time_limit) VALUES (?,?,?,?)",
        (title, description, created_by, time_limit)
    )
    assessment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return assessment_id

# ── QUESTION FUNCTIONS ────────────────────────────────────────────────────

def add_question(assessment_id, text, a, b, c, d, correct, category, difficulty):
    conn = get_conn()
    conn.execute(
        "INSERT INTO questions (assessment_id,question_text,option_a,option_b,option_c,option_d,correct_option,category,difficulty) VALUES (?,?,?,?,?,?,?,?,?)",
        (assessment_id, text, a, b, c, d, correct, category, difficulty)
    )
    conn.commit()
    conn.close()

def get_questions(assessment_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM questions WHERE assessment_id=? ORDER BY RANDOM()",
        (assessment_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── RESPONSE FUNCTIONS ────────────────────────────────────────────────────

def save_response(candidate_id, assessment_id, question_id, selected_option, is_correct, time_taken):
    conn = get_conn()
    conn.execute(
        "INSERT INTO responses (candidate_id,assessment_id,question_id,selected_option,is_correct,time_taken) VALUES (?,?,?,?,?,?)",
        (candidate_id, assessment_id, question_id, selected_option, is_correct, time_taken)
    )
    conn.commit()
    conn.close()

def already_attempted(candidate_id, assessment_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM scores WHERE candidate_id=? AND assessment_id=?",
        (candidate_id, assessment_id)
    ).fetchone()
    conn.close()
    return row is not None

def get_candidate_responses(candidate_id, assessment_id):
    conn = get_conn()
    rows = conn.execute('''
        SELECT r.*, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_option, q.category, q.difficulty
        FROM responses r JOIN questions q ON r.question_id=q.id
        WHERE r.candidate_id=? AND r.assessment_id=?
    ''', (candidate_id, assessment_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── SCORE FUNCTIONS ───────────────────────────────────────────────────────

def save_score(candidate_id, assessment_id, total_score, max_score,
               percentage, correct, wrong, skipped, avg_time):
    conn = get_conn()
    conn.execute('''
        INSERT INTO scores
        (candidate_id,assessment_id,total_score,max_score,percentage,
         correct_count,wrong_count,skipped_count,avg_time_per_q)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', (candidate_id, assessment_id, total_score, max_score,
          percentage, correct, wrong, skipped, avg_time))
    conn.commit()
    conn.close()

def get_score(candidate_id, assessment_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM scores WHERE candidate_id=? AND assessment_id=?",
        (candidate_id, assessment_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_scores_for_assessment(assessment_id):
    conn = get_conn()
    rows = conn.execute('''
        SELECT s.*, u.name, u.email
        FROM scores s JOIN users u ON s.candidate_id=u.id
        WHERE s.assessment_id=?
        ORDER BY s.percentage DESC, s.avg_time_per_q ASC
    ''', (assessment_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_question_to_bank(question_text, option_a, option_b,
                         option_c, option_d, correct_option,
                         category, difficulty):
    conn = get_conn()
    conn.execute('''
        INSERT INTO question_bank
        (question_text, option_a, option_b, option_c,
         option_d, correct_option, category, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        question_text, option_a, option_b,
        option_c, option_d, correct_option,
        category, difficulty
    ))
    conn.commit()
    conn.close()


def get_question_bank():
    conn = get_conn()
    rows = conn.execute('''
        SELECT *
        FROM question_bank
        ORDER BY category, difficulty
    ''').fetchall()
    conn.close()
    return rows

def delete_question_from_bank(question_id):
    conn = get_conn()

    conn.execute(
        "DELETE FROM question_bank WHERE id = ?",
        (question_id,)
    )
def get_question_from_bank(question_id):
    conn = get_conn()

    row = conn.execute(
        "SELECT * FROM question_bank WHERE id=?",
        (question_id,)
    ).fetchone()

    conn.close()

    return row


def update_question_in_bank(
    question_id,
    question_text,
    option_a,
    option_b,
    option_c,
    option_d,
    correct_option,
    category,
    difficulty
):
    conn = get_conn()

    conn.execute("""
        UPDATE question_bank
        SET
            question_text=?,
            option_a=?,
            option_b=?,
            option_c=?,
            option_d=?,
            correct_option=?,
            category=?,
            difficulty=?
        WHERE id=?
    """,
    (
        question_text,
        option_a,
        option_b,
        option_c,
        option_d,
        correct_option,
        category,
        difficulty,
        question_id
    ))


    conn.commit()
    conn.close()