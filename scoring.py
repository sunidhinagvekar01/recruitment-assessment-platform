from database import (get_questions, get_candidate_responses,
                       save_score, get_score)

def calculate_and_save_score(candidate_id, assessment_id):
    """
    Reads all saved responses for a candidate,
    calculates score using negative marking,
    and saves the final result to the scores table.
    """
    responses = get_candidate_responses(candidate_id, assessment_id)

    if not responses:
        return None

    correct = sum(1 for r in responses if r['is_correct'] == 1)
    wrong   = sum(1 for r in responses if r['is_correct'] == 0)
    skipped = sum(1 for r in responses if r['is_correct'] is None)

    total_questions = len(responses)
    score     = (correct * 4) - (wrong * 1)   # +4 correct, -1 wrong
    max_score = total_questions * 4
    percentage = round((correct / total_questions) * 100, 2) if total_questions else 0

    times  = [r['time_taken'] for r in responses if r['time_taken'] is not None]
    avg_time = round(sum(times) / len(times), 1) if times else 0

    save_score(candidate_id, assessment_id, score, max_score,
               percentage, correct, wrong, skipped, avg_time)

    return {
        'score': score, 'max_score': max_score,
        'percentage': percentage, 'correct': correct,
        'wrong': wrong, 'skipped': skipped, 'avg_time': avg_time
    }


def get_rank_label(percentage):
    """Returns a text badge based on score percentage."""
    if percentage >= 85:
        return ('Expert',        '🏆', '#fbbf24')
    elif percentage >= 70:
        return ('Advanced',      '🥇', '#818cf8')
    elif percentage >= 55:
        return ('Intermediate',  '🥈', '#34d399')
    elif percentage >= 40:
        return ('Beginner',      '🥉', '#94a3b8')
    else:
        return ('Needs Practice','📚', '#f87171')
