"""Tool definitions the LLM sees, and the dispatcher that runs them (phase 3.1).

The model never sees the Python code, only these definitions. The descriptions decide whether it
picks the right tool, so they say when to use each one and how to phrase the input.

get_transcript has no student_id parameter on purpose: the session supplies it, so the model
cannot ask for another student's record.
"""

from src.tools.catalog_search import search_catalog
from src.tools.planner import plan_next_semester
from src.tools.transcript import get_transcript


def _spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
    schema = {"type": "object", "properties": properties, "required": required}
    return {"name": name, "description": description, "inputSchema": {"json": schema}}


TOOL_SPECS = [
    _spec(
        "get_transcript",
        "Returns the current student's completed courses with grades and credits, plus credits completed, "
        "credits required and GPA (already calculated). Use it whenever the answer depends on what this "
        "student has taken. It always returns the student in this session; it cannot look up anyone else.",
        {},
        [],
    ),
    _spec(
        "search_catalog",
        "Searches the official course catalog of the MPS in Informatics program: course descriptions, "
        "credits, prerequisites, and graduation rules (required courses, concentrations, electives). "
        "If you know a course code, include it (e.g. 'ITC 6680') for an exact lookup. Otherwise write a "
        "short English search phrase (e.g. 'data visualization course'), even if the student wrote in another language.",
        {"query": {"type": "string", "description": "A course code or a short English search phrase."}},
        ["query"],
    ),
    _spec(
        "plan_next_semester",
        "Deterministic rule check for the current student. With course_code: whether they can take that course now, "
        "which prerequisites are missing, and whether it counts toward a remaining graduation requirement. "
        "Without course_code: everything still needed to graduate (courses and credits), the courses they can take "
        "next semester that count, and needed courses still blocked by prerequisites. Use it for every question about "
        "eligibility, remaining requirements, remaining credits, or what to take next.",
        {"course_code": {"type": "string", "description": "Optional course code, e.g. 'ITC 6680'."}},
        [],
    ),
]


def run_tool(name: str, tool_input: dict, student_id: str) -> dict:
    """Runs the requested tool. Any student_id the model sends is ignored; the session's is used."""
    if name == "get_transcript":
        return get_transcript(student_id)
    if name == "search_catalog":
        return search_catalog(tool_input.get("query", ""))
    if name == "plan_next_semester":
        return plan_next_semester(student_id, tool_input.get("course_code"))
    raise ValueError(f"Unknown tool: {name}")
