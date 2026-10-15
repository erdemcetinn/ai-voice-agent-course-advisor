"""Checks the prerequisites for cycles (phase 1.4).

Usage:
    python -m scripts.check_prereqs

Courses are nodes, prerequisites are edges: "ITC 6680 -> ITC 6610" means "6680 requires 6610".
If there is a cycle (A requires B and B requires A), no student can take those courses
and the planner gets stuck. The script exits with an error code when it finds a cycle.
"""

import json
import logging
import sys
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

Graph = dict[str, list[str]]

log = logging.getLogger(__name__)


def codes_in(node: dict | None) -> list[str]:
    """All course codes in a prerequisite tree, in order and without duplicates."""
    if node is None:
        return []
    if "course" in node:
        return [node["course"]]
    children = node.get("and") or node.get("or") or []
    return list(dict.fromkeys(code for child in children for code in codes_in(child)))


def build_graph(courses: dict) -> Graph:
    """Prerequisite codes for each course. Retired codes missing from the catalog are left out, so they add no edges."""
    return {code: [p for p in codes_in(course["prereq"]) if p in courses] for code, course in courses.items()}


def find_cycle(graph: Graph) -> list[str] | None:
    """Returns the path of a cycle if one exists (e.g. ["A", "B", "A"]), otherwise None."""
    done: set[str] = set()

    def visit(code: str, path: list[str]) -> list[str] | None:
        if code in path:
            return [*path[path.index(code):], code]
        if code in done:
            return None
        for prereq in graph[code]:
            if cycle := visit(prereq, [*path, code]):
                return cycle
        done.add(code)
        return None

    for code in graph:
        if cycle := visit(code, []):
            return cycle
    return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    courses = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["courses"]
    graph = build_graph(courses)
    edge_count = sum(len(prereqs) for prereqs in graph.values())

    cycle = find_cycle(graph)
    if cycle:
        log.error("CYCLE FOUND: %s", " -> ".join(cycle))
        sys.exit(1)
    log.info("OK: %d courses, %d prerequisite edges, no cycles.", len(graph), edge_count)


if __name__ == "__main__":
    main()
