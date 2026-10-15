"""check_prereqs.py testleri."""

from scripts.check_prereqs import build_graph, codes_in, find_cycle


def _course(prereq: dict | None) -> dict:
    return {"prereq": prereq}


def _req(code: str) -> dict:
    return {"course": code, "min_grade": "C-", "concurrent": False}


class TestCodesIn:
    def test_empty_prereq_has_no_codes(self):
        assert codes_in(None) == []

    def test_collects_codes_from_nested_and_or(self):
        tree = {"or": [_req("A"), {"and": [_req("B"), _req("C")]}]}
        assert codes_in(tree) == ["A", "B", "C"]


class TestFindCycle:
    def test_returns_none_when_there_is_no_cycle(self):
        courses = {"A": _course(None), "B": _course(_req("A")), "C": _course({"and": [_req("A"), _req("B")]})}
        assert find_cycle(build_graph(courses)) is None

    def test_finds_two_course_cycle(self):
        courses = {"A": _course(_req("B")), "B": _course(_req("A"))}
        cycle = find_cycle(build_graph(courses))
        assert cycle is not None
        assert cycle[0] == cycle[-1]
        assert set(cycle) == {"A", "B"}

    def test_finds_course_that_requires_itself(self):
        assert find_cycle(build_graph({"A": _course(_req("A"))})) == ["A", "A"]

    def test_codes_missing_from_catalog_do_not_break_the_check(self):
        courses = {"A": _course({"or": [_req("OLD 1000"), _req("B")]}), "B": _course(None)}
        assert find_cycle(build_graph(courses)) is None
