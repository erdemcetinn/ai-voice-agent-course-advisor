"""Katalogdaki ön koşul metnini planlayıcının okuyabileceği bir ağaca çevirir (Faz 1.2).

Örnek:
    "ITC 6610 with a minimum grade of C- ; ITC 6620 with a minimum grade of C-"
    -> {"and": [{"course": "ITC 6610", "min_grade": "C-", "concurrent": False},
                {"course": "ITC 6620", "min_grade": "C-", "concurrent": False}]}

Dil kuralları (katalogdaki 19 ön koşul metninden çıkarıldı):
    ";"  = ve      "or" = veya      "( )" = grup
    "(may be taken concurrently)" = ders aynı dönemde de alınabilir

Öncelik: ";" en gevşek bağ. "A ; B or C" = A ve (B veya C).
Bu bir varsayım, çünkü katalog parantezsiz karışık ifadeyi sadece DGM 6600'de kullanıyor.
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
    """Metni parçalara ayırır. Tanımadığı bir şey görürse durur ve nerede olduğunu söyler."""
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
            raise ValueError(f"Tanınmayan ifade: {text[pos:]!r} (tam metin: {text!r})")
    return tokens


def _group(kind: str, children: list[Node]) -> Node:
    """Tek elemanlı grupları açar: and(A) yerine sadece A."""
    return children[0] if len(children) == 1 else {kind: children}


def _parse_and(tokens: list[Token], pos: int) -> tuple[Node, int]:
    """and_ifadesi := or_ifadesi (';' or_ifadesi)*"""
    first, pos = _parse_or(tokens, pos)
    children = [first]
    while pos < len(tokens) and tokens[pos].kind == "AND":
        child, pos = _parse_or(tokens, pos + 1)
        children.append(child)
    return _group("and", children), pos


def _parse_or(tokens: list[Token], pos: int) -> tuple[Node, int]:
    """or_ifadesi := parça ('or' parça)*"""
    first, pos = _parse_atom(tokens, pos)
    children = [first]
    while pos < len(tokens) and tokens[pos].kind == "OR":
        child, pos = _parse_atom(tokens, pos + 1)
        children.append(child)
    return _group("or", children), pos


def _parse_atom(tokens: list[Token], pos: int) -> tuple[Node, int]:
    """parça := DERS | '(' and_ifadesi ')'"""
    if pos >= len(tokens):
        raise ValueError("Ön koşul beklenmedik yerde bitti (eksik ders ya da kapanmamış parantez)")
    token = tokens[pos]
    if token.kind == "COURSE":
        return token.course, pos + 1
    if token.kind == "LPAREN":
        node, pos = _parse_and(tokens, pos + 1)
        if pos >= len(tokens) or tokens[pos].kind != "RPAREN":
            raise ValueError("Kapanmamış parantez")
        return node, pos + 1
    raise ValueError(f"Ders ya da '(' beklenirken {token.kind} geldi")


def parse_prereq(text: str | None) -> Node | None:
    """Ön koşul metnini ağaca çevirir. Ön koşul yoksa None döndürür."""
    if not text:
        return None
    tokens = tokenize(text)
    node, pos = _parse_and(tokens, 0)
    if pos != len(tokens):
        raise ValueError(f"Fazladan kapanan parantez ya da beklenmeyen {tokens[pos].kind}")
    return node
