"""parse_prereqs.py testleri. Metinler data/catalog.json'daki gerçek ön koşullardan alındı."""

import pytest

from scripts.parse_prereqs import parse_prereq

GRADE = "with a minimum grade of C-"


def course(code: str, concurrent: bool = False) -> dict:
    return {"course": code, "min_grade": "C-", "concurrent": concurrent}


def test_empty_prereq_returns_none():
    assert parse_prereq(None) is None
    assert parse_prereq("") is None


def test_single_course():
    assert parse_prereq(f"ITC 6610 {GRADE}") == course("ITC 6610")


def test_and_itc_6680():
    text = f"ITC 6610 {GRADE} ; ITC 6620 {GRADE}"
    assert parse_prereq(text) == {"and": [course("ITC 6610"), course("ITC 6620")]}


def test_or_with_three_courses_itc_6721():
    text = f"AAI 6600 {GRADE} or ALY 6420 {GRADE} or ITC 6150 {GRADE}"
    assert parse_prereq(text) == {
        "or": [course("AAI 6600"), course("ALY 6420"), course("ITC 6150")]
    }


def test_concurrent_flag_aly_6115():
    text = f"ALY 6105 (may be taken concurrently) {GRADE} or ALY 6000 {GRADE}"
    assert parse_prereq(text) == {
        "or": [course("ALY 6105", concurrent=True), course("ALY 6000")]
    }


def test_and_inside_parentheses_or_outside_aly_6145():
    text = f"ALY 6115 {GRADE} or (ALY 6000 {GRADE} ; ALY 6010 {GRADE} )"
    assert parse_prereq(text) == {
        "or": [course("ALY 6115"), {"and": [course("ALY 6000"), course("ALY 6010")]}]
    }


def test_two_big_groups_itc_6980():
    new = ["ITC 6105", "ITC 6150", "ITC 6205", "ITC 6250", "PJM 6440"]
    old = ["INT 6940", "ITC 6000", "ITC 6010", "ITC 6020", "ITC 6035", "ITC 6400"]
    text = (
        "( " + " ; ".join(f"{c} {GRADE}" for c in new) + " ) or ( "
        + " ; ".join(f"{c} {GRADE}" for c in old) + " )"
    )
    assert parse_prereq(text) == {
        "or": [{"and": [course(c) for c in new]}, {"and": [course(c) for c in old]}]
    }


def test_mixed_without_parentheses_dgm_6600():
    # VARSAYIM: Katalog parantez koymamış. ";" (ve) en gevşek bağ kabul ediliyor, yani
    # "A ; B or C or D" = A ve (B veya C veya D). Diğer okunuş "(A ve B) veya C veya D" olurdu.
    text = (
        f"DGM 5050 {GRADE} ; DGM 5060 {GRADE} or "
        f"DGM 6168 (may be taken concurrently) {GRADE} or "
        f"TCC 6120 (may be taken concurrently) {GRADE}"
    )
    assert parse_prereq(text) == {
        "and": [
            course("DGM 5050"),
            {"or": [
                course("DGM 5060"),
                course("DGM 6168", concurrent=True),
                course("TCC 6120", concurrent=True),
            ]},
        ]
    }


def test_unknown_word_raises_clear_error():
    with pytest.raises(ValueError, match="instructor"):
        parse_prereq(f"ITC 6610 {GRADE} or permission of instructor")


def test_unbalanced_parentheses_raise_error():
    with pytest.raises(ValueError, match="parantez"):
        parse_prereq(f"( ITC 6610 {GRADE} ; ITC 6620 {GRADE}")
