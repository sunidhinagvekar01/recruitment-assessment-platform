import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import sys
import os

# So Python can find analytics.py one folder up
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

DB = os.path.join(os.path.dirname(__file__), '..', 'assessment.db')

st.set_page_config(
    page_title="Recruiter Analytics",
    page_icon="📊",
    layout="wide"
)

# ── Custom dark theme styling ─────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background:#0f172a; }
  [data-testid="stSidebar"]          { background:#1e293b; border-right:1px solid #334155; }
  .block-container                   { padding-top:2rem; }
  h1,h2,h3,p,label                   { color:#e2e8f0 !important; }
  .metric-label                      { color:#64748b !important; }
  .stDataFrame                       { border:1px solid #334155; border-radius:10px; }
</style>
""", unsafe_allow_html=True)

# ── Load helpers ──────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def load_assessments():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT a.id, a.title, u.name as recruiter FROM assessments a JOIN users u ON a.created_by=u.id WHERE a.is_active=1",
        conn
    )
    conn.close()
    return df

def load_scores(assessment_id):
    conn = get_conn()
    df = pd.read_sql_query('''
        SELECT s.candidate_id, s.total_score, s.max_score, s.percentage,
               s.correct_count, s.wrong_count, s.skipped_count,
               s.avg_time_per_q, s.completed_at,
               u.name, u.email
        FROM scores s JOIN users u ON s.candidate_id=u.id
        WHERE s.assessment_id=?
        ORDER BY s.percentage DESC
    ''', conn, params=(assessment_id,))
    conn.close()
    return df

def load_responses(assessment_id):
    conn = get_conn()
    df = pd.read_sql_query('''
        SELECT r.candidate_id, r.is_correct, r.time_taken,
               q.category, q.difficulty, q.question_text,
               u.name as candidate_name
        FROM responses r
        JOIN questions q ON r.question_id=q.id
        JOIN users u ON r.candidate_id=u.id
        WHERE r.assessment_id=?
    ''', conn, params=(assessment_id,))
    conn.close()
    return df

# ── Sidebar ───────────────────────────────────────────────────────────
st.sidebar.title("📊 RecruitAssess")
st.sidebar.markdown("---")

assessments = load_assessments()

if assessments.empty:
    st.sidebar.warning("No assessments found.")
    st.title("No assessments yet.")
    st.info("Create an assessment from the recruiter web portal first.")
    st.stop()

selected_id = st.sidebar.selectbox(
    "Select Assessment",
    options=assessments['id'].tolist(),
    format_func=lambda x: assessments[assessments['id']==x]['title'].values[0]
)

selected_title = assessments[assessments['id']==selected_id]['title'].values[0]
st.sidebar.markdown("---")
st.sidebar.info(f"Viewing: **{selected_title}**")

# ── Load data ─────────────────────────────────────────────────────────
scores_df    = load_scores(selected_id)
responses_df = load_responses(selected_id)

# ── Page title ────────────────────────────────────────────────────────
st.title(f"📊 {selected_title}")
st.caption("Recruiter Analytics Dashboard")

if scores_df.empty:
    st.info("No candidates have completed this assessment yet.")
    st.stop()

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — KPI CARDS
# ═══════════════════════════════════════════════════════════════════
st.subheader("Overview")
col1, col2, col3, col4, col5 = st.columns(5)

pct_vals  = scores_df['percentage'].values
pass_rate = round((pct_vals >= 60).sum() / len(pct_vals) * 100, 1)

col1.metric("Total Candidates",  len(scores_df))
col2.metric("Average Score",     f"{round(float(np.mean(pct_vals)), 1)}%")
col3.metric("Median Score",      f"{round(float(np.median(pct_vals)), 1)}%")
col4.metric("Pass Rate (≥60%)",  f"{pass_rate}%")
col5.metric("Top Score",         f"{round(float(np.max(pct_vals)), 1)}%")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — SCORE DISTRIBUTION + TOP CANDIDATES
# ═══════════════════════════════════════════════════════════════════
st.subheader("Score Analysis")
col_left, col_right = st.columns(2)

with col_left:
    fig_hist = px.histogram(
        scores_df, x='percentage', nbins=10,
        title='Score Distribution',
        labels={'percentage': 'Score (%)'},
        color_discrete_sequence=['#6366f1']
    )
    fig_hist.update_layout(
        plot_bgcolor='#1e293b', paper_bgcolor='#1e293b',
        font_color='#94a3b8', bargap=0.08,
        title_font_color='#e2e8f0'
    )
    fig_hist.add_vline(x=float(np.mean(pct_vals)), line_dash='dash',
                       line_color='#f59e0b',
                       annotation_text=f'Avg {round(float(np.mean(pct_vals)),1)}%',
                       annotation_font_color='#f59e0b')
    st.plotly_chart(fig_hist, use_container_width=True)

with col_right:
    fig_bar = px.bar(
        scores_df.head(10), x='name', y='percentage',
        title='Top 10 Candidates',
        labels={'percentage': 'Score (%)', 'name': 'Candidate'},
        color='percentage',
        color_continuous_scale='Viridis'
    )
    fig_bar.update_layout(
        plot_bgcolor='#1e293b', paper_bgcolor='#1e293b',
        font_color='#94a3b8', showlegend=False,
        title_font_color='#e2e8f0'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════
# SECTION 3 — CATEGORY ANALYTICS (only if responses exist)
# ═══════════════════════════════════════════════════════════════════
if not responses_df.empty:
    st.subheader("Category & Difficulty Analytics")
    col_cat, col_diff = st.columns(2)

    # Category avg across all candidates
    cat_agg = responses_df.groupby('category')['is_correct'].apply(
        lambda x: round((x == 1).sum() / len(x) * 100, 1)
    ).reset_index()
    cat_agg.columns = ['Category', 'Avg Correct %']

    with col_cat:
        fig_cat = px.bar(
            cat_agg, x='Category', y='Avg Correct %',
            title='Avg Score per Category (All Candidates)',
            color='Avg Correct %',
            color_continuous_scale='RdYlGn',
            range_color=[0, 100]
        )
        fig_cat.update_layout(
            plot_bgcolor='#1e293b', paper_bgcolor='#1e293b',
            font_color='#94a3b8', showlegend=False,
            title_font_color='#e2e8f0'
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    # Difficulty breakdown
    diff_agg = responses_df.groupby('difficulty')['is_correct'].apply(
        lambda x: round((x == 1).sum() / len(x) * 100, 1)
    ).reset_index()
    diff_agg.columns = ['Difficulty', 'Avg Correct %']

    with col_diff:
        fig_diff = px.pie(
            diff_agg, names='Difficulty', values='Avg Correct %',
            title='Score Share by Difficulty',
            color_discrete_sequence=['#34d399', '#fbbf24', '#f87171']
        )
        fig_diff.update_layout(
            plot_bgcolor='#1e293b', paper_bgcolor='#1e293b',
            font_color='#94a3b8', title_font_color='#e2e8f0'
        )
        st.plotly_chart(fig_diff, use_container_width=True)

    # Hardest questions
    q_difficulty = responses_df.groupby('question_text')['is_correct'].apply(
        lambda x: round((x == 1).sum() / len(x) * 100, 1)
    ).reset_index()
    q_difficulty.columns = ['Question', 'Correct %']
    q_difficulty = q_difficulty.sort_values('Correct %')

    st.markdown("**5 Hardest Questions (lowest correct rate)**")
    st.dataframe(
        q_difficulty.head(5).reset_index(drop=True),
        use_container_width=True
    )

    st.markdown("---")

# ═══════════════════════════════════════════════════════════════════
# SECTION 4 — TIMING ANALYSIS
# ═══════════════════════════════════════════════════════════════════
if not responses_df.empty and 'time_taken' in responses_df.columns:
    st.subheader("Timing Analysis")
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        fig_time = px.box(
            responses_df[responses_df['time_taken'].notna()],
            x='category', y='time_taken',
            title='Time Taken per Category (seconds)',
            color='category',
            labels={'time_taken': 'Seconds', 'category': 'Category'}
        )
        fig_time.update_layout(
            plot_bgcolor='#1e293b', paper_bgcolor='#1e293b',
            font_color='#94a3b8', showlegend=False,
            title_font_color='#e2e8f0'
        )
        st.plotly_chart(fig_time, use_container_width=True)

    with col_t2:
        fig_scatter = px.scatter(
            scores_df, x='avg_time_per_q', y='percentage',
            title='Avg Time vs Score (each dot = one candidate)',
            labels={'avg_time_per_q': 'Avg Time per Question (s)', 'percentage': 'Score (%)'},
            hover_data=['name'],
            color='percentage',
            color_continuous_scale='Viridis'
        )
        fig_scatter.update_layout(
            plot_bgcolor='#1e293b', paper_bgcolor='#1e293b',
            font_color='#94a3b8', title_font_color='#e2e8f0'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")

# ═══════════════════════════════════════════════════════════════════
# SECTION 5 — CANDIDATE COMPARISON TABLE
# ═══════════════════════════════════════════════════════════════════
st.subheader("All Candidates")

filter_col, sort_col = st.columns([2, 1])
with filter_col:
    min_score = st.slider("Filter: minimum score (%)", 0, 100, 0)
with sort_col:
    sort_by = st.selectbox("Sort by", ["Score (High→Low)", "Score (Low→High)", "Name"])

filtered = scores_df[scores_df['percentage'] >= min_score].copy()
if sort_by == "Score (High→Low)":
    filtered = filtered.sort_values('percentage', ascending=False)
elif sort_by == "Score (Low→High)":
    filtered = filtered.sort_values('percentage', ascending=True)
else:
    filtered = filtered.sort_values('name')

display = filtered[['name','email','percentage','correct_count',
                     'wrong_count','skipped_count','avg_time_per_q']].copy()
display.columns = ['Name','Email','Score %','Correct','Wrong','Skipped','Avg Time (s)']
display = display.reset_index(drop=True)

st.dataframe(
    display.style.background_gradient(subset=['Score %'], cmap='RdYlGn'),
    use_container_width=True
)

# Download button
csv = display.to_csv(index=False)
st.download_button(
    label="⬇️ Download Report as CSV",
    data=csv,
    file_name=f"{selected_title}_candidates.csv",
    mime="text/csv"
)
