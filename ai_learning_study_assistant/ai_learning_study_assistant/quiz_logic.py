"""
quiz_logic.py
-------------
Everything about courses, notes and quizzes lives here:
  * reading the CSV files with Pandas
  * checking what the student typed
  * marking the quiz
  * saving the result as a new row in data/quiz_results.csv
"""

import csv
import os
import re
from datetime import datetime

import pandas as pd

# ---------------------------------------------------------------------------
# File locations (relative to this project folder, so it works on any computer)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

COURSES_FILE = os.path.join(DATA_DIR, "courses.csv")
QUESTIONS_FILE = os.path.join(DATA_DIR, "questions.csv")
RESULTS_FILE = os.path.join(DATA_DIR, "quiz_results.csv")
SAMPLE_FILE = os.path.join(DATA_DIR, "sample_students.csv")

RESULT_COLUMNS = ["student_id", "student_name", "course_name", "topic",
                  "quiz_date", "score", "total_questions", "percentage"]
COURSE_COLUMNS = ["course_id", "course_name", "description", "topics"]
QUESTION_COLUMNS = ["question_id", "course_id", "topic", "question",
                    "option_a", "option_b", "option_c", "option_d", "correct_answer"]

LETTERS = ["A", "B", "C", "D"]


# ---------------------------------------------------------------------------
# Reading CSV files
# ---------------------------------------------------------------------------
def read_csv_safe(path, columns):
    """Read a CSV file with Pandas.

    If the file is missing or completely empty, return an empty table with the
    expected columns instead of crashing.
    """
    try:
        table = pd.read_csv(path, dtype=str)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        table = pd.DataFrame(columns=columns)
    return table.fillna("")


def load_courses():
    """Return a list of courses. Each course is a dictionary.

    The 'topics' column (e.g. "A;B;C") is turned into a Python list.
    """
    table = read_csv_safe(COURSES_FILE, COURSE_COLUMNS)
    courses = []
    for row in table.to_dict("records"):
        topics = [t.strip() for t in row.get("topics", "").split(";") if t.strip()]
        courses.append({
            "course_id": row.get("course_id", "").strip(),
            "course_name": row.get("course_name", "").strip(),
            "description": row.get("description", "").strip(),
            "topics": topics,
        })
    return courses


def find_course(courses, course_id):
    """Return the course with this id, or None if there is no such course."""
    course_id = str(course_id or "").strip()
    for course in courses:
        if course["course_id"] == course_id:
            return course
    return None


def load_questions(course_id, topic):
    """Load the MCQs for one course and topic using Pandas.

    Rows with a missing question or an invalid correct answer are skipped.
    """
    table = read_csv_safe(QUESTIONS_FILE, QUESTION_COLUMNS)
    if table.empty:
        return []

    chosen = table[(table["course_id"].str.strip() == str(course_id).strip()) &
                   (table["topic"].str.strip() == str(topic).strip())]

    questions = []
    for row in chosen.to_dict("records"):
        correct = row["correct_answer"].strip().upper()
        if not row["question"].strip() or correct not in LETTERS:
            continue                                   # skip broken rows
        questions.append({
            "question_id": row["question_id"].strip(),
            "question": row["question"].strip(),
            "options": [("A", row["option_a"]), ("B", row["option_b"]),
                        ("C", row["option_c"]), ("D", row["option_d"])],
            "correct": correct,
        })
    return questions


# ---------------------------------------------------------------------------
# Checking the student's details
# ---------------------------------------------------------------------------
def clean_student_id(raw_id):
    """Return a tidy student ID (upper case) or '' if it is not valid.

    Allowed: letters, digits, '-' and '_' (1 to 15 characters).
    """
    student_id = (raw_id or "").strip().upper()
    if re.fullmatch(r"[A-Z0-9_-]{1,15}", student_id):
        return student_id
    return ""


def clean_student_name(raw_name):
    """Return a tidy name or '' if it is not valid.

    Allowed: letters, spaces, dots, apostrophes and hyphens (2 to 50 characters).
    """
    name = " ".join((raw_name or "").split())          # remove extra spaces
    if 2 <= len(name) <= 50 and re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", name):
        return name
    return ""


