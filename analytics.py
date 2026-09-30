import pandas as pd
import numpy as np
from database import get_conn, get_cursor

conn = get_conn()
cur = get_cursor(conn)

def get_candidate_analytics(candidate_id, assessment_id):
    """
    Returns full analytics for ONE candidate on ONE assessment.
    Used by: candidate results page + recruiter individual view.
    """
    conn = get_conn()
    cur = get_cursor(conn)


    cur.execute(
    '''
        SELECT r.is_correct, r.time_taken, r.selected_option,
               q.category, q.difficulty, q.correct_option
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        WHERE r.candidate_id = %s
          AND r.assessment_id = %s
        ''',
        (candidate_id, assessment_id)
    )

    rows = cur.fetchall()

    df = pd.DataFrame(rows)

    cur.close()
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


    # ── Strongest & Weakest Skill ─────────────────────────────

    if not cat.empty:
        strongest_skill = cat.sort_values(
        by="percentage",
        ascending=False
        ).iloc[0]["category"]

        weakest_skill = cat.sort_values(
        by="percentage",
        ascending=True
        ).iloc[0]["category"]
    else:
        strongest_skill = "N/A"
        weakest_skill = "N/A"

    # ── Performance Metrics ───────────────────────────────────────

    accuracy = round(
        float(cat['correct'].sum() / cat['total'].sum() * 100),
        1
    )

    performance_metrics = calculate_performance_metrics(
        accuracy,
        timing['avg'],
        timing['std']
    )

    # ── Performance Trend ─────────────────────────────

    performance_trend = []

    running_correct = 0

    for i, row in enumerate(df.itertuples(), start=1):

        if row.is_correct == 1:
            running_correct += 1

        running_score = round((running_correct / i) * 100, 1)

        performance_trend.append({
            "question": i,
            "score": running_score
        })

    # ── Hiring Recommendation ─────────────────────────────

    performance_index = performance_metrics["performance_index"]

    if performance_index >= 90:
        hiring_recommendation = "Highly Recommended"

    elif performance_index >= 75:
        hiring_recommendation = "Recommended"

    elif performance_index >= 60:
        hiring_recommendation = "Consider"

    else:
        hiring_recommendation = "Needs Improvement"

    return {
        'category_performance': cat.to_dict('records'),
        'difficulty_performance': diff.to_dict('records'),
        'timing': timing,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'strongest_skill': strongest_skill,
        'weakest_skill': weakest_skill,
        'hiring_recommendation': hiring_recommendation,
        'total_questions': len(df),
        'performance_metrics': performance_metrics,
        'performance_trend': performance_trend,
    }


def calculate_performance_metrics(accuracy, avg_time, std_dev):
    """
    Calculates the overall Performance Index.

    Formula:
    70% Accuracy
    15% Time Efficiency
    15% Consistency
    """


    # Convert average time (0–60 sec) into a score out of 100
    time_efficiency = max(
        0,
        ((60 - avg_time) / 60) * 100
    )

        # Speed Index
    if avg_time <= 10:
        speed_label = "Excellent"

    elif avg_time <= 20:
        speed_label = "Fast"

    elif avg_time <= 35:
        speed_label = "Moderate"

    elif avg_time <= 50:
        speed_label = "Slow"

    else:
        speed_label = "Very Slow"

    # Lower standard deviation = more consistent
    consistency = max(
        0,
        ((60 - std_dev) / 60) * 100
    )

    
    # Consistency Level

    if consistency >= 90:
        consistency_label = "Excellent"

    elif consistency >= 75:
        consistency_label = "High"

    elif consistency >= 60:
        consistency_label = "Moderate"

    elif consistency >= 40:
        consistency_label = "Low"

    else:
        consistency_label = "Very Low"


    performance_index = round(
        (accuracy * 0.70)
        + (time_efficiency * 0.15)
        + (consistency * 0.15),
        1
    )

    completion_rate = 100

    confidence_score = round(
    (accuracy * 0.60)
    + (consistency * 0.25)
    + (completion_rate * 0.15),
    1
)

    return {
    "performance_index": performance_index,
    "confidence_score": confidence_score,
    "time_efficiency": round(time_efficiency, 1),
    "consistency_score": round(consistency, 1),
    "consistency_level": consistency_label,
    "speed_index": speed_label
    }   

def get_recruiter_analytics(assessment_id):
    """
    Returns comparative analytics across ALL candidates for one assessment.
    Used by: recruiter Streamlit dashboard.
    """
    conn = get_conn()

    scores_df = pd.read_sql_query('''
        SELECT s.*, u.name, u.email
        FROM scores s
        JOIN users u ON s.candidate_id = u.id
        WHERE s.assessment_id = %s
        ORDER BY s.percentage DESC
    ''', conn, params=(assessment_id,))

    responses_df = pd.read_sql_query('''
        SELECT r.candidate_id, r.is_correct, r.time_taken,
               q.category, q.difficulty
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        WHERE r.assessment_id = %s
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
    conn = get_conn()
    all_pct = pd.read_sql_query(
        "SELECT percentage FROM scores WHERE assessment_id=%s",
        conn, params=(assessment_id,)
    )['percentage'].values

    my_pct = pd.read_sql_query(
        "SELECT percentage FROM scores WHERE candidate_id=%s AND assessment_id=%s",
        conn, params=(candidate_id, assessment_id)
    )['percentage'].values

    conn.close()

    if len(my_pct) == 0 or len(all_pct) == 0:
        return 0

    return round(float(np.sum(all_pct < my_pct[0]) / len(all_pct) * 100), 1)
