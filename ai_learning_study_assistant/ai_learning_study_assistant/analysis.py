"""
analysis.py
-----------
Reads data/quiz_results.csv and works out how students are doing.

  * Pandas  -> loading, grouping and averaging the table
  * NumPy   -> mean / max / min / differences on arrays of scores
  * Matplotlib + Seaborn -> the four charts saved in static/images/charts/

Every function copes with an empty table (no quiz attempts yet).
"""

import os
import textwrap

import matplotlib
matplotlib.use("Agg")                 # draw charts to files (no pop-up window)
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
import seaborn as sns

from quiz_logic import BASE_DIR, RESULTS_FILE, RESULT_COLUMNS

CHART_DIR = os.path.join(BASE_DIR, "static", "images", "charts")
CHART_FILES = {
    "course": "course_average.png",
    "topic": "topic_performance.png",
    "student": "student_comparison.png",
    "progress": "score_progress.png",
}

# Theme colours (same as the website)
CREAM, WHITE = "#FFFDF5", "#FFFFFF"
BLUE, DARK_BLUE, LIGHT_BLUE = "#2563EB", "#17345C", "#EAF2FF"
LINE_COLOURS = [BLUE, DARK_BLUE, "#D97706", "#059669", "#7C3AED", "#DC2626", "#0891B2", "#64748B"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_results():
    """Load quiz_results.csv into a clean DataFrame, oldest attempt first.

    Missing / empty file -> an empty DataFrame. Rows with unreadable numbers
    are dropped so one bad row cannot break the analysis.
    """
    try:
        table = pd.read_csv(RESULTS_FILE, dtype={"student_id": str})
    except (FileNotFoundError, pd.errors.EmptyDataError):
        table = pd.DataFrame(columns=RESULT_COLUMNS)

    for column in RESULT_COLUMNS:                      # make sure every column exists
        if column not in table.columns:
            table[column] = np.nan

    table["student_id"] = table["student_id"].astype(str).str.strip().str.upper()
    for column in ["score", "total_questions", "percentage"]:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    table["quiz_date"] = pd.to_datetime(table["quiz_date"], errors="coerce")

    table = table.dropna(subset=["score", "total_questions", "percentage"])
    table = table.sort_values("quiz_date", kind="stable").reset_index(drop=True)
    return table


def level_for(percentages):
    """Turn percentages into a level label (works on a NumPy array)."""
    values = np.asarray(percentages, dtype=float)
    return np.select([values >= 75, values >= 50],
                     ["Strong", "Developing"], default="Needs practice")


# ---------------------------------------------------------------------------
# Numbers and tables
# ---------------------------------------------------------------------------
def _describe_attempt(row):
    """Short dictionary describing one attempt (used for highest / lowest)."""
    return {
        "student_name": row["student_name"],
        "course_name": row["course_name"],
        "topic": row["topic"],
        "score": int(row["score"]),
        "total": int(row["total_questions"]),
        "percentage": float(row["percentage"]),
    }


def overall_summary(results):
    """Total attempts, average score / percentage, highest and lowest attempt."""
    if results.empty:
        return {"attempts": 0, "average_score": None, "average_percentage": None,
                "highest": None, "lowest": None}

    percentages = results["percentage"].to_numpy()
    scores = results["score"].to_numpy()
    best_row = results.iloc[int(np.argmax(percentages))]
    worst_row = results.iloc[int(np.argmin(percentages))]

    return {
        "attempts": int(len(results)),
        "average_score": round(float(np.mean(scores)), 2),
        "average_percentage": round(float(np.mean(percentages)), 1),
        "highest": _describe_attempt(best_row),
        "lowest": _describe_attempt(worst_row),
    }


def student_performance(results):
    """One row per student: attempts, average, best and lowest percentage."""
    columns = ["student_id", "student_name", "attempts", "average_percentage",
               "best_percentage", "lowest_percentage", "level"]
    if results.empty:
        return pd.DataFrame(columns=columns)

    table = results.groupby("student_id").agg(
        student_name=("student_name", "last"),
        attempts=("percentage", "count"),
        average_percentage=("percentage", "mean"),
        best_percentage=("percentage", "max"),
        lowest_percentage=("percentage", "min"),
    ).reset_index()
    table["level"] = level_for(table["average_percentage"])
    table = table.round(1).sort_values("average_percentage", ascending=False)
    return table[columns].reset_index(drop=True)


def course_performance(results):
    """One row per course: attempts, average score and average percentage."""
    columns = ["course_name", "attempts", "average_score", "average_percentage"]
    if results.empty:
        return pd.DataFrame(columns=columns)

    table = results.groupby("course_name").agg(
        attempts=("percentage", "count"),
        average_score=("score", "mean"),
        average_percentage=("percentage", "mean"),
    ).reset_index().round(1)
    return table[columns]


def topic_performance(results):
    """One row per course + topic: attempts and average percentage."""
    columns = ["course_name", "topic", "attempts", "average_percentage", "level"]
    if results.empty:
        return pd.DataFrame(columns=columns)

    table = results.groupby(["course_name", "topic"]).agg(
        attempts=("percentage", "count"),
        average_percentage=("percentage", "mean"),
    ).reset_index().round(1)
    table["level"] = level_for(table["average_percentage"])
    return table[columns]


def score_changes(results):
    """Compare first and latest attempts of the SAME student on the SAME topic.

    Only student + course + topic groups with at least 2 attempts can be
    compared, so those are the only ones listed.
    """
    columns = ["student_name", "course_name", "topic", "attempts",
               "first_percentage", "latest_percentage", "change", "trend"]
    rows = []
    if not results.empty:
        for (_, course, topic), group in results.groupby(["student_id", "course_name", "topic"]):
            if len(group) < 2:
                continue
            percentages = group["percentage"].to_numpy()      # already oldest -> newest
            change = float(np.sum(np.diff(percentages)))      # same as last - first
            rows.append({
                "student_name": group["student_name"].iloc[-1],
                "course_name": course,
                "topic": topic,
                "attempts": int(len(percentages)),
                "first_percentage": round(float(percentages[0]), 1),
                "latest_percentage": round(float(percentages[-1]), 1),
                "change": round(change, 1),
                "trend": "Improved" if change > 0 else ("Dropped" if change < 0 else "No change"),
            })
    return pd.DataFrame(rows, columns=columns)


def get_student_results(results, student_id):
    """All attempts of one student, newest first."""
    mine = results[results["student_id"] == student_id]
    return mine.sort_values("quiz_date", ascending=False, kind="stable").reset_index(drop=True)


def student_summary(student_results):
    """Quick numbers for a single student's attempts."""
    if student_results.empty:
        return {"attempts": 0, "average_percentage": None, "best_percentage": None,
                "lowest_percentage": None}
    pct = student_results["percentage"].to_numpy()
    return {
        "attempts": int(len(pct)),
        "average_percentage": round(float(np.mean(pct)), 1),
        "best_percentage": round(float(np.max(pct)), 1),
        "lowest_percentage": round(float(np.min(pct)), 1),
    }


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def _new_chart(width=8, height=4.6):
    """Create a figure that matches the website theme."""
    sns.set_theme(style="whitegrid", rc={
        "axes.facecolor": CREAM, "figure.facecolor": WHITE,
        "axes.edgecolor": "#C9D6EC", "grid.color": "#DDE7F7",
        "text.color": DARK_BLUE, "axes.labelcolor": DARK_BLUE,
        "xtick.color": DARK_BLUE, "ytick.color": DARK_BLUE,
    })
    fig, ax = plt.subplots(figsize=(width, height))
    return fig, ax


def _wrap(text, width=18):
    return textwrap.fill(str(text), width=width)


def _save(fig, key):
    """Save the figure in static/images/charts/ and free its memory."""
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, CHART_FILES[key]), dpi=110)
    plt.close(fig)
    return CHART_FILES[key]


