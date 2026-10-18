"""Tests for src/tools/transcript.py. Uses the synthetic students in data/students.json."""

import pytest

from decimal import Decimal

import src.tools.transcript as transcript
from src.tools.transcript import StudentNotFoundError, get_transcript, load_student


class TestLoadStudent:
    def test_returns_raw_record(self):
        assert load_student("s001")["name"] == "Maya Okafor"

    def test_unknown_student_raises_clear_error(self):
        with pytest.raises(StudentNotFoundError, match="s999"):
            load_student("s999")


class TestGetTranscript:
    def setup_method(self):
        self.transcript = get_transcript("s001")

    def test_never_returns_pin(self):
        assert "pin" not in self.transcript
        assert "4821" not in str(self.transcript)

    def test_courses_include_title_credits_and_grade(self):
        first = self.transcript["terms"][0]["courses"][0]
        assert first == {"course": "ITC 6105", "title": "Foundations of Informatics", "credits": 3, "grade": "A"}

    def test_totals_are_calculated(self):
        assert self.transcript["credits_completed"] == 6
        assert self.transcript["credits_required"] == 34
        assert self.transcript["gpa"] == 3.83

    def test_keeps_identity_and_option(self):
        assert self.transcript["student_id"] == "s001"
        assert self.transcript["option"] == "Information Security Management"

    def test_near_graduation_student(self):
        assert get_transcript("s003")["credits_completed"] == 28


class FakeTable:
    def __init__(self, items: dict):
        self.items = items

    def get_item(self, Key: dict) -> dict:
        item = self.items.get(Key["student_id"])
        return {"Item": item} if item else {}


class TestDynamoSource:
    def setup_method(self):
        self.record = {"student_id": "s009", "name": "Test", "pin": "1", "option": "Analytics",
                       "terms": [{"term": Decimal("1"), "courses": [{"course": "ITC 6105", "grade": "A"}]}]}

    def test_reads_from_the_table_when_env_is_set(self, monkeypatch):
        monkeypatch.setenv("STUDENTS_TABLE", "students")
        monkeypatch.setattr(transcript, "_students_table", lambda name: FakeTable({"s009": self.record}))
        student = load_student("s009")
        assert student["name"] == "Test"
        assert student["terms"][0]["term"] == 1 and isinstance(student["terms"][0]["term"], int)

    def test_missing_item_raises(self, monkeypatch):
        monkeypatch.setenv("STUDENTS_TABLE", "students")
        monkeypatch.setattr(transcript, "_students_table", lambda name: FakeTable({}))
        with pytest.raises(StudentNotFoundError, match="s404"):
            load_student("s404")

    def test_file_is_used_without_env(self, monkeypatch):
        monkeypatch.delenv("STUDENTS_TABLE", raising=False)
        assert load_student("s001")["name"] == "Maya Okafor"
