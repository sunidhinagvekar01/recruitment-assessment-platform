from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from database import (create_user, login_user, get_user, get_all_assessments,
                      get_assessment, get_questions, save_response,
                      already_attempted, get_candidate_responses, get_score)
from scoring import calculate_and_save_score, get_rank_label
from analytics import get_candidate_analytics, get_percentile_rank
import json
import pandas as pd
app = Flask(__name__)
app.secret_key = 'recruitment_secret_2025'

# ── HELPER ───────────────────────────────────────────────────────────────

def login_required(role=None):
    """Call at top of any route to guard it."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if role and session.get('role') != role:
        return redirect(url_for('dashboard'))
    return None


# ── AUTH ROUTES ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    error = None
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        ok, msg  = create_user(name, email, password, role='candidate')
        if ok:
            return redirect(url_for('login'))
        error = msg
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user     = login_user(email, password)
        if user:
            session['user_id'] = user['id']
            session['name']    = user['name']
            session['role']    = user['role']
            return redirect(url_for('dashboard'))
        error = 'Incorrect email or password.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── SHARED DASHBOARD ──────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    guard = login_required()
    if guard: return guard
    if session['role'] == 'recruiter':
        return redirect(url_for('recruiter_home'))
    return redirect(url_for('candidate_home'))


# ── CANDIDATE ROUTES ──────────────────────────────────────────────────────

@app.route('/candidate')
def candidate_home():
    guard = login_required('candidate')
    if guard: return guard
    assessments = get_all_assessments()
    completed   = []
    for a in assessments:
        a['attempted'] = already_attempted(session['user_id'], a['id'])
        if a['attempted']:
            completed.append(a['id'])
    return render_template('candidate_home.html',
                           assessments=assessments,
                           name=session['name'])

@app.route('/quiz/<int:assessment_id>')
def quiz(assessment_id):
    guard = login_required('candidate')
    if guard: return guard

    if already_attempted(session['user_id'], assessment_id):
        return redirect(url_for('results', assessment_id=assessment_id))

    assessment = get_assessment(assessment_id)
    questions  = get_questions(assessment_id)

    if not questions:
        return redirect(url_for('candidate_home'))

    # Pass questions to template as JSON (JavaScript reads it)
    questions_json = json.dumps([{
        'id':       q['id'],
        'text':     q['question_text'],
        'options': {
            'A': q['option_a'],
            'B': q['option_b'],
            'C': q['option_c'],
            'D': q['option_d']
        },
        'category':   q['category'],
        'difficulty': q['difficulty'],
        'correct_option': q['correct_option']
    } for q in questions])

    return render_template('quiz.html',
                           assessment=assessment,
                           questions_json=questions_json,
                           total=len(questions))

@app.route('/submit', methods=['POST'])
def submit():
    guard = login_required('candidate')
    if guard: return guard

    data          = request.get_json()
    candidate_id  = session['user_id']
    assessment_id = data['assessment_id']

    if already_attempted(candidate_id, assessment_id):
        return jsonify({'status': 'already_submitted'})

    # Get correct answers from DB to verify (never trust the client!)
    questions = get_questions(assessment_id)
    # Re-fetch without RANDOM so we can match by ID
    import sqlite3
    conn = sqlite3.connect('assessment.db')
    conn.row_factory = sqlite3.Row
    all_q = {row['id']: dict(row) for row in conn.execute(
        "SELECT * FROM questions WHERE assessment_id=?", (assessment_id,)
    ).fetchall()}
    conn.close()

    for answer in data['answers']:
        q_id     = answer['question_id']
        selected = answer.get('selected')   # 'A','B','C','D' or None
        time_taken = answer.get('time_taken', 0)
        q        = all_q.get(q_id)

        if not q:
            continue

        if selected is None:
            is_correct = None    # skipped
        else:
            is_correct = 1 if selected == q['correct_option'] else 0

        save_response(candidate_id, assessment_id, q_id,
                      selected, is_correct, time_taken)

    # Calculate and save the final score
    calculate_and_save_score(candidate_id, assessment_id)

    return jsonify({'status': 'ok',
                    'redirect': f'/results/{assessment_id}'})

@app.route('/results/<int:assessment_id>')
def results(assessment_id):
    guard = login_required('candidate')
    if guard: return guard

    candidate_id = session['user_id']
    score_row    = get_score(candidate_id, assessment_id)

    if not score_row:
        return redirect(url_for('quiz', assessment_id=assessment_id))

    assessment  = get_assessment(assessment_id)
    analytics   = get_candidate_analytics(candidate_id, assessment_id)
    percentile  = get_percentile_rank(candidate_id, assessment_id)
    rank_label, rank_emoji, rank_color = get_rank_label(score_row['percentage'])

    responses = get_candidate_responses(candidate_id, assessment_id)

    return render_template('results.html',
                           score=score_row,
                           assessment=assessment,
                           analytics=analytics,
                           percentile=percentile,
                           rank_label=rank_label,
                           rank_emoji=rank_emoji,
                           rank_color=rank_color,
                           responses=responses,
                           name=session['name'])



@app.route('/recruiter/assessment/<int:assessment_id>/delete')
def delete_assessment_route(assessment_id):

    guard = login_required('recruiter')
    if guard:
        return guard

    from database import delete_assessment

    delete_assessment(assessment_id)

    return redirect('/recruiter')

# ── RECRUITER ROUTES ──────────────────────────────────────────────────────

@app.route('/recruiter')
def recruiter_home():
    guard = login_required('recruiter')
    if guard: return guard
    from database import (
    get_all_assessments,
    get_total_candidates,
    get_total_questions,
    get_completion_rate
)
    assessments = get_all_assessments()
    return render_template(
    'recruiter_home.html',
    assessments=assessments,
    name=session['name'],
    total_candidates=get_total_candidates(),
    total_questions=get_total_questions(),
    completion_rate=get_completion_rate()
)

@app.route('/recruiter/question-bank')
def question_bank():
    guard = login_required('recruiter')
    if guard:
        return guard

    from database import get_question_bank

    questions = get_question_bank()

    search = request.args.get('search', '').lower()
    category = request.args.get('category', '')
    difficulty = request.args.get('difficulty', '')

    if search:
        questions = [
            q for q in questions
            if search in q['question_text'].lower()
        ]

    if category:
        questions = [
            q for q in questions
            if q['category'] == category
        ]

    if difficulty:
        questions = [
            q for q in questions
            if q['difficulty'] == difficulty
        ]

    return render_template(
        'question_bank.html',
        questions=questions,
        name=session['name']
    )

@app.route('/recruiter/question-bank/add', methods=['GET', 'POST'])
def add_question_bank_page():
    guard = login_required('recruiter')
    if guard:
        return guard

    from database import add_question_to_bank

    if request.method == 'POST':
        add_question_to_bank(
            request.form['question_text'],
            request.form['option_a'],
            request.form['option_b'],
            request.form['option_c'],
            request.form['option_d'],
            request.form['correct_option'],
            request.form['category'],
            request.form['difficulty']
        )

        return redirect('/recruiter/question-bank')

    return render_template(
        'add_bank_question.html',
        name=session['name']
    )

@app.route('/recruiter/question-bank/delete/<int:question_id>')
def delete_question_bank(question_id):
    guard = login_required('recruiter')
    if guard:
        return guard

    from database import delete_question_from_bank

    delete_question_from_bank(question_id)

    return redirect('/recruiter/question-bank')

@app.route('/recruiter/question-bank/edit/<int:question_id>',
           methods=['GET', 'POST'])
def edit_question_bank(question_id):

    guard = login_required('recruiter')
    if guard:
        return guard

    from database import (
        get_question_from_bank,
        update_question_in_bank
    )

    question = get_question_from_bank(question_id)

    if request.method == 'POST':

        update_question_in_bank(
            question_id,
            request.form['question_text'],
            request.form['option_a'],
            request.form['option_b'],
            request.form['option_c'],
            request.form['option_d'],
            request.form['correct_option'],
            request.form['category'],
            request.form['difficulty']
        )

        return redirect('/recruiter/question-bank')

    return render_template(
        'edit_question_bank.html',
        question=question
    )

@app.route('/recruiter/create', methods=['GET','POST'])
def create_assessment():
    guard = login_required('recruiter')
    if guard: return guard
    from database import create_assessment as db_create
    if request.method == 'POST':
        title      = request.form['title']
        desc       = request.form['description']
        time_limit = int(request.form.get('time_limit', 60))
        a_id = db_create(title, desc, session['user_id'], time_limit)
        return redirect(url_for('add_questions', assessment_id=a_id))
    return render_template('create_assessment.html')

@app.route('/recruiter/assessment/<int:assessment_id>/add-questions', methods=['GET','POST'])
def add_questions(assessment_id):
    guard = login_required('recruiter')
    if guard: return guard
    from database import add_question
    success = None
    if request.method == 'POST':
        add_question(
            assessment_id,
            request.form['question_text'],
            request.form['option_a'], request.form['option_b'],
            request.form['option_c'], request.form['option_d'],
            request.form['correct_option'],
            request.form['category'],
            request.form['difficulty']
        )
        success = 'Question added!'
    assessment = get_assessment(assessment_id)
    questions  = get_questions(assessment_id)
    return render_template('add_questions.html',
                           assessment=assessment,
                           questions=questions,
                           success=success)

@app.route('/recruiter/<int:assessment_id>/import-questions', methods=['GET', 'POST'])
def import_questions(assessment_id):
    guard = login_required('recruiter')
    if guard:
        return guard

    from database import (
        get_question_bank,
        get_conn
    )

    if request.method == 'POST':

        selected_ids = request.form.getlist('question_ids')

        conn = get_conn()

        for qid in selected_ids:

            q = conn.execute(
                "SELECT * FROM question_bank WHERE id=?",
                (qid,)
            ).fetchone()

            conn.execute("""
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
                VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                assessment_id,
                q['question_text'],
                q['option_a'],
                q['option_b'],
                q['option_c'],
                q['option_d'],
                q['correct_option'],
                q['category'],
                q['difficulty']
            ))

        conn.commit()
        conn.close()

        return redirect(
            f'/recruiter/assessment/{assessment_id}/add-questions'
        )

    assessment = get_assessment(assessment_id)
    questions = get_question_bank()

    return render_template(
        'import_questions.html',
        assessment=assessment,
        questions=questions
    )

