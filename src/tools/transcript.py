"""Records clerk: the get_transcript tool (phase 2.1).

Returns the student's courses, total credits and GPA. Python calculates credits and GPA,
the LLM only reads the finished numbers. The PIN is never returned.

Reading goes through load_student(). In phase 6 only this function will switch to DynamoDB.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STUDENTS_PATH = PROJECT_ROOT / "data" / "students.json"
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog.json"

GRADE_POINTS = {"A": 4.0, "A-": 3.667, "B+": 3.333, "B": 3.0, "B-": 2.667, "C+": 2.333, "C": 2.0, "C-": 1.667}
GPA_DECIMALS = 2


class StudentNotFoundError(LookupError):
    pass


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_student(student_id: str) -> dict:
    """The raw student record (including the PIN). Use only inside this module."""
    students = _read_json(STUDENTS_PATH)["students"]
    if student_id not in students:
        raise StudentNotFoundError(f"Student not found: {student_id}")
    return students[student_id]


def _all_courses(student: dict) -> list[dict]:
    return [entry for term in student["terms"] for entry in term["courses"]]


def total_credits(student: dict, catalog: dict) -> int:
    return sum(catalog["courses"][entry["course"]]["credits"] for entry in _all_courses(student))


def gpa(student: dict, catalog: dict) -> float:
    """Credit-weighted grade point average."""
    entries = _all_courses(student)
    credits = [catalog["courses"][entry["course"]]["credits"] for entry in entries]
    points = sum(GRADE_POINTS[entry["grade"]] * credit for entry, credit in zip(entries, credits))
    return points / sum(credits)


def _describe(entry: dict, courses: dict) -> dict:
    course = courses[entry["course"]]
    return {"course": entry["course"], "title": course["title"], "credits": course["credits"], "grade": entry["grade"]}


def get_transcript(student_id: str) -> dict:
    """The transcript sent to the LLM. The session supplies student_id, not the LLM."""
    student = load_student(student_id)
    catalog = _read_json(CATALOG_PATH)
    return {
        "student_id": student["student_id"],
        "name": student["name"],
        "option": student["option"],
        "terms": [
            {"term": term["term"], "courses": [_describe(entry, catalog["courses"]) for entry in term["courses"]]}
            for term in student["terms"]
        ],
        "credits_completed": total_credits(student, catalog),
        "credits_required": catalog["program"]["total_credits"],
        "gpa": round(gpa(student, catalog), GPA_DECIMALS),
    }
