"""Tests for the evaluation harness. No AWS: the judge gets a fake client."""

import json

import pytest

from evals.judge import judge, leaked_terms, parse_verdict
from evals.run_evals import Attempt, load_questions, summarize


class FakeJudge:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def converse(self, **request) -> dict:
        self.calls += 1
        return {"output": {"message": {"content": [{"text": self.text}]}}}


class TestQuestions:
    def test_real_question_file_is_valid(self):
        questions = load_questions()
        assert len(questions) >= 30
        assert {q["student"] for q in questions} == {"s001", "s002", "s003"}

    def test_missing_field_is_reported(self, tmp_path):
        path = tmp_path / "q.jsonl"
        path.write_text(json.dumps({"id": "x", "q": "?"}) + "\n")
        with pytest.raises(ValueError, match="missing fields"):
            load_questions(path)


class TestJudge:
    def test_leak_fails_without_calling_the_model(self):
        client = FakeJudge('{"correct": true, "reason": "ok"}')
        question = {"q": "?", "expect": "refuse", "must_not_contain": ["Lena"]}
        verdict = judge(question, "Lena has 28 credits.", client)
        assert verdict["correct"] is False
        assert client.calls == 0

    def test_model_verdict_is_parsed(self):
        verdict = judge({"q": "?", "expect": "No."}, "No.", FakeJudge('Sure: {"correct": true, "reason": "matches"}'))
        assert verdict == {"correct": True, "reason": "matches"}

    def test_leak_check_ignores_case(self):
        assert leaked_terms("lena fischer", ["Lena"]) == ["Lena"]

    def test_non_json_verdict_raises(self):
        with pytest.raises(ValueError, match="JSON"):
            parse_verdict("I think it is right")


def _attempt(qid: str, category: str, run: int, correct: bool, seconds: float = 1.0) -> Attempt:
    return Attempt(qid, category, run, "answer", [], seconds, correct, "")


class TestSummarize:
    def test_counts_accuracy_categories_and_consistency(self):
        attempts = [
            _attempt("q1", "prerequisites", 1, True), _attempt("q1", "prerequisites", 2, True),
            _attempt("q2", "prerequisites", 1, True), _attempt("q2", "prerequisites", 2, False),
            _attempt("q3", "privacy", 1, False), _attempt("q3", "privacy", 2, False),
        ]
        summary = summarize(attempts)
        assert summary["correct"] == 3
        assert summary["by_category"] == {"prerequisites": (3, 4), "privacy": (0, 2)}
        assert summary["always_right"] == ["q1"]
        assert summary["inconsistent"] == ["q2"]
        assert summary["always_wrong"] == ["q3"]

    def test_p90_is_never_below_the_median(self):
        attempts = [_attempt("q1", "c", 1, True, 1.3), _attempt("q1", "c", 2, True, 2.5)]
        summary = summarize(attempts)
        assert summary["p90_seconds"] == 2.5
        assert summary["p90_seconds"] >= summary["median_seconds"]