@app.route('/recruiter/assessment/<int:assessment_id>/candidates')
def view_candidates(assessment_id):
    guard = login_required('recruiter')
    if guard: return guard
    from database import get_all_scores_for_assessment
    assessment = get_assessment(assessment_id)
    scores     = get_all_scores_for_assessment(assessment_id)
    return render_template('view_candidates.html',
                           assessment=assessment,
                           scores=scores)

@app.route('/recruiter/candidate/<int:candidate_id>/assessment/<int:assessment_id>')
def recruiter_candidate_detail(candidate_id, assessment_id):
    guard = login_required('recruiter')
    if guard: return guard
    candidate  = get_user(candidate_id)
    assessment = get_assessment(assessment_id)
    score_row  = get_score(candidate_id, assessment_id)
    analytics  = get_candidate_analytics(candidate_id, assessment_id)
    responses  = get_candidate_responses(candidate_id, assessment_id)
    rank_label, rank_emoji, rank_color = get_rank_label(
        score_row['percentage'] if score_row else 0
    )
    return render_template('candidate_detail.html',
                           candidate=candidate,
                           assessment=assessment,
                           score=score_row,
                           analytics=analytics,
                           responses=responses,
                           rank_label=rank_label,
                           rank_emoji=rank_emoji,
                           rank_color=rank_color)