def _add_pass_lines(ax, horizontal=True):
    """Draw the 50% and 75% guide lines used by the study rules."""
    for value, label in [(50, "50%"), (75, "75%")]:
        if horizontal:
            ax.axhline(value, color=DARK_BLUE, linestyle="--", linewidth=0.8, alpha=0.5)
            ax.text(ax.get_xlim()[1], value, f" {label}", va="center", fontsize=8, color=DARK_BLUE)
        else:
            ax.axvline(value, color=DARK_BLUE, linestyle="--", linewidth=0.8, alpha=0.5)
            ax.text(value, ax.get_ylim()[1], label, ha="center", va="bottom", fontsize=8, color=DARK_BLUE)


def chart_course_average(results):
    """Bar chart: average percentage for each course."""
    data = course_performance(results)
    fig, ax = _new_chart()
    data["label"] = data["course_name"].apply(_wrap)
    sns.barplot(data=data, x="label", y="average_percentage", color=BLUE, ax=ax)
    ax.bar_label(ax.containers[0], fmt="%.1f%%", padding=3, color=DARK_BLUE)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Course")
    ax.set_ylabel("Average percentage")
    ax.set_title("Course-wise average score", color=DARK_BLUE, fontweight="bold")
    return _save(fig, "course")


def chart_topic_performance(results):
    """Horizontal bar chart: average percentage for each topic."""
    data = topic_performance(results).sort_values("average_percentage")
    height = max(3.6, 0.55 * len(data) + 1.6)
    fig, ax = _new_chart(height=height)
    data["label"] = (data["course_name"] + ": " + data["topic"]).apply(lambda t: _wrap(t, 34))
    sns.barplot(data=data, x="average_percentage", y="label", color=BLUE, ax=ax)
    ax.bar_label(ax.containers[0], fmt="%.1f%%", padding=3, color=DARK_BLUE)
    ax.set_xlim(0, 110)
    _add_pass_lines(ax, horizontal=False)
    ax.set_xlabel("Average percentage")
    ax.set_ylabel("")
    ax.set_title("Topic-wise performance", color=DARK_BLUE, fontweight="bold", pad=18)
    return _save(fig, "topic")


