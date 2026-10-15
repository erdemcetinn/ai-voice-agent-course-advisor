"""Splits the catalog into chunks and creates an embedding for each chunk (phase 2.2).

Usage:
    source env.sh
    python -m scripts.build_index

Output is two files that match row by row:
    data/chunks.json  the texts and which course they belong to (row i)
    data/index.npy    the 1024-number embedding of each text (row i)

Calls Bedrock (Titan). Creates no resources; for a few hundred short texts the cost is under a cent.
"""

import json
import logging
from pathlib import Path

import numpy as np

from src.embeddings import embed_text, make_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog.json"
CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.json"
INDEX_PATH = PROJECT_ROOT / "data" / "index.npy"
PROGRESS_EVERY = 20

log = logging.getLogger(__name__)


def _chunk(chunk_id: str, text: str, course: str | None = None) -> dict:
    return {"id": chunk_id, "course": course, "text": text}


def _credits_text(credits: int | dict) -> str:
    return f"{credits['min']}-{credits['max']}" if isinstance(credits, dict) else str(credits)


def course_chunks(course: dict) -> list[dict]:
    """For one course: an overview chunk, plus a prerequisite chunk if it has one."""
    code, title = course["code"], course["title"]
    overview = _chunk(
        f"{code}#overview",
        f"{code} {title} ({_credits_text(course['credits'])} credits). {course['description']}".strip(),
        code,
    )
    if not course["prereq_text"]:
        return [overview]
    return [overview, _chunk(f"{code}#prereq", f"{code} {title} prerequisites: {course['prereq_text']}", code)]


def _option_text(option: dict, program_name: str) -> str:
    parts = [f"{program_name}, {option['name']} ({option['kind']}).", f"Required: {', '.join(option['required']) or 'none'}."]
    parts += [f"Choose {group['credits']} credits from: {', '.join(group['from'])}." for group in option["choose"]]
    if option["any_cps_graduate_credits"]:
        parts.append(f"{option['any_cps_graduate_credits']} credits of any CPS graduate-level courses.")
    if option["restricted_elective_credits"]:
        parts.append(f"{option['restricted_elective_credits']} credits of restricted electives.")
    return " ".join(parts)


def program_chunks(program: dict) -> list[dict]:
    """Graduation rules: general requirements, required courses, each option, restricted electives."""
    name = program["name"]
    rules = (
        f"{name} graduation requirements: {program['total_credits']} credits total, minimum GPA {program['min_gpa']:.1f}. "
        f"Students complete the required courses plus one concentration or the electives option. "
        + " ".join(program["notes"])
    )
    return [
        _chunk("program#rules", rules),
        _chunk("program#required", f"{name} required courses for every student: {', '.join(program['required'])}."),
        *[_chunk(f"program#option#{option['name']}", _option_text(option, name)) for option in program["options"]],
        _chunk("program#restricted", f"{name} restricted electives: {', '.join(program['restricted_electives'])}."),
    ]


def build_chunks(catalog: dict) -> list[dict]:
    return [
        *program_chunks(catalog["program"]),
        *[chunk for course in catalog["courses"].values() for chunk in course_chunks(course)],
    ]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    chunks = build_chunks(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    log.info("%d chunks ready, creating embeddings...", len(chunks))

    client = make_client()
    vectors = []
    for number, chunk in enumerate(chunks, start=1):
        vectors = [*vectors, embed_text(chunk["text"], client)]
        if number % PROGRESS_EVERY == 0:
            log.info("  %d / %d", number, len(chunks))

    np.save(INDEX_PATH, np.array(vectors, dtype=np.float32))
    CHUNKS_PATH.write_text(json.dumps(chunks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("Wrote: %s (%d x %d) and %s", INDEX_PATH.name, len(vectors), len(vectors[0]), CHUNKS_PATH.name)


if __name__ == "__main__":
    main()