def validate_student(raw_id, raw_name):
    """Check ID and name. Returns (student_id, student_name, list_of_errors)."""
    errors = []
    student_id = clean_student_id(raw_id)
    student_name = clean_student_name(raw_name)

    if not student_id:
        errors.append("Enter a student ID using letters, numbers, '-' or '_' (up to 15 characters).")
    if not student_name:
        errors.append("Enter a valid name using letters and spaces (2 to 50 characters).")

    # The same ID must not be used by a different person.
    if student_id and student_name:
        saved_name = name_for_id(student_id)
        if saved_name and saved_name.lower() != student_name.lower():
            errors.append(f"The ID {student_id} has already been used with the name "
                          f"'{saved_name}'. Use that name or choose a different ID.")
    return student_id, student_name, errors


def name_for_id(student_id):
    """Look in quiz_results.csv for a name already saved with this ID."""
    table = read_csv_safe(RESULTS_FILE, RESULT_COLUMNS)
    if table.empty:
        return ""
    matches = table[table["student_id"].str.strip().str.upper() == student_id]
    if matches.empty:
        return ""
    return matches["student_name"].iloc[0].strip()


# ---------------------------------------------------------------------------
# Marking the quiz
# ---------------------------------------------------------------------------
def score_quiz(questions, answers):
    """Mark the quiz. Called only AFTER the student submits.

    questions : list from load_questions()
    answers   : dictionary like {"5": "B", "6": "D"}  (question_id -> letter)

    Returns a dictionary with score, total, percentage and a review list.
    """
    score = 0
    review = []
    for q in questions:
        chosen = answers.get(q["question_id"], "")
        is_correct = (chosen == q["correct"])
        if is_correct:
            score += 1
        option_text = dict(q["options"])
        review.append({
            "question": q["question"],
            "chosen": chosen,
            "chosen_text": option_text.get(chosen, ""),
            "correct": q["correct"],
            "correct_text": option_text.get(q["correct"], ""),
            "is_correct": is_correct,
        })

    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0.0
    return {"score": score, "total": total, "percentage": percentage, "review": review}


# ---------------------------------------------------------------------------
# Saving the result
# ---------------------------------------------------------------------------
def save_result(student_id, student_name, course_name, topic, score, total, percentage):
    """Append ONE new row to data/quiz_results.csv.

    Creates the file (with its header) if it is missing or empty. Raises
    OSError if the file cannot be written (for example, it is locked because
    it is open in another program).
    """
    is_new_file = (not os.path.exists(RESULTS_FILE)) or os.path.getsize(RESULTS_FILE) == 0

    # If the file was edited by hand and has no final line break, add one first
    # so that our new row does not get glued to the previous line.
    needs_line_break = False
    if not is_new_file:
        with open(RESULTS_FILE, "rb") as check:
            check.seek(-1, os.SEEK_END)
            needs_line_break = check.read(1) not in (b"\n", b"\r")

    with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as file:
        if needs_line_break:
            file.write("\n")
        writer = csv.writer(file, lineterminator="\n")
        if is_new_file:
            writer.writerow(RESULT_COLUMNS)
        writer.writerow([
            student_id,
            student_name,
            course_name,
            topic,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            score,
            total,
            percentage,
        ])


