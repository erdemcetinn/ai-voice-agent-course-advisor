"""Tests for build_index.py and src/embeddings.py. No AWS connection, uses a fake client."""

import io
import json

import pytest

from scripts.build_index import build_chunks
from src.embeddings import DIMENSIONS, embed_text

CATALOG = {
    "program": {
        "name": "MPS in Informatics (Boston)",
        "total_credits": 34,
        "min_gpa": 3.0,
        "required": ["ITC 6105"],
        "options": [
            {"name": "Analytics", "kind": "concentration", "required": ["ALY 6105"],
             "choose": [{"credits": 3, "from": ["ALY 6125", "ALY 6610"]}],
             "restricted_elective_credits": 4, "any_cps_graduate_credits": 0},
        ],
        "restricted_electives": ["ITC 6680"],
        "notes": ["A note."],
    },
    "courses": {
        "ITC 6105": {"code": "ITC 6105", "title": "Foundations of Informatics", "credits": 3,
                     "description": "Introduces information.", "prereq_text": None},
        "ITC 6680": {"code": "ITC 6680", "title": "CISSP Preparation", "credits": 2,
                     "description": "Covers eight domains.", "prereq_text": "ITC 6610 ; ITC 6620"},
    },
}


class TestBuildChunks:
    def setup_method(self):
        self.chunks = build_chunks(CATALOG)
        self.by_id = {chunk["id"]: chunk for chunk in self.chunks}

    def test_every_course_gets_an_overview_chunk(self):
        overview = self.by_id["ITC 6105#overview"]
        assert overview["course"] == "ITC 6105"
        assert overview["text"] == "ITC 6105 Foundations of Informatics (3 credits). Introduces information."

    def test_only_courses_with_prereq_get_a_prereq_chunk(self):
        assert "ITC 6105#prereq" not in self.by_id
        assert self.by_id["ITC 6680#prereq"]["text"] == "ITC 6680 CISSP Preparation prerequisites: ITC 6610 ; ITC 6620"

    def test_program_chunks_cover_rules_required_and_each_option(self):
        assert "34 credits" in self.by_id["program#rules"]["text"]
        assert "ITC 6105" in self.by_id["program#required"]["text"]
        analytics = self.by_id["program#option#Analytics"]["text"]
        assert "ALY 6105" in analytics and "ALY 6125" in analytics and "4 credits of restricted electives" in analytics
        assert "ITC 6680" in self.by_id["program#restricted"]["text"]
        assert self.by_id["program#rules"]["course"] is None

    def test_ids_are_unique(self):
        assert len(self.by_id) == len(self.chunks)


class FakeBedrock:
    def __init__(self, size: int = DIMENSIONS):
        self.size = size
        self.calls = []

    def invoke_model(self, modelId: str, body: str) -> dict:
        self.calls = [*self.calls, (modelId, json.loads(body))]
        return {"body": io.BytesIO(json.dumps({"embedding": [0.0] * self.size}).encode())}


class TestEmbedText:
    def test_sends_titan_v2_request_with_normalize(self):
        client = FakeBedrock()
        assert len(embed_text("hello", client)) == DIMENSIONS
        model_id, body = client.calls[0]
        assert model_id == "amazon.titan-embed-text-v2:0"
        assert body == {"inputText": "hello", "dimensions": DIMENSIONS, "normalize": True}

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="empty"):
            embed_text("  ", FakeBedrock())

    def test_wrong_size_raises(self):
        with pytest.raises(ValueError, match="1024"):
            embed_text("hello", FakeBedrock(size=3))
