"""Ön koşullarda döngü var mı kontrol eder (Faz 1.4).

Kullanım:
    python -m scripts.check_prereqs

Dersler düğüm, ön koşullar ok: "ITC 6680 -> ITC 6610" demek "6680 için 6610 gerekli".
Döngü varsa (A, B'yi istiyor, B de A'yı istiyor) hiçbir öğrenci bu dersleri alamaz
ve planlayıcı takılır. Döngü bulunursa betik hata koduyla çıkar.
"""

import json
import logging
import sys
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

Graph = dict[str, list[str]]

log = logging.getLogger(__name__)


def codes_in(node: dict | None) -> list[str]:
    """Ön koşul ağacındaki bütün ders kodları, sırayla ve tekrarsız."""
    if node is None:
        return []
    if "course" in node:
        return [node["course"]]
    children = node.get("and") or node.get("or") or []
    return list(dict.fromkeys(code for child in children for code in codes_in(child)))


def build_graph(courses: dict) -> Graph:
    """Her ders için ön koşul kodları. Katalogda olmayan eski kodlar dışarıda kalır, onlardan ok çıkmaz."""
    return {code: [p for p in codes_in(course["prereq"]) if p in courses] for code, course in courses.items()}


def find_cycle(graph: Graph) -> list[str] | None:
    """Bir döngü bulursa yolunu döndürür (ör. ["A", "B", "A"]), yoksa None."""
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
        log.error("DÖNGÜ VAR: %s", " -> ".join(cycle))
        sys.exit(1)
    log.info("OK: %d ders, %d ön koşul oku, döngü yok.", len(graph), edge_count)


if __name__ == "__main__":
    main()
