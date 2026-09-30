import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


def get_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)

def ensure_attempts_table():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessment_attempts (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL,
            assessment_id INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            UNIQUE(candidate_id, assessment_id)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ── USER FUNCTIONS ────────────────────────────────────────────────────────

def create_user(name, email, password, role='candidate'):
    conn = get_conn()
    cur = get_cursor(conn)

    try:
        cur.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, hash_password(password), role)
        )
        conn.commit()
        return True, "Account created!"

    except psycopg2.IntegrityError as e:
        conn.rollback()
        return False, f"Database error: {e}"

    finally:
        cur.close()
        conn.close()


def login_user(email, password):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT *
        FROM users
        WHERE email=%s AND password=%s
        """,
        (email, hash_password(password))
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return dict(user) if user else None


def get_user(user_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "SELECT * FROM users WHERE id=%s",
        (user_id,)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return dict(user) if user else None

def get_all_candidates():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute("""
        SELECT id, name, email
        FROM users
        WHERE role = 'candidate'
        ORDER BY name
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(row) for row in rows]


# ── ASSESSMENT FUNCTIONS ──────────────────────────────────────────────────

def get_all_assessments():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT a.*, u.name AS recruiter_name
        FROM assessments a
        JOIN users u ON a.created_by = u.id
        WHERE a.is_active = 1
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(r) for r in rows]


