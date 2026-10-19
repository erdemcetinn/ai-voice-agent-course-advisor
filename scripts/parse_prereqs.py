"""Turns catalog prerequisite text into a tree the planner can read.

Example:
    "ITC 6610 with a minimum grade of C- ; ITC 6620 with a minimum grade of C-"
    -> {"and": [{"course": "ITC 6610", "min_grade": "C-", "concurrent": False},
                {"course": "ITC 6620", "min_grade": "C-", "concurrent": False}]}

Grammar (derived from the 19 prerequisite texts in the catalog):
    ";"  = and     "or" = or        "( )" = group
    "(may be taken concurrently)" = the course may also be taken in the same term

Precedence: ";" binds loosest. "A ; B or C" = A and (B or C).
This is an assumption, because the catalog uses a mixed expression without parentheses only in DGM 6600.
"""

import re
from typing import NamedTuple

Node = dict

COURSE_RE = re.compile(
    r"(?P<code>[A-Z]{2,5} \d{4})"
    r"(?P<concurrent>\s*\(may be taken concurrently\))?"
    r"\s+with a minimum grade of (?P<grade>[A-F][+-]?)"
)
AND_RE = re.compile(r";")
OR_RE = re.compile(r"or\b")
LPAREN_RE = re.compile(r"\(")
RPAREN_RE = re.compile(r"\)")
SPACE_RE = re.compile(r"\s+")


class Token(NamedTuple):
    kind: str  # "COURSE", "AND", "OR", "LPAREN", "RPAREN"
    course: Node | None = None


def tokenize(text: str) -> list[Token]:
    """Splits the text into tokens. Stops on anything it does not recognize and says where."""
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        if m := SPACE_RE.match(text, pos):
            pos = m.end()
        elif m := COURSE_RE.match(text, pos):
            course = {
                "course": m["code"],
                "min_grade": m["grade"],
                "concurrent": m["concurrent"] is not None,
            }
            tokens.append(Token("COURSE", course))
            pos = m.end()
        elif m := AND_RE.match(text, pos):
            tokens.append(Token("AND"))
            pos = m.end()
        elif m := OR_RE.match(text, pos):
            tokens.append(Token("OR"))
            pos = m.end()
        elif m := LPAREN_RE.match(text, pos):
            tokens.append(Token("LPAREN"))
            pos = m.end()
        elif m := RPAREN_RE.match(text, pos):
            tokens.append(Token("RPAREN"))
            pos = m.end()
        else:
            raise ValueError(f"Unrecognized text: {text[pos:]!r} (full text: {text!r})")
    return tokens


def _group(kind: str, children: list[Node]) -> Node:
    """Unwraps single-child groups: just A instead of and(A)."""
    return children[0] if len(children) == 1 else {kind: children}


def _parse_and(tokens: list[Token], pos: int) -> tuple[Node, int]:
    """and_expr := or_expr (';' or_expr)*"""
    first, pos = _parse_or(tokens, pos)
    children = [first]
    while pos < len(tokens) and tokens[pos].kind == "AND":
        child, pos = _parse_or(tokens, pos + 1)
        children.append(child)
    return _group("and", children), pos


def _parse_or(tokens: list[Token], pos: int) -> tuple[Node, int]:
    """or_expr := atom ('or' atom)*"""
    first, pos = _parse_atom(tokens, pos)
    children = [first]
    while pos < len(tokens) and tokens[pos].kind == "OR":
        child, pos = _parse_atom(tokens, pos + 1)
        children.append(child)
    return _group("or", children), pos


def _parse_atom(tokens: list[Token], pos: int) -> tuple[Node, int]:
    """atom := COURSE | '(' and_expr ')'"""
    if pos >= len(tokens):
        raise ValueError("Prerequisite ended unexpectedly (missing course or unclosed parenthesis)")
    token = tokens[pos]
    if token.kind == "COURSE":
        return token.course, pos + 1
    if token.kind == "LPAREN":
        node, pos = _parse_and(tokens, pos + 1)
        if pos >= len(tokens) or tokens[pos].kind != "RPAREN":
            raise ValueError("Unclosed parenthesis")
        return node, pos + 1
    raise ValueError(f"Expected a course or '(' but got {token.kind}")


def parse_prereq(text: str | None) -> Node | None:
    """Turns prerequisite text into a tree. Returns None when there is no prerequisite."""
    if not text:
        return None
    tokens = tokenize(text)
    node, pos = _parse_and(tokens, 0)
    if pos != len(tokens):
        raise ValueError(f"Extra closing parenthesis or unexpected {tokens[pos].kind}")
    return node
