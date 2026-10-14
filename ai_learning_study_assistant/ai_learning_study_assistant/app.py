"""
app.py
------
The Flask application. It connects the web pages (templates/) to the Python
code in quiz_logic.py, analysis.py and recommendations.py.

Run it with:   python app.py
Then open:     http://127.0.0.1:5000
"""

import time

from flask import Flask, redirect, render_template, request, session, url_for

import analysis
import quiz_logic
import recommendations

app = Flask(__name__)

# Flask needs a secret key to remember the last quiz result between the
# "submit" step and the "result" page. Change this text for a real deployment.
app.secret_key = "change-this-secret-key-before-sharing-the-project"


# Make a helper available inside every HTML template.
@app.context_processor
def template_helpers():
    return {"make_anchor": quiz_logic.make_anchor}


# ---------------------------------------------------------------------------
# Main pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Homepage: introduction and the three team member cards."""
    team = [
        {"name": "Shahid", "page": "shahid",
         "intro": "Shahid is a member of the AI Learning & Study Assistant team, working on a study tool that combines courses, notes and quizzes."},
        {"name": "Bilal", "page": "bilal",
         "intro": "Bilal is a member of the AI Learning & Study Assistant team, helping to turn quiz results into clear progress reports for students."},
        {"name": "Owais Qayoom", "page": "owais",
         "intro": "Owais Qayoom is a member of the AI Learning & Study Assistant team, building Python-based study support for learners."},
    ]
    return render_template("index.html", team=team)


@app.route("/courses")
def courses():
    """List all courses (and their topics) from courses.csv."""
    return render_template("courses.html", courses=quiz_logic.load_courses())


@app.route("/notes")
def notes():
    """Course-wise and topic-wise study notes."""
    return render_template("notes.html", notes=quiz_logic.get_notes(quiz_logic.load_courses()))


# ---------------------------------------------------------------------------
# Quiz workflow
# ---------------------------------------------------------------------------
@app.route("/quiz")
def quiz():
    """Three steps on one page, chosen by what is in the web address:

    Step 1: student ID, name and course
    Step 2: choose a topic
    Step 3: answer the questions
    """
    all_courses = quiz_logic.load_courses()
    args = request.args

    # Step 1 (first visit). A course may be pre-selected from the Courses page.
    if "student_id" not in args:
        form = {"student_id": "", "student_name": "", "course_id": args.get("course_id", "")}
        return render_template("quiz.html", stage=1, courses=all_courses, form=form, errors=[])

    form = {"student_id": args.get("student_id", ""),
            "student_name": args.get("student_name", ""),
            "course_id": args.get("course_id", "")}

    # Check the student details and course.
    student_id, student_name, errors = quiz_logic.validate_student(form["student_id"], form["student_name"])
    course = quiz_logic.find_course(all_courses, form["course_id"])
    if course is None:
        errors.append("Please select a course.")
    if errors:
        return render_template("quiz.html", stage=1, courses=all_courses, form=form, errors=errors)

    form["student_id"], form["student_name"] = student_id, student_name

    # Step 2: show the topics of the chosen course.
    topic = args.get("topic")
    if topic is None:
        return render_template("quiz.html", stage=2, course=course, form=form, errors=[])
    if topic not in course["topics"]:
        return render_template("quiz.html", stage=2, course=course, form=form,
                               errors=["Please choose a topic from the list."])

    # Step 3: load the questions for this topic.
    questions = quiz_logic.load_questions(course["course_id"], topic)
    if not questions:
        return render_template("quiz.html", stage=2, course=course, form=form,
                               errors=["There are no questions for this topic yet. Please choose another topic."])
    return render_template("quiz.html", stage=3, course=course, topic=topic,
                           questions=questions, form=form, selected={}, errors=[])


@app.route("/submit", methods=["POST"])
def submit():
    """Mark the quiz, save the result and show the result page.

    The score is calculated ONLY here, after the student presses Submit.
    """
    all_courses = quiz_logic.load_courses()
    form = {"student_id": request.form.get("student_id", ""),
            "student_name": request.form.get("student_name", ""),
            "course_id": request.form.get("course_id", "")}
    topic = request.form.get("topic", "")

    # Re-check everything, because anyone can send a form to this address.
    student_id, student_name, errors = quiz_logic.validate_student(form["student_id"], form["student_name"])
    course = quiz_logic.find_course(all_courses, form["course_id"])
    if course is None:
        errors.append("Please select a course.")
    elif topic not in course["topics"]:
        errors.append("Please choose a topic.")
    if errors:
        return render_template("quiz.html", stage=1, courses=all_courses, form=form, errors=errors)

    questions = quiz_logic.load_questions(course["course_id"], topic)
    if not questions:
        return render_template("quiz.html", stage=2, course=course, form=form,
                               errors=["There are no questions for this topic yet."])

    # Collect the chosen answers. Every question must have a valid answer (A-D).
    answers = {}
    for q in questions:
        choice = request.form.get("q_" + q["question_id"], "").strip().upper()
        if choice in quiz_logic.LETTERS:
            answers[q["question_id"]] = choice

    form["student_id"], form["student_name"] = student_id, student_name
    if len(answers) < len(questions):
        missing = len(questions) - len(answers)
        return render_template("quiz.html", stage=3, course=course, topic=topic,
                               questions=questions, form=form, selected=answers,
                               errors=[f"{missing} question(s) not answered yet. Answer every question, then submit."])

    # Mark the quiz.
    outcome = quiz_logic.score_quiz(questions, answers)

    # Save the result as a new row in quiz_results.csv.
    try:
        quiz_logic.save_result(student_id, student_name, course["course_name"], topic,
                               outcome["score"], outcome["total"], outcome["percentage"])
    except OSError:
        return render_template("quiz.html", stage=3, course=course, topic=topic,
                               questions=questions, form=form, selected=answers,
                               errors=["The result could not be saved. If data/quiz_results.csv is open in "
                                       "another program, close it and press Submit again."])

    # Remember the outcome for the result page, then redirect.
    # (Redirecting means refreshing the result page cannot save the quiz twice.)
    session["last_result"] = {
        "student_id": student_id, "student_name": student_name,
        "course_id": course["course_id"], "topic": topic, "answers": answers,
        "score": outcome["score"], "total": outcome["total"], "percentage": outcome["percentage"],
    }
    return redirect(url_for("result"))


