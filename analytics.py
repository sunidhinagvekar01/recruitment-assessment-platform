import sqlite3
import pandas as pd
import numpy as np

DB = 'assessment.db'

def get_candidate_analytics(candidate_id, assessment_id):
    """
    Returns full analytics for ONE candidate on ONE assessment.
    Used by: candidate results page + recruiter individual view.
    """
    conn = sqlite3.connect(DB)

    df = pd.read_sql_query('''
        SELECT r.is_correct, r.time_taken, r.selected_option,
               q.category, q.difficulty, q.correct_option
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        WHERE r.candidate_id = ? AND r.assessment_id = ?
    ''', conn, params=(candidate_id, assessment_id))

    conn.close()

    if df.empty:
        return {}

    # ── Category-wise performance ─────────────────────────────────────
    cat = df.groupby('category')['is_correct'].agg(
        correct=lambda x: (x == 1).sum(),
        total='count'
    ).reset_index()
    cat['percentage'] = (cat['correct'] / cat['total'] * 100).round(1)
    cat['wrong']      = cat['total'] - cat['correct']

    # ── Difficulty-wise performance ───────────────────────────────────
    diff = df.groupby('difficulty')['is_correct'].agg(
        correct=lambda x: (x == 1).sum(),
        total='count'
    ).reset_index()
    diff['percentage'] = (diff['correct'] / diff['total'] * 100).round(1)

    # ── Timing stats (NumPy) ──────────────────────────────────────────
    times = df['time_taken'].dropna().astype(float).values
    if len(times) > 0:
        timing = {
            'avg':     round(float(np.mean(times)), 1),
            'median':  round(float(np.median(times)), 1),
            'std':     round(float(np.std(times)), 1),
            'fastest': int(np.min(times)),
            'slowest': int(np.max(times))
        }
    else:
        timing = {'avg': 0, 'median': 0, 'std': 0, 'fastest': 0, 'slowest': 0}

    # ── Strengths / Weaknesses ────────────────────────────────────────
    strengths  = cat[cat['percentage'] >= 60]['category'].tolist()
    weaknesses = cat[cat['percentage'] <  60]['category'].tolist()

    return {
        'category_performance':    cat.to_dict('records'),
        'difficulty_performance':  diff.to_dict('records'),
        'timing':                  timing,
        'strengths':               strengths,
        'weaknesses':              weaknesses,
        'total_questions':         len(df)
    }


def get_recruiter_analytics(assessment_id):
    """
    Returns comparative analytics across ALL candidates for one assessment.
    Used by: recruiter Streamlit dashboard.
    """
    conn = sqlite3.connect(DB)

    scores_df = pd.read_sql_query('''
        SELECT s.*, u.name, u.email
        FROM scores s
        JOIN users u ON s.candidate_id = u.id
        WHERE s.assessment_id = ?
        ORDER BY s.percentage DESC
    ''', conn, params=(assessment_id,))

    responses_df = pd.read_sql_query('''
        SELECT r.candidate_id, r.is_correct, r.time_taken,
               q.category, q.difficulty
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        WHERE r.assessment_id = ?
    ''', conn, params=(assessment_id,))

    conn.close()

    if scores_df.empty:
        return {}

    # ── Score distribution ────────────────────────────────────────────
    pct = scores_df['percentage'].values

    # ── Category avg across all candidates ───────────────────────────
    if not responses_df.empty:
        cat_avg = responses_df.groupby('category')['is_correct'].apply(
            lambda x: round((x == 1).sum() / len(x) * 100, 1)
        ).reset_index()
        cat_avg.columns = ['category', 'avg_correct_pct']
        cat_avg_list = cat_avg.to_dict('records')

        # hardest questions: categories with lowest avg
        hardest = cat_avg.nsmallest(2, 'avg_correct_pct')['category'].tolist()
        easiest = cat_avg.nlargest(2, 'avg_correct_pct')['category'].tolist()
    else:
        cat_avg_list = []
        hardest = []
        easiest = []

    return {
        'total_candidates':    len(scores_df),
        'avg_score':           round(float(np.mean(pct)), 1),
        'median_score':        round(float(np.median(pct)), 1),
        'score_std':           round(float(np.std(pct)), 1),
        'pass_rate':           round(float((pct >= 60).sum() / len(pct) * 100), 1),
        'top_candidates':      scores_df.head(10).to_dict('records'),
        'all_scores':          scores_df.to_dict('records'),
        'score_distribution':  pct.tolist(),
        'category_avg':        cat_avg_list,
        'hardest_categories':  hardest,
        'easiest_categories':  easiest
    }


def get_percentile_rank(candidate_id, assessment_id):
    """Returns what % of other candidates this candidate beat."""
    conn = sqlite3.connect(DB)
    all_pct = pd.read_sql_query(
        "SELECT percentage FROM scores WHERE assessment_id=?",
        conn, params=(assessment_id,)
    )['percentage'].values

    my_pct = pd.read_sql_query(
        "SELECT percentage FROM scores WHERE candidate_id=? AND assessment_id=?",
        conn, params=(candidate_id, assessment_id)
    )['percentage'].values

    conn.close()

    if len(my_pct) == 0 or len(all_pct) == 0:
        return 0

    return round(float(np.sum(all_pct < my_pct[0]) / len(all_pct) * 100), 1)
