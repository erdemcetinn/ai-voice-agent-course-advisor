"""Tests for src/tools/catalog_search.py. No AWS connection: semantic search uses a fake embedder and a tiny index."""

import numpy as np
import pytest

from src.tools.catalog_search import find_codes, program_roles, search_catalog, top_k


class TestFindCodes:
    def test_finds_codes_in_any_common_spelling(self):
        assert find_codes("Can I take ITC 6680, itc6620 or ALY-6145?") == ["ITC 6680", "ITC 6620", "ALY 6145"]

    def test_ignores_words_that_are_not_catalog_subjects(self):
        assert find_codes("What can I take in fall 2026?") == []

    def test_keeps_retired_codes_with_a_known_subject(self):
        assert find_codes("Is ITC 6300 still offered?") == ["ITC 6300"]


class TestTopK:
    def test_returns_best_rows_first_with_scores(self):
        matrix = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]])
        assert top_k(matrix, np.array([0.0, 1.0]), k=2) == [(1, pytest.approx(1.0)), (2, pytest.approx(0.8))]

    def test_k_larger_than_rows_returns_all_rows(self):
        assert len(top_k(np.eye(2), np.array([1.0, 0.0]), k=5)) == 2


class TestProgramRoles:
    def test_required_course(self):
        assert program_roles("ITC 6105") == ["required for every student"]

    def test_course_in_two_concentrations(self):
        roles = program_roles("ITC 6630")
        assert "required in Cloud Computing Application and Management" in roles
        assert "required in Information Security Management" in roles

    def test_choose_group_and_restricted_elective(self):
        assert program_roles("ALY 6610") == ["one of the choices in Analytics"]
        assert program_roles("ITC 6680") == ["restricted elective"]


class TestExactSearch:
    def test_code_returns_course_details_without_embedding(self):
        result = search_catalog("ITC 6680 prerequisites", embed=_must_not_embed)
        assert result["mode"] == "exact"
        course = result["results"][0]
        assert course["course"] == "ITC 6680"
        assert course["title"] == "CISSP Preparation"
        assert "ITC 6620" in course["prerequisites"]
        assert course["program_roles"] == ["restricted elective"]

    def test_unknown_code_is_reported(self):
        result = search_catalog("ITC 6300", embed=_must_not_embed)
        assert result["results"] == []
        assert result["not_found"] == ["ITC 6300"]


CHUNKS = [
    {"id": "A#overview", "course": "A", "text": "visualization"},
    {"id": "B#overview", "course": "B", "text": "security"},
    {"id": "program#rules", "course": None, "text": "34 credits"},
]
MATRIX = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])


class TestSemanticSearch:
    def test_no_code_uses_embedding_and_returns_closest_chunks(self):
        result = search_catalog("data visualization", embed=lambda text: [0.9, 0.1, 0.0], index=(MATRIX, CHUNKS), k=2)
        assert result["mode"] == "semantic"
        assert [r["id"] for r in result["results"]] == ["A#overview", "B#overview"]
        assert result["results"][0] == {"id": "A#overview", "course": "A", "text": "visualization", "score": 0.9}

    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="empty"):
            search_catalog("   ", embed=_must_not_embed)


def _must_not_embed(text: str) -> list[float]:
    raise AssertionError("exact search must not call the embedding model")