@app.route("/result")
def result():
    """Score, total marks, percentage, feedback and answer review."""
    saved = session.get("last_result")
    if not saved:
        return redirect(url_for("quiz"))

    all_courses = quiz_logic.load_courses()
    course = quiz_logic.find_course(all_courses, saved["course_id"])
    if course is None:
        return redirect(url_for("quiz"))

    questions = quiz_logic.load_questions(course["course_id"], saved["topic"])
    review = quiz_logic.score_quiz(questions, saved["answers"])["review"]

    # Study suggestion for this topic, based on this student's saved results.
    all_results = analysis.load_results()
    mine = analysis.get_student_results(all_results, saved["student_id"]).iloc[::-1]   # oldest first
    plan = recommendations.build_recommendations(mine.to_dict("records"), all_courses)
    topic_advice = next((t for t in plan["topics"]
                         if t["course_name"] == course["course_name"] and t["topic"] == saved["topic"]), None)

    return render_template("result.html", saved=saved, course=course, review=review,
                           level=recommendations.get_level(saved["percentage"]),
                           feedback=recommendations.get_feedback(saved["percentage"]),
                           topic_advice=topic_advice)


# ---------------------------------------------------------------------------
# Results, performance and study support
# ---------------------------------------------------------------------------
@app.route("/my-results")
def my_results():
    """Previous quiz results for one student ID."""
    raw_id = request.args.get("student_id", "")
    context = {"searched": False, "student_id": raw_id, "error": "", "rows": [], "summary": None}

    if "student_id" in request.args:
        student_id = quiz_logic.clean_student_id(raw_id)
        if not student_id:
            context["error"] = "Enter a valid student ID (letters, numbers, '-' or '_')."
        else:
            mine = analysis.get_student_results(analysis.load_results(), student_id)
            context.update(searched=True, student_id=student_id,
                           rows=mine.to_dict("records"), summary=analysis.student_summary(mine))
    return render_template("my_results.html", **context)


@app.route("/performance")
def performance():
    """Statistics tables and charts built from quiz_results.csv."""
    results = analysis.load_results()
    charts = analysis.generate_charts(results)
    return render_template(
        "performance.html",
        summary=analysis.overall_summary(results),
        students=analysis.student_performance(results).to_dict("records"),
        course_rows=analysis.course_performance(results).to_dict("records"),
        topic_rows=analysis.topic_performance(results).to_dict("records"),
        changes=analysis.score_changes(results).to_dict("records"),
        charts=charts,
        version=int(time.time()),          # makes the browser reload new chart images
    )


@app.route("/dataset")
def dataset():
    """Show every CSV file in a readable table."""
    files = [
        ("courses.csv", "Courses available in the quiz.", quiz_logic.COURSES_FILE, quiz_logic.COURSE_COLUMNS, False),
        ("questions.csv", "The MCQ question bank.", quiz_logic.QUESTIONS_FILE, quiz_logic.QUESTION_COLUMNS, False),
        ("quiz_results.csv", "Actual quiz submissions. A new row is added each time a quiz is submitted.",
         quiz_logic.RESULTS_FILE, quiz_logic.RESULT_COLUMNS, False),
        ("sample_students.csv", "SAMPLE DATA for testing only. It is kept separate from real quiz submissions.",
         quiz_logic.SAMPLE_FILE, ["student_id", "student_name", "course_name", "study_hours"], True),
    ]
    tables = []
    for name, description, path, columns, is_sample in files:
        data = quiz_logic.read_csv_safe(path, columns)
        tables.append({"name": name, "description": description, "is_sample": is_sample,
                       "columns": list(data.columns), "rows": data.values.tolist()})
    return render_template("dataset.html", tables=tables)


@app.route("/assistant")
def assistant():
    """Rule-based study suggestions for one student."""
    raw_id = request.args.get("student_id", "")
    context = {"searched": False, "student_id": raw_id, "error": "", "plan": None}

    if "student_id" in request.args:
        student_id = quiz_logic.clean_student_id(raw_id)
        if not student_id:
            context["error"] = "Enter a valid student ID (letters, numbers, '-' or '_')."
        else:
            mine = analysis.get_student_results(analysis.load_results(), student_id).iloc[::-1]  # oldest first
            plan = recommendations.build_recommendations(mine.to_dict("records"), quiz_logic.load_courses())
            context.update(searched=True, student_id=student_id, plan=plan, attempts=len(mine))
    return render_template("assistant.html", **context)


# ---------------------------------------------------------------------------
# Team portfolio pages (one page per member)
# ---------------------------------------------------------------------------
@app.route("/shahid.html")
def shahid():
    return render_template("shahid.html")


@app.route("/bilal.html")
def bilal():
    return render_template("bilal.html")


@app.route("/owais.html")
def owais():
    return render_template("owais.html")


@app.errorhandler(404)
def page_not_found(error):
    return render_template("base.html", not_found=True), 404


if __name__ == "__main__":
    app.run(debug=True)
