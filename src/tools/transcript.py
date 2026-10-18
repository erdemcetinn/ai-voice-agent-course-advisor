"""Records clerk: the get_transcript tool (phase 2.1).

Returns the student's courses, total credits and GPA. Python calculates credits and GPA,
the LLM only reads the finished numbers. The PIN is never returned.

Reading goes through load_student(): from data/students.json by default, or from DynamoDB when
the STUDENTS_TABLE environment variable names a table (set on Lambda, phase 6.2).
"""

import json
import os
from decimal import Decimal
from pathlib import Path

import boto3

from src.data import load_catalog

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STUDENTS_PATH = PROJECT_ROOT / "data" / "students.json"
STUDENTS_TABLE_ENV = "STUDENTS_TABLE"

GRADE_POINTS = {"A": 4.0, "A-": 3.667, "B+": 3.333, "B": 3.0, "B-": 2.667, "C+": 2.333, "C": 2.0, "C-": 1.667}
GPA_DECIMALS = 2


class StudentNotFoundError(LookupError):
    pass


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _students_table(name: str):
    return boto3.resource("dynamodb").Table(name)


def _plain(value):
    """DynamoDB returns numbers as Decimal; turn them back into int or float so they serialize as JSON."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def load_student(student_id: str) -> dict:
    """The raw student record (including the PIN). Use only inside this module."""
    table_name = os.environ.get(STUDENTS_TABLE_ENV)
    if table_name:
        record = _students_table(table_name).get_item(Key={"student_id": student_id}).get("Item")
    else:
        record = _read_json(STUDENTS_PATH)["students"].get(student_id)
    if record is None:
        raise StudentNotFoundError(f"Student not found: {student_id}")
    return _plain(record)


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
    catalog = load_catalog()
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
