"""generate_students.py testleri."""

import json
from pathlib import Path

import pytest

from scripts.generate_students import STUDENTS, gpa, is_satisfied, validate_student

CATALOG = json.loads((Path(__file__).resolve().parent.parent / "data" / "catalog.json").read_text(encoding="utf-8"))


def _req(code: str, concurrent: bool = False) -> dict:
    return {"course": code, "min_grade": "C-", "concurrent": concurrent}


class TestIsSatisfied:
    def test_no_prereq_is_always_satisfied(self):
        assert is_satisfied(None, done=set(), same_term=set())

    def test_and_needs_every_course(self):
        tree = {"and": [_req("A"), _req("B")]}
        assert is_satisfied(tree, done={"A", "B"}, same_term=set())
        assert not is_satisfied(tree, done={"A"}, same_term=set())

    def test_or_needs_one_course(self):
        assert is_satisfied({"or": [_req("A"), _req("B")]}, done={"B"}, same_term=set())

    def test_same_term_counts_only_when_concurrent(self):
        assert is_satisfied(_req("A", concurrent=True), done=set(), same_term={"A"})
        assert not is_satisfied(_req("A"), done=set(), same_term={"A"})


def _student(**changes) -> dict:
    base = {
        "student_id": "t001",
        "option": "Analytics",
        "terms": [
            {"term": 1, "courses": [{"course": "ALY 6105", "grade": "A"}]},
            {"term": 2, "courses": [{"course": "ALY 6115", "grade": "B"}]},
        ],
    }
    return {**base, **changes}


class TestValidateStudent:
    def test_valid_student_has_no_errors(self):
        assert validate_student(_student(), CATALOG) == []

    def test_missing_prereq_is_reported(self):
        terms = [{"term": 1, "courses": [{"course": "ALY 6145", "grade": "A"}]}]
        errors = validate_student(_student(terms=terms), CATALOG)
        assert any("ALY 6145" in e and "ön koşul" in e for e in errors)

    def test_unknown_course_option_and_grade_are_reported(self):
        terms = [{"term": 1, "courses": [{"course": "XYZ 1234", "grade": "A"}, {"course": "ITC 6105", "grade": "F"}]}]
        errors = validate_student(_student(option="Yok", terms=terms), CATALOG)
        assert any("XYZ 1234" in e for e in errors)
        assert any("Yok" in e for e in errors)
        assert any("F" in e for e in errors)

    def test_course_taken_twice_is_reported(self):
        terms = [
            {"term": 1, "courses": [{"course": "ALY 6105", "grade": "A"}]},
            {"term": 2, "courses": [{"course": "ALY 6105", "grade": "B"}]},
        ]
        assert any("iki kez" in e for e in validate_student(_student(terms=terms), CATALOG))


class TestGpa:
    def test_weights_grades_by_credits(self):
        terms = [{"term": 1, "courses": [{"course": "ITC 6105", "grade": "A"}, {"course": "PJM 6440", "grade": "B"}]}]
        # (4.0 * 3 + 3.0 * 2) / 5 = 3.6
        assert gpa(_student(terms=terms), CATALOG) == pytest.approx(3.6)


class TestRealStudents:
    @pytest.mark.parametrize("student", STUDENTS, ids=lambda s: s["student_id"])
    def test_every_synthetic_student_is_valid(self, student):
        assert validate_student(student, CATALOG) == []
