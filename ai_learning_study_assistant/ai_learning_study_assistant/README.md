# AI Learning & Study Assistant

A beginner-friendly Flask web app for **courses, study notes, MCQ quizzes, student performance analysis, CSV data and Python-based study support**.

**Team:** Shahid, Bilal and Owais Qayoom (each has an individual portfolio page).

> The study suggestions come from simple Python `if / elif / else` rules applied to quiz percentages.
> They are **rule-based**. The project does not use a trained AI or machine-learning model.

---

## 1. Technologies

Core Python, Flask, NumPy, Pandas, Matplotlib, Seaborn, HTML, CSS and CSV files.
There is **no JavaScript**, no database and no other library.

## 2. Installation

You need Python 3.9 or newer.

```bash
# 1. Go into the project folder
cd ai_learning_study_assistant

# 2. (Recommended) create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 3. Install the libraries
pip install -r requirements.txt
```

## 3. Run the project

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser. Press `Ctrl + C` in the terminal to stop the server.

## 4. How to use it

1. **Courses / Notes** – read about a course and its topics.
2. **Quiz** – enter your student ID and name, choose a course, choose a topic, answer all questions and press **Submit quiz**.
3. **Result** – see your score, total marks, percentage, feedback and the answers you missed.
4. **My Results** – enter your student ID to see all your saved quizzes.
5. **Performance** – statistics and four charts built from `data/quiz_results.csv`.
6. **Study Assistant** – enter your student ID to get suggestions for each topic you have attempted.
7. **Dataset** – all four CSV files shown as tables.

Student IDs accept letters, numbers, `-` and `_` (up to 15 characters) and are stored in capitals. An ID that is already saved with one name cannot be reused with a different name.

## 5. How to verify that quiz results are saved

1. Open `data/quiz_results.csv` in a text editor. At first it contains only the header row:
   `student_id,student_name,course_name,topic,quiz_date,score,total_questions,percentage`
2. Take a quiz and press **Submit quiz**.
3. Check the file again. **One new row** has been added, for example:
   `S101,Ali Khan,Python Programming,Functions,2026-10-14 10:30:12,3,4,75.0`
4. You can also check in any of these ways:
   * open the **Dataset** page, section `quiz_results.csv`;
   * open **My Results** and enter your ID;
   * run this in the project folder:
     ```bash
     python -c "import pandas as pd; print(pd.read_csv('data/quiz_results.csv'))"
     ```

Notes:
* A row is added **only** after pressing Submit. Opening a quiz, or refreshing the result page, never saves anything.
* If you open the CSV in Excel while testing, close it before submitting. Windows locks open files and the app will show a "could not be saved" message.
* To start fresh, delete every row except the header line in `quiz_results.csv`.

## 6. Folder structure

```text
ai_learning_study_assistant/
├── app.py               Flask routes (connects pages and Python code)
├── quiz_logic.py        Load courses/questions, validate input, mark quiz, save result, study notes
├── analysis.py          Pandas + NumPy statistics, Matplotlib + Seaborn charts
├── recommendations.py   Rule-based study suggestions (core Python)
├── requirements.txt
├── README.md
├── data/
│   ├── courses.csv          3 courses and their topics
│   ├── questions.csv        32 MCQs (4 per topic)
│   ├── quiz_results.csv     REAL submissions (starts with the header only)
│   └── sample_students.csv  SAMPLE records for testing, kept separate from real results
├── static/
│   ├── css/style.css
│   └── images/charts/       charts are created here by the Performance page
└── templates/               12 pages + base.html
```

`templates/base.html` is the shared layout (menu and footer). Every page "extends" it, so the menu is written once instead of twelve times.

## 7. How the analysis works

* **Total attempts, average score / percentage, highest and lowest** – `np.mean`, `np.argmax`, `np.argmin` on the saved scores.
* **Student-wise, course-wise and topic-wise** – Pandas `groupby`.
* **Score changes** – only the *same student on the same course and topic* is compared. With at least two attempts, change = latest percentage minus first percentage.
* **Charts** (`static/images/charts/`): course average, topic performance, student comparison, score progress. They are redrawn from the CSV every time the Performance page opens. With no data the page shows a message instead.

## 8. Study support rules (`recommendations.py`)

| Latest percentage | Suggestion |
|---|---|
| Below 50% | Review the notes and practise the same topic again |
| 50% to below 75% | Review incorrect answers and attempt more practice questions |
| 75% or above | Move on to the next topic or try another quiz |

## 9. Customising

* **Portfolio pages** – open `templates/shahid.html`, `bilal.html` and `owais.html` and replace the text with each member's real introduction, skills and contribution. The short card text on the homepage is in `app.py` (`index()` function).
* **Add a course** – add a row to `courses.csv`. Topics are separated by `;`.
* **Add questions** – add rows to `questions.csv`. `correct_answer` must be `A`, `B`, `C` or `D`, and `topic` must match a topic in `courses.csv` exactly.
* **Add notes** – edit the `STUDY_NOTES` dictionary in `quiz_logic.py` (course name, then topic name).
* Before sharing the project online, change `app.secret_key` in `app.py`.
