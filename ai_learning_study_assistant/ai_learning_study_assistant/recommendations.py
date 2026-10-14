"""
recommendations.py
------------------
Python-based, RULE-BASED study support.

This is NOT a trained AI or machine-learning model. It only uses simple
if / elif / else rules on the percentages saved in quiz_results.csv:

    below 50%            -> review the notes and practise the same topic again
    50% to below 75%     -> review incorrect answers and try more practice
    75% or above         -> move on to the next topic or another quiz

Only core Python is used here (no Pandas), so it is easy to read.
"""


def get_level(percentage):
    """Return a short level name for a percentage."""
    if percentage < 50:
        return "Needs practice"
    elif percentage < 75:
        return "Developing"
    else:
        return "Strong"


def get_feedback(percentage):
    """Feedback message shown on the result page right after a quiz."""
    if percentage < 50:
        return "Keep going. This topic needs more practice, and the notes are a good place to start."
    elif percentage < 75:
        return "Good effort. You understand the basics, and a little more practice will lift your score."
    elif percentage < 100:
        return "Great work. You know this topic well."
    else:
        return "Perfect score. Excellent work."


def make_advice(topic, percentage, next_topic=None):
    """Apply the three study rules to one topic and return one sentence of advice."""
    if percentage < 50:
        return f"Review the notes for {topic} and practise this topic again."
    elif percentage < 75:
        return (f"Review the questions you answered incorrectly in {topic} "
                f"and attempt more practice questions on it.")
    else:
        if next_topic:
            return f"You are doing well in {topic}. Move on to the next topic: {next_topic}."
        return f"You are doing well in {topic}. Try another available quiz."


def next_untried_topic(course, topic, tried_topics):
    """Find the next topic in the same course that the student has not attempted yet."""
    topics = course["topics"]
    if topic not in topics:
        return None
    start = topics.index(topic) + 1
    for candidate in topics[start:]:
        if candidate not in tried_topics:
            return candidate
    return None


def build_recommendations(attempts, courses):
    """Create study suggestions for ONE student.

    attempts : list of dictionaries (that student's rows from quiz_results.csv),
               ordered from oldest to newest
    courses  : list from quiz_logic.load_courses()

    Returns a dictionary with an overall message, one entry per attempted topic
    (weakest first) and a list of topics not attempted yet.
    """
    # 1. Group the attempts by (course, topic).
    grouped = {}
    for row in attempts:
        key = (row["course_name"], row["topic"])
        grouped.setdefault(key, []).append(float(row["percentage"]))

    course_by_name = {c["course_name"]: c for c in courses}
    tried = {}                               # course name -> set of attempted topics
    for course_name, topic in grouped:
        tried.setdefault(course_name, set()).add(topic)

    # 2. One suggestion for every topic, based on the LATEST attempt.
    topic_items = []
    for (course_name, topic), percentages in grouped.items():
        latest = percentages[-1]
        course = course_by_name.get(course_name)
        next_topic = None
        if course:
            next_topic = next_untried_topic(course, topic, tried.get(course_name, set()))

        if len(percentages) >= 2:
            change = round(latest - percentages[0], 1)
            if change > 0:
                progress = f"Up {change} points since your first attempt."
            elif change < 0:
                progress = f"Down {abs(change)} points since your first attempt."
            else:
                progress = "Same as your first attempt."
        else:
            progress = "First attempt so far."

        topic_items.append({
            "course_name": course_name,
            "topic": topic,
            "attempts": len(percentages),
            "latest_percentage": round(latest, 1),
            "best_percentage": round(max(percentages), 1),
            "level": get_level(latest),
            "advice": make_advice(topic, latest, next_topic),
            "progress": progress,
        })
    topic_items.sort(key=lambda item: item["latest_percentage"])      # weakest first

    # 3. Topics the student has not tried yet.
    not_tried = []
    for course in courses:
        for topic in course["topics"]:
            if topic not in tried.get(course["course_name"], set()):
                not_tried.append({"course_name": course["course_name"], "topic": topic})

    # 4. Overall message.
    if not topic_items:
        overall = "No quiz results yet. Take a quiz to get study suggestions."
    else:
        average = sum(item["latest_percentage"] for item in topic_items) / len(topic_items)
        weakest = topic_items[0]
        if weakest["latest_percentage"] < 75:
            overall = (f"Your latest results average {average:.1f}%. "
                       f"Focus first on {weakest['topic']} ({weakest['course_name']}).")
        else:
            overall = (f"Your latest results average {average:.1f}% and every attempted topic is "
                       f"at 75% or above. Try a new topic or another course.")

    return {"overall": overall, "topics": topic_items, "not_tried": not_tried}
