"""Checks 3 synthetic (made-up) students against the catalog and writes data/students.json.

Usage:
    python -m scripts.generate_students

The students are designed by hand, each one represents a different situation. The script does not
invent data, it checks that it is consistent: are the courses in the catalog, were prerequisites taken
in earlier terms, is the GPA above 3.0. All grades are passing grades (no failed-course scenario, by design).
Terms are numbered (1, 2, 3...) instead of dated. "Next term" is the term after the last number.
"""

import json
import logging
import sys
from pathlib import Path

from src.tools.planner import is_satisfied
from src.tools.transcript import GRADE_POINTS, gpa, total_credits

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "students.json"

log = logging.getLogger(__name__)


def _term(number: int, *courses: tuple[str, str]) -> dict:
    return {"term": number, "courses": [{"course": code, "grade": grade} for code, grade in courses]}


STUDENTS = [
    {
        # Just started: 1 term. Has not taken ITC 6620, so not yet eligible for ITC 6680.
        "student_id": "s001",
        "name": "Maya Okafor",
        "pin": "4821",
        "option": "Information Security Management",
        "terms": [_term(1, ("ITC 6105", "A"), ("ITC 6610", "A-"))],
    },
    {
        # Midway: 3 terms, 20 credits.
        "student_id": "s002",
        "name": "Daniel Reyes",
        "pin": "7350",
        "option": "Cloud Computing Application and Management",
        "terms": [
            _term(1, ("ITC 6105", "B+"), ("ITC 6150", "B")),
            _term(2, ("ITC 6205", "A-"), ("ITC 6650", "B+")),
            _term(3, ("ITC 6250", "B"), ("ITC 6630", "A"), ("PJM 6440", "B+")),
        ],
    },
    {
        # Close to graduation: 4 terms, 28 credits. Remaining: capstone (ITC 6980) + 2 credits of restricted electives.
        "student_id": "s003",
        "name": "Lena Fischer",
        "pin": "2694",
        "option": "Analytics",
        "terms": [
            _term(1, ("ITC 6105", "A"), ("ALY 6105", "A-"), ("ITC 6150", "B+")),
            _term(2, ("ALY 6115", "A"), ("ITC 6205", "B+"), ("PJM 6440", "A")),
            _term(3, ("ALY 6145", "A-"), ("ALY 6610", "B+"), ("ITC 6250", "A-")),
            _term(4, ("ITC 6415", "A")),
        ],
    },
]


def _all_courses(student: dict) -> list[dict]:
    return [entry for term in student["terms"] for entry in term["courses"]]


def validate_student(student: dict, catalog: dict) -> list[str]:
    """Returns the inconsistencies in a student record as a list. Empty list = no problems."""
    courses = catalog["courses"]
    sid = student["student_id"]
    option_names = {option["name"] for option in catalog["program"]["options"]}
    errors = [] if student["option"] in option_names else [f"{sid}: unknown option {student['option']!r}"]

    codes = [entry["course"] for entry in _all_courses(student)]
    errors += [f"{sid}: {code} taken twice" for code in sorted({c for c in codes if codes.count(c) > 1})]

    done: set[str] = set()
    for term in student["terms"]:
        same_term = {entry["course"] for entry in term["courses"]}
        for entry in term["courses"]:
            code, grade = entry["course"], entry["grade"]
            if code not in courses:
                errors.append(f"{sid}: {code} is not in the catalog")
                continue
            if grade not in GRADE_POINTS:
                errors.append(f"{sid}: invalid grade {grade!r} for {code}")
            if not is_satisfied(courses[code]["prereq"], done, same_term):
                errors.append(f"{sid}: {code} taken in term {term['term']} but its prerequisite is not met")
        done = done | same_term
    return errors


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    errors = [error for student in STUDENTS for error in validate_student(student, catalog)]
    if errors:
        log.error("Student data is inconsistent:\n  %s", "\n  ".join(errors))
        sys.exit(1)

    output = {
        "meta": {"synthetic": True, "note": "Made-up students. Not real people or records."},
        "students": {student["student_id"]: student for student in STUDENTS},
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for student in STUDENTS:
        log.info(
            "%s %-14s %-45s %d terms, %2d credits, GPA %.2f",
            student["student_id"], student["name"], student["option"],
            len(student["terms"]), total_credits(student, catalog), gpa(student, catalog),
        )
    log.info("Wrote: %s", OUTPUT_PATH.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