# ---------------------------------------------------------------------------
# Study notes
# ---------------------------------------------------------------------------
# Notes are organised course -> topic. Topic names must match courses.csv.
STUDY_NOTES = {
    "Python Programming": {
        "Variables and Data Types": {
            "points": [
                "A variable is a name that stores a value. Names may contain letters, digits and underscores, but cannot start with a digit or contain spaces or hyphens.",
                "Common types: int (whole numbers), float (decimal numbers), str (text) and bool (True or False).",
                "Use type(value) to find the type of a value.",
                "Arithmetic operators: + - * / // % and ** (power).",
            ],
            "example": "age = 18\nprice = 3.14\nname = \"Sara\"\nprint(type(price))   # <class 'float'>\nprint(2 ** 3)        # 8",
        },
        "Loops and Conditions": {
            "points": [
                "if, elif and else let a program choose between actions.",
                "for loops repeat a block for every item in a sequence; range(3) gives 0, 1, 2.",
                "while loops repeat as long as a condition is True.",
                "break stops a loop immediately; continue skips to the next round.",
                "The % operator gives the remainder of a division (10 % 3 is 1).",
            ],
            "example": "for i in range(3):\n    if i == 1:\n        continue\n    print(i)",
        },
        "Functions": {
            "points": [
                "A function is a reusable block of code created with the def keyword.",
                "Names inside the brackets are parameters; the values you pass in are arguments.",
                "return sends a value back to the caller. Without return, a function gives back None.",
                "Give functions clear names and add a short comment or docstring.",
            ],
            "example": "def add(a, b):\n    return a + b\n\nprint(add(2, 3))   # 5",
        },
    },
    "Data Analysis with Python": {
        "NumPy Basics": {
            "points": [
                "NumPy stores numbers in fast arrays: np.array([1, 2, 3]).",
                "array.shape tells you the rows and columns, e.g. (2, 3) means 2 rows and 3 columns.",
                "np.zeros(), np.ones() and np.arange() create arrays quickly.",
                "np.mean(), np.max(), np.min() and np.sum() summarise an array.",
            ],
            "example": "import numpy as np\nscores = np.array([40, 60, 80])\nprint(np.mean(scores))   # 60.0\nprint(scores.shape)      # (3,)",
        },
        "Pandas Basics": {
            "points": [
                "A DataFrame is a table of rows and columns.",
                "pd.read_csv('file.csv') loads a CSV file; df.head() shows the first 5 rows.",
                "df['score'] selects a column and df['score'].mean() gives its average.",
                "df.groupby('course')['score'].mean() calculates an average for each group.",
            ],
            "example": "import pandas as pd\ndf = pd.read_csv('data/quiz_results.csv')\nprint(df.groupby('course_name')['percentage'].mean())",
        },
        "Data Visualization": {
            "points": [
                "Matplotlib draws charts: plt.plot() for lines and plt.bar() for bars.",
                "Seaborn is built on Matplotlib and makes good-looking statistical charts with less code.",
                "Use a line chart for change over time and a bar chart to compare categories.",
                "plt.savefig('chart.png') saves a chart as an image file.",
            ],
            "example": "import matplotlib.pyplot as plt\nplt.plot([1, 2, 3], [50, 65, 80])\nplt.savefig('progress.png')",
        },
    },
    "Web Basics": {
        "HTML Basics": {
            "points": [
                "HTML describes the structure of a web page using tags.",
                "<h1> is the largest heading, <p> is a paragraph, <a href=\"...\"> is a link and <img src=\"...\"> shows an image.",
                "<ul> makes a bulleted list and <ol> a numbered list; each item uses <li>.",
                "Every page needs <html>, <head> and <body>.",
            ],
            "example": "<h1>My Page</h1>\n<p>Hello!</p>\n<ul>\n  <li>First</li>\n  <li>Second</li>\n</ul>",
        },
        "CSS Basics": {
            "points": [
                "CSS controls how HTML looks: colours, spacing and layout.",
                "A class selector starts with a dot (.card); an id selector starts with # (#menu).",
                "color changes text colour; margin is space outside an element; padding is space inside it.",
                "display: flex arranges items in a flexible row or column.",
            ],
            "example": ".card {\n  color: #17345C;\n  margin: 16px;\n  display: flex;\n}",
        },
    },
}


def make_anchor(course_name, topic):
    """Turn a course and topic into a safe page anchor like 'python-programming-functions'."""
    text = f"{course_name} {topic}".lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def get_notes(courses):
    """Combine courses.csv with STUDY_NOTES into a list the notes page can loop over.

    Topics that have no written notes yet are still shown, with a short message.
    """
    notes = []
    for course in courses:
        course_notes = STUDY_NOTES.get(course["course_name"], {})
        topics = []
        for topic in course["topics"]:
            entry = course_notes.get(topic, {"points": [], "example": ""})
            topics.append({
                "topic": topic,
                "points": entry["points"],
                "example": entry["example"],
                "anchor": make_anchor(course["course_name"], topic),
            })
        notes.append({"course": course, "topics": topics})
    return notes