def get_assessment(assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "SELECT * FROM assessments WHERE id=%s",
        (assessment_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return dict(row) if row else None


def create_assessment(title, description, created_by, time_limit=60):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        INSERT INTO assessments
        (title, description, created_by, time_limit)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (title, description, created_by, time_limit)
    )

    assessment_id = cur.fetchone()["id"]

    conn.commit()
    cur.close()
    conn.close()


    return assessment_id


# ── QUESTION FUNCTIONS ────────────────────────────────────────────────────

def add_question(
    assessment_id,
    text,
    a,
    b,
    c,
    d,
    correct,
    category,
    difficulty
):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        INSERT INTO questions
        (
            assessment_id,
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_option,
            category,
            difficulty
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            assessment_id,
            text,
            a,
            b,
            c,
            d,
            correct,
            category,
            difficulty
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def get_question(question_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "SELECT * FROM questions WHERE id=%s",
        (question_id,)
    )

    question = cur.fetchone()

    cur.close()
    conn.close()

    return dict(question) if question else None


def update_question(
    question_id,
    text,
    a,
    b,
    c,
    d,
    correct,
    category,
    difficulty
):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        UPDATE questions
        SET
            question_text=%s,
            option_a=%s,
            option_b=%s,
            option_c=%s,
            option_d=%s,
            correct_option=%s,
            category=%s,
            difficulty=%s
        WHERE id=%s
        """,
        (
            text,
            a,
            b,
            c,
            d,
            correct,
            category,
            difficulty,
            question_id
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def get_questions(assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT *
        FROM questions
        WHERE assessment_id=%s
        ORDER BY RANDOM()
        """,
        (assessment_id,)
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(r) for r in rows]


# ── RESPONSE FUNCTIONS ────────────────────────────────────────────────────

def save_response(
    candidate_id,
    assessment_id,
    question_id,
    selected_option,
    is_correct,
    time_taken
):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        INSERT INTO responses
        (
            candidate_id,
            assessment_id,
            question_id,
            selected_option,
            is_correct,
            time_taken
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            candidate_id,
            assessment_id,
            question_id,
            selected_option,
            is_correct,
            time_taken
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def already_attempted(candidate_id, assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT id
        FROM scores
        WHERE candidate_id=%s AND assessment_id=%s
        """,
        (candidate_id, assessment_id)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row is not None


def attempt_started(candidate_id, assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT id
        FROM assessment_attempts
        WHERE candidate_id=%s
          AND assessment_id=%s
        """,
        (candidate_id, assessment_id)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row is not None


def start_attempt(candidate_id, assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        INSERT INTO assessment_attempts
        (candidate_id, assessment_id)
        VALUES (%s, %s)
        ON CONFLICT (candidate_id, assessment_id)
        DO NOTHING
        """,
        (candidate_id, assessment_id)
    )

    conn.commit()
    cur.close()
    conn.close()


def complete_attempt(candidate_id, assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        UPDATE assessment_attempts
        SET completed_at = CURRENT_TIMESTAMP
        WHERE candidate_id=%s
          AND assessment_id=%s
        """,
        (candidate_id, assessment_id)
    )

    conn.commit()
    cur.close()
    conn.close()


def get_candidate_responses(candidate_id, assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT
            r.*,
            q.question_text,
            q.option_a,
            q.option_b,
            q.option_c,
            q.option_d,
            q.correct_option,
            q.category,
            q.difficulty
        FROM responses r
        JOIN questions q
            ON r.question_id = q.id
        WHERE r.candidate_id=%s
          AND r.assessment_id=%s
        """,
        (candidate_id, assessment_id)
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(r) for r in rows]


# ── SCORE FUNCTIONS ───────────────────────────────────────────────────────

def save_score(
    candidate_id,
    assessment_id,
    total_score,
    max_score,
    percentage,
    correct,
    wrong,
    skipped,
    avg_time
):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        INSERT INTO scores
        (
            candidate_id,
            assessment_id,
            total_score,
            max_score,
            percentage,
            correct_count,
            wrong_count,
            skipped_count,
            avg_time_per_q
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            candidate_id,
            assessment_id,
            total_score,
            max_score,
            percentage,
            correct,
            wrong,
            skipped,
            avg_time
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def get_score(candidate_id, assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT *
        FROM scores
        WHERE candidate_id=%s
          AND assessment_id=%s
        """,
        (candidate_id, assessment_id)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return dict(row) if row else None


def get_all_scores_for_assessment(assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT
            s.*,
            u.name,
            u.email
        FROM scores s
        JOIN users u
            ON s.candidate_id = u.id
        WHERE s.assessment_id=%s
        ORDER BY s.percentage DESC,
                 s.avg_time_per_q ASC
        """,
        (assessment_id,)
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(r) for r in rows]


# ── QUESTION BANK ─────────────────────────────────────────────────────────

def add_question_to_bank(
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
    cur = get_cursor(conn)

    cur.execute(
        """
        INSERT INTO question_bank
        (
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_option,
            category,
            difficulty
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_option,
            category,
            difficulty
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def get_question_bank():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT *
        FROM question_bank
        ORDER BY category, difficulty
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(r) for r in rows]


def delete_question_from_bank(question_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "DELETE FROM question_bank WHERE id=%s",
        (question_id,)
    )

    conn.commit()
    cur.close()
    conn.close()

def delete_question(question_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "DELETE FROM questions WHERE id=%s",
        (question_id,)
    )

    conn.commit()
    cur.close()
    conn.close()


def get_question_from_bank(question_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "SELECT * FROM question_bank WHERE id=%s",
        (question_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return dict(row) if row else None


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
    cur = get_cursor(conn)

    cur.execute(
        """
        UPDATE question_bank
        SET
            question_text=%s,
            option_a=%s,
            option_b=%s,
            option_c=%s,
            option_d=%s,
            correct_option=%s,
            category=%s,
            difficulty=%s
        WHERE id=%s
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
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def bulk_add_questions_to_bank(df):
    conn = get_conn()
    cur = get_cursor(conn)

    for _, row in df.iterrows():
        cur.execute(
            """
            INSERT INTO question_bank
            (
                question_text,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_option,
                category,
                difficulty
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row['question_text'],
                row['option_a'],
                row['option_b'],
                row['option_c'],
                row['option_d'],
                row['correct_option'],
                row['category'],
                row['difficulty']
            )
        )

    conn.commit()
    cur.close()
    conn.close()


# ── ASSESSMENT DELETE ─────────────────────────────────────────────────────

def delete_assessment(assessment_id):
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        "DELETE FROM responses WHERE assessment_id=%s",
        (assessment_id,)
    )

    cur.execute(
        "DELETE FROM scores WHERE assessment_id=%s",
        (assessment_id,)
    )

    cur.execute(
        "DELETE FROM questions WHERE assessment_id=%s",
        (assessment_id,)
    )

    cur.execute(
        "DELETE FROM assessments WHERE id=%s",
        (assessment_id,)
    )

    conn.commit()
    cur.close()
    conn.close()


# ── DASHBOARD FUNCTIONS ───────────────────────────────────────────────────

def get_total_candidates():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT COUNT(DISTINCT candidate_id) AS total
        FROM scores
        """
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row["total"] if row else 0


def get_total_questions():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM questions
        """
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row["total"] if row else 0


def get_completion_rate():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM assessments
        """
    )

    assessments = cur.fetchone()["total"]

    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM scores
        """
    )

    completed = cur.fetchone()["total"]

    cur.close()
    conn.close()

    if assessments == 0:
        return 0

    return round((completed / assessments) * 100)