@app.route('/recruiter/assessment/<int:assessment_id>/upload',
           methods=['GET', 'POST'])
def upload_questions_to_assessment(assessment_id):

    guard = login_required('recruiter')
    if guard:
        return guard

    assessment = get_assessment(assessment_id)

    success = None

    if request.method == 'POST':

        file = request.files['file']

        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)

        else:
            df = pd.read_excel(file)

        from database import add_question

        for _, row in df.iterrows():

            add_question(
                assessment_id,
                row['question_text'],
                row['option_a'],
                row['option_b'],
                row['option_c'],
                row['option_d'],
                row['correct_option'],
                row['category'],
                row['difficulty']
            )

        success = f"{len(df)} questions imported successfully!"

    return render_template(
        'upload_assessment_questions.html',
        assessment=assessment,
        success=success
    )        

@app.route('/recruiter/analytics')
def recruiter_analytics():
    guard = login_required('recruiter')
    if guard:
        return guard

    return render_template(
        'analytics.html',
        name=session['name']
    )               

@app.route('/recruiter/question-bank/upload',
           methods=['GET', 'POST'])
def upload_question_bank():

    guard = login_required('recruiter')
    if guard:
        return guard

    success = None

    if request.method == 'POST':

        file = request.files['file']

        if file.filename.endswith('.csv'):

            df = pd.read_csv(file)

        else:

            df = pd.read_excel(file)

        from database import bulk_add_questions_to_bank

        bulk_add_questions_to_bank(df)

        success = f"{len(df)} questions imported successfully!"

    return render_template(
        'upload_question_bank.html',
        success=success
    )

import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)