def chart_student_comparison(results):
    """Bar chart: every student's average percentage side by side."""
    data = student_performance(results)
    fig, ax = _new_chart()
    data["label"] = (data["student_name"] + " (" + data["student_id"] + ")").apply(_wrap)
    sns.barplot(data=data, x="label", y="average_percentage", color=DARK_BLUE, ax=ax)
    ax.bar_label(ax.containers[0], fmt="%.1f%%", padding=3, color=DARK_BLUE)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Student")
    ax.set_ylabel("Average percentage")
    ax.set_title("Student score comparison", color=DARK_BLUE, fontweight="bold")
    return _save(fig, "student")


def chart_score_progress(results):
    """Line chart: percentage on attempt 1, 2, 3 ... for each student + topic."""
    data = results.copy()
    group_keys = ["student_id", "course_name", "topic"]
    data["attempt"] = data.groupby(group_keys).cumcount() + 1
    data["label"] = data["student_name"] + " - " + data["topic"]

    # Keep the chart readable: show the 8 combinations with the most attempts.
    top_labels = data.groupby("label")["attempt"].max().sort_values(ascending=False).head(8).index

    fig, ax = _new_chart(width=10)          # wider, because the legend sits beside the chart
    for number, label in enumerate(top_labels):
        part = data[data["label"] == label]
        sns.lineplot(data=part, x="attempt", y="percentage", marker="o", markersize=7,
                     color=LINE_COLOURS[number % len(LINE_COLOURS)], label=label, ax=ax)
    ax.set_ylim(0, 105)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Attempt number (same student, same topic)")
    ax.set_ylabel("Percentage")
    ax.set_title("Score progress across attempts", color=DARK_BLUE, fontweight="bold")
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    return _save(fig, "progress")


def generate_charts(results):
    """Create all four charts from the CSV data.

    Returns a dictionary {"course": "course_average.png", ...}.
    With no data, old chart files are removed and an empty dictionary is returned.
    """
    os.makedirs(CHART_DIR, exist_ok=True)

    if results.empty:
        for filename in CHART_FILES.values():
            old_file = os.path.join(CHART_DIR, filename)
            if os.path.exists(old_file):
                os.remove(old_file)
        return {}

    return {
        "course": chart_course_average(results),
        "topic": chart_topic_performance(results),
        "student": chart_student_comparison(results),
        "progress": chart_score_progress(results),
    }
