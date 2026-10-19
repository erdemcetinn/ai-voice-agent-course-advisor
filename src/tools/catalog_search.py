"""Librarian: the search_catalog tool.

Two paths:
  1. The query contains a course code ("ITC 6680"): exact lookup in catalog.json, no embedding.
     An exact match is always more reliable than semantic search.
  2. No code ("data visualization"): embed the query and return the closest chunks from the index.

Embeddings are normalized, so cosine similarity is a plain dot product (see src/embeddings.py).
"""

import re
from typing import Callable

import numpy as np

from src.data import load_catalog, load_index
from src.embeddings import embed_text, make_client

DEFAULT_TOP_K = 5
SCORE_DECIMALS = 3
# Accepts "ITC 6680", "itc6680" and "ITC-6680".
CODE_RE = re.compile(r"\b([A-Za-z]{2,5})[\s-]?(\d{4})\b")

Embedder = Callable[[str], list[float]]
Index = tuple[np.ndarray, list[dict]]


def _known_subjects() -> set[str]:
    return {code.split()[0] for code in load_catalog()["courses"]}


def find_codes(query: str) -> list[str]:
    """Course codes in the query, normalized to "ITC 6680". Only catalog subjects count, so "fall 2026" is ignored."""
    subjects = _known_subjects()
    codes = [f"{subject.upper()} {number}" for subject, number in CODE_RE.findall(query) if subject.upper() in subjects]
    return list(dict.fromkeys(codes))


def top_k(matrix: np.ndarray, query_vector: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Row numbers of the k most similar rows, best first, with their scores."""
    scores = matrix @ query_vector
    best = np.argsort(-scores)[:k]
    return [(int(row), float(scores[row])) for row in best]


def program_roles(code: str) -> list[str]:
    """Where the course counts in the program: required, concentration, choice group, restricted elective."""
    program = load_catalog()["program"]
    roles = ["required for every student"] if code in program["required"] else []
    for option in program["options"]:
        if code in option["required"]:
            roles = [*roles, f"required in {option['name']}"]
        if any(code in group["from"] for group in option["choose"]):
            roles = [*roles, f"one of the choices in {option['name']}"]
    if code in program["restricted_electives"]:
        roles = [*roles, "restricted elective"]
    return roles


def _course_details(code: str) -> dict:
    course = load_catalog()["courses"][code]
    return {
        "course": code,
        "title": course["title"],
        "credits": course["credits"],
        "description": course["description"],
        "prerequisites": course["prereq_text"] or "none",
        "program_roles": program_roles(code),
    }


def _exact_search(query: str, codes: list[str]) -> dict:
    courses = load_catalog()["courses"]
    return {
        "query": query,
        "mode": "exact",
        "results": [_course_details(code) for code in codes if code in courses],
        "not_found": [code for code in codes if code not in courses],
    }


def _semantic_search(query: str, embed: Embedder, index: Index, k: int) -> dict:
    matrix, chunks = index
    hits = top_k(matrix, np.array(embed(query)), k)
    results = [{**chunks[row], "score": round(score, SCORE_DECIMALS)} for row, score in hits]
    return {"query": query, "mode": "semantic", "results": results, "not_found": []}


def _default_embed(text: str) -> list[float]:
    return embed_text(text, make_client())


def search_catalog(query: str, embed: Embedder | None = None, index: Index | None = None, k: int = DEFAULT_TOP_K) -> dict:
    """The tool the LLM calls. embed and index are injectable for tests."""
    if not query.strip():
        raise ValueError("Search query is empty")
    codes = find_codes(query)
    if codes:
        return _exact_search(query, codes)
    return _semantic_search(query, embed or _default_embed, index or load_index(), k)
