"""Tests for src/tools/planner.py. Uses the real catalog and synthetic students, plus one test-only student."""

import json
from pathlib import Path

import pytest

from src.tools.planner import check_course, is_satisfied, plan_next_semester, remaining_requirements
from src.tools.transcript import load_student

CATALOG = json.loads((Path(__file__).resolve().parent.parent / "data" / "catalog.json").read_text(encoding="utf-8"))


def _req(code: str, concurrent: bool = False) -> dict:
    return {"course": code, "min_grade": "C-", "concurrent": concurrent}


class TestIsSatisfied:
    def test_and_or_and_concurrent(self):
        tree = {"and": [_req("A"), {"or": [_req("B"), _req("C", concurrent=True)]}]}
        assert is_satisfied(tree, done={"A", "B"}, same_term=set())
        assert is_satisfied(tree, done={"A"}, same_term={"C"})
        assert not is_satisfied(tree, done={"B"}, same_term=set())


class TestRemainingRequirements:
    def test_new_student(self):
        remaining = remaining_requirements(load_student("s001"), CATALOG)
        assert [c["course"] for c in remaining["core_missing"]] == ["ITC 6150", "ITC 6205", "ITC 6250", "PJM 6440", "ITC 6980"]
        assert [c["course"] for c in remaining["option_missing"]] == ["ITC 6620", "ITC 6630", "ITC 6640"]
        assert remaining["restricted_elective_credits_remaining"] == 4
        assert remaining["credits_remaining"] == 28

    def test_near_graduation_student(self):
        remaining = remaining_requirements(load_student("s003"), CATALOG)
        assert [c["course"] for c in remaining["core_missing"]] == ["ITC 6980"]
        assert remaining["core_missing"][0]["credits"] == 4
        assert remaining["choose"] == [{"credits_remaining": 0, "from": ["ALY 6125", "ALY 6610", "ALY 6620"]}]
        assert remaining["restricted_elective_credits_remaining"] == 2
        assert remaining["credits_remaining"] == 6

    def test_mid_program_student(self):
        assert remaining_requirements(load_student("s002"), CATALOG)["credits_remaining"] == 14

    def test_course_that_does_not_count_is_not_subtracted(self):
        student = {
            "student_id": "t001",
            "option": "Analytics",
            "terms": [{"term": 1, "courses": [
                {"course": "ALY 6105", "grade": "A"}, {"course": "ALY 6115", "grade": "A"},
                {"course": "ALY 6610", "grade": "A"}, {"course": "ALY 6620", "grade": "A"},
            ]}],
        }
        remaining = remaining_requirements(student, CATALOG)
        assert remaining["courses_not_counting"] == ["ALY 6620"]
        # 12 credits taken, but only 9 count: 34 - 9 = 25, not 34 - 12 = 22
        assert remaining["credits_remaining"] == 25


class TestCheckCourse:
    def test_missing_prerequisite_is_named(self):
        result = check_course("ITC 6680", load_student("s001"), CATALOG)
        assert result["eligible_now"] is False
        assert result["missing_prerequisites"] == "ITC 6620"

    def test_eligible_course_that_does_not_count(self):
        result = check_course("ALY 6620", load_student("s003"), CATALOG)
        assert result["eligible_now"] is True
        assert result["counts_toward"] == []
        assert "does not count" in result["note"]

    def test_concurrent_prerequisite(self):
        result = check_course("ALY 6115", load_student("s001"), CATALOG)
        assert result["eligible_now"] is False
        assert result["can_take_together_with"] == ["ALY 6105"]

    def test_capstone_counts_as_core(self):
        result = check_course("ITC 6980", load_student("s002"), CATALOG)
        assert result["eligible_now"] is True
        assert result["counts_toward"] == ["required core course"]

    def test_or_groups_are_described(self):
        missing = check_course("ITC 6980", load_student("s001"), CATALOG)["missing_prerequisites"]
        assert missing.startswith("one of:")
        assert "ITC 6150" in missing and "PJM 6440" in missing and "ITC 6105" not in missing.split("or (")[0]

    def test_completed_course(self):
        assert check_course("ITC 6610", load_student("s001"), CATALOG)["completed"] is True

    def test_unknown_course_raises(self):
        with pytest.raises(ValueError, match="not in the catalog"):
            check_course("ITC 9999", load_student("s001"), CATALOG)


class TestPlanNextSemester:
    def test_full_plan_lists_counting_eligible_and_blocked_courses(self):
        plan = plan_next_semester("s002")
        eligible = {c["course"] for c in plan["eligible_now_and_counting"]}
        assert {"ITC 6660", "ITC 6670", "ITC 6980", "ITC 6405"} <= eligible
        assert "ITC 6680" not in eligible
        assert "ALY 6105" not in eligible
        assert "ITC 6680" in {c["course"] for c in plan["needed_but_blocked"]}
        assert plan["remaining"]["credits_remaining"] == 14

    def test_variable_credit_course_does_not_crash(self):
        eligible = {c["course"]: c for c in plan_next_semester("s002")["eligible_now_and_counting"]}
        assert eligible["ITC 6983"]["credits"] == {"min": 1, "max": 4}

    def test_single_course_mode(self):
        assert plan_next_semester("s001", "ITC 6680")["eligible_now"] is False
