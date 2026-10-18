"""Calculator: the plan_next_semester tool (phase 5).

Deterministic rule checks, so the LLM no longer reasons about prerequisites and credits itself:
  1. Can the student take a course? If not, which prerequisites are missing?
  2. Does a course count toward a remaining requirement, or toward nothing?
  3. What is left to graduate, in courses and credits?

Credits remaining come from which requirements are filled, not from "34 minus credits taken":
a course that fills no requirement does not bring the student closer to graduating.
A completed course satisfies a prerequisite; minimum grades are not checked (all grades are passing by design).
"""

from src.data import load_catalog
from src.tools.transcript import load_student

NOT_COUNTING_NOTE = "Eligible, but it does not count toward any remaining graduation requirement."


def is_satisfied(node: dict | None, done: set[str], same_term: set[str]) -> bool:
    """Is a prerequisite tree met? A course taken in the same term only counts when marked concurrent."""
    if node is None:
        return True
    if "course" in node:
        return node["course"] in done or (node["concurrent"] and node["course"] in same_term)
    if "and" in node:
        return all(is_satisfied(child, done, same_term) for child in node["and"])
    return any(is_satisfied(child, done, same_term) for child in node["or"])


def _missing(node: dict | None, done: set[str]) -> str | None:
    """Readable description of the unmet part of a prerequisite tree, or None when it is met."""
    if node is None or is_satisfied(node, done, set()):
        return None
    if "course" in node:
        return node["course"]
    if "and" in node:
        parts = [part for child in node["and"] if (part := _missing(child, done))]
        return " and ".join(parts)
    options = [_missing(child, done) for child in node["or"]]
    return "one of: " + " or ".join(f"({option})" if " and " in option else option for option in options)


def _concurrent_codes(node: dict | None) -> list[str]:
    if node is None:
        return []
    if "course" in node:
        return [node["course"]] if node["concurrent"] else []
    return [code for child in node.get("and") or node.get("or") for code in _concurrent_codes(child)]


def _taken(student: dict) -> list[str]:
    return [entry["course"] for term in student["terms"] for entry in term["courses"]]


def _credits(code: str, courses: dict) -> int:
    """Credits a completed course counts for. A variable-credit course counts at its minimum."""
    credits = courses[code]["credits"]
    return credits["min"] if isinstance(credits, dict) else credits


def _describe(code: str, courses: dict) -> dict:
    return {"course": code, "title": courses[code]["title"], "credits": courses[code]["credits"]}


def _fill(candidates: list[str], needed: int, courses: dict) -> tuple[list[str], int]:
    """Uses completed courses to fill a credit bucket. Returns the courses used and the credits still needed."""
    used: list[str] = []
    for code in candidates:
        if needed <= 0:
            break
        used = [*used, code]
        needed -= _credits(code, courses)
    return used, max(needed, 0)


def _option(program: dict, name: str) -> dict:
    return next(option for option in program["options"] if option["name"] == name)


def remaining_requirements(student: dict, catalog: dict) -> dict:
    courses, program = catalog["courses"], catalog["program"]
    option = _option(program, student["option"])
    taken = _taken(student)
    used = {code for code in taken if code in program["required"] or code in option["required"]}

    choose = []
    for group in option["choose"]:
        group_used, left = _fill([c for c in taken if c in group["from"] and c not in used], group["credits"], courses)
        used = used | set(group_used)
        choose = [*choose, {"credits_remaining": left, "from": group["from"]}]

    restricted_used, restricted_left = _fill(
        [c for c in taken if c in program["restricted_electives"] and c not in used], option["restricted_elective_credits"], courses)
    used = used | set(restricted_used)
    cps_used, cps_left = _fill([c for c in taken if c not in used], option["any_cps_graduate_credits"], courses)
    used = used | set(cps_used)

    core_missing = [_describe(c, courses) for c in program["required"] if c not in taken]
    option_missing = [_describe(c, courses) for c in option["required"] if c not in taken]
    credits_remaining = (sum(c["credits"] for c in core_missing + option_missing)
                         + sum(g["credits_remaining"] for g in choose) + restricted_left + cps_left)
    return {
        "option": option["name"],
        "core_missing": core_missing,
        "option_missing": option_missing,
        "choose": choose,
        "restricted_elective_credits_remaining": restricted_left,
        "any_cps_graduate_credits_remaining": cps_left,
        "credits_remaining": credits_remaining,
        "courses_not_counting": [c for c in taken if c not in used],
    }


def _counts_toward(code: str, remaining: dict, program: dict, option: dict) -> list[str]:
    roles = []
    if code in {c["course"] for c in remaining["core_missing"]}:
        roles = [*roles, "required core course"]
    if code in {c["course"] for c in remaining["option_missing"]}:
        roles = [*roles, f"required for {option['name']}"]
    if any(g["credits_remaining"] > 0 and code in g["from"] for g in remaining["choose"]):
        roles = [*roles, f"choice group in {option['name']}"]
    if remaining["restricted_elective_credits_remaining"] > 0 and code in program["restricted_electives"]:
        roles = [*roles, "restricted elective"]
    if not roles and remaining["any_cps_graduate_credits_remaining"] > 0:
        roles = [*roles, "any CPS graduate-level elective"]
    return roles


def check_course(code: str, student: dict, catalog: dict) -> dict:
    courses, program = catalog["courses"], catalog["program"]
    if code not in courses:
        raise ValueError(f"{code} is not in the catalog")
    done = set(_taken(student))
    if code in done:
        return {**_describe(code, courses), "completed": True}

    prereq = courses[code]["prereq"]
    eligible = is_satisfied(prereq, done, set())
    together = [c for c in _concurrent_codes(prereq) if c not in done]
    remaining = remaining_requirements(student, catalog)
    counts = _counts_toward(code, remaining, program, _option(program, student["option"]))
    result = {
        **_describe(code, courses),
        "completed": False,
        "eligible_now": eligible,
        "missing_prerequisites": _missing(prereq, done),
        "counts_toward": counts,
    }
    if not eligible and together and is_satisfied(prereq, done, set(together)):
        result = {**result, "can_take_together_with": together}
    return {**result, "note": NOT_COUNTING_NOTE} if eligible and not counts else result


def full_plan(student: dict, catalog: dict) -> dict:
    checks = [check_course(code, student, catalog) for code in catalog["courses"]]
    open_checks = [c for c in checks if not c["completed"] and c["counts_toward"]]
    return {
        "remaining": remaining_requirements(student, catalog),
        "eligible_now_and_counting": [
            {k: c[k] for k in ("course", "title", "credits", "counts_toward")} for c in open_checks if c["eligible_now"]],
        "needed_but_blocked": [
            {k: c[k] for k in ("course", "title", "missing_prerequisites")} for c in open_checks if not c["eligible_now"]],
    }


def plan_next_semester(student_id: str, course_code: str | None = None) -> dict:
    """The tool the LLM calls. student_id comes from the session; course_code narrows it to one course."""
    student, catalog = load_student(student_id), load_catalog()
    if course_code:
        return check_course(course_code.strip().upper(), student, catalog)
    return full_plan(student, catalog)
