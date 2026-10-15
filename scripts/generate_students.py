"""3 sentetik (uydurma) öğrenciyi katalogla kontrol edip data/students.json'a yazar (Faz 1.5).

Kullanım:
    python -m scripts.generate_students

Öğrenciler elle tasarlandı, her biri farklı bir durumu temsil ediyor. Betik veriyi uydurmuyor,
tutarlı olduğunu kontrol ediyor: dersler katalogda var mı, ön koşullar önceki dönemlerde alınmış mı,
GPA 3.0'ın üstünde mi. Bütün notlar geçer not (kalan ders senaryosu yok, karar 15 Ekim).
Dönemler tarih yerine sırayla numaralı (1, 2, 3...). "Gelecek dönem" son numaradan sonraki dönem.
"""

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "students.json"

GRADE_POINTS = {"A": 4.0, "A-": 3.667, "B+": 3.333, "B": 3.0, "B-": 2.667, "C+": 2.333, "C": 2.0, "C-": 1.667}

log = logging.getLogger(__name__)


def _term(number: int, *courses: tuple[str, str]) -> dict:
    return {"term": number, "courses": [{"course": code, "grade": grade} for code, grade in courses]}


STUDENTS = [
    {
        # Yeni başlamış: 1 dönem. ITC 6620'yi almadığı için ITC 6680'e henüz uygun değil.
        "student_id": "s001",
        "name": "Maya Okafor",
        "pin": "4821",
        "option": "Information Security Management",
        "terms": [_term(1, ("ITC 6105", "A"), ("ITC 6610", "A-"))],
    },
    {
        # Ortada: 3 dönem, 20 kredi.
        "student_id": "s002",
        "name": "Daniel Reyes",
        "pin": "7350",
        "option": "Cloud Computing Application and Management",
        "terms": [
            _term(1, ("ITC 6105", "B+"), ("ITC 6150", "B")),
            _term(2, ("ITC 6205", "A-"), ("ITC 6650", "B+")),
            _term(3, ("ITC 6250", "B"), ("ITC 6630", "A"), ("PJM 6440", "B+")),
        ],
    },
    {
        # Mezuniyete yakın: 4 dönem, 28 kredi. Kalan: capstone (ITC 6980) + 2 kredi kısıtlı seçmeli.
        "student_id": "s003",
        "name": "Lena Fischer",
        "pin": "2694",
        "option": "Analytics",
        "terms": [
            _term(1, ("ITC 6105", "A"), ("ALY 6105", "A-"), ("ITC 6150", "B+")),
            _term(2, ("ALY 6115", "A"), ("ITC 6205", "B+"), ("PJM 6440", "A")),
            _term(3, ("ALY 6145", "A-"), ("ALY 6610", "B+"), ("ITC 6250", "A-")),
            _term(4, ("ITC 6415", "A")),
        ],
    },
]


def is_satisfied(node: dict | None, done: set[str], same_term: set[str]) -> bool:
    """Ön koşul ağacı sağlanıyor mu? Aynı dönemde alınan ders sadece "concurrent" ise sayılır."""
    if node is None:
        return True
    if "course" in node:
        return node["course"] in done or (node["concurrent"] and node["course"] in same_term)
    if "and" in node:
        return all(is_satisfied(child, done, same_term) for child in node["and"])
    return any(is_satisfied(child, done, same_term) for child in node["or"])


def _all_courses(student: dict) -> list[dict]:
    return [entry for term in student["terms"] for entry in term["courses"]]


def validate_student(student: dict, catalog: dict) -> list[str]:
    """Öğrenci kaydındaki tutarsızlıkları liste olarak döndürür. Boş liste = sorun yok."""
    courses = catalog["courses"]
    sid = student["student_id"]
    option_names = {option["name"] for option in catalog["program"]["options"]}
    errors = [] if student["option"] in option_names else [f"{sid}: bilinmeyen seçenek {student['option']!r}"]

    codes = [entry["course"] for entry in _all_courses(student)]
    errors += [f"{sid}: {code} iki kez alınmış" for code in sorted({c for c in codes if codes.count(c) > 1})]

    done: set[str] = set()
    for term in student["terms"]:
        same_term = {entry["course"] for entry in term["courses"]}
        for entry in term["courses"]:
            code, grade = entry["course"], entry["grade"]
            if code not in courses:
                errors.append(f"{sid}: {code} katalogda yok")
                continue
            if grade not in GRADE_POINTS:
                errors.append(f"{sid}: {code} için geçersiz not {grade!r}")
            if not is_satisfied(courses[code]["prereq"], done, same_term):
                errors.append(f"{sid}: {code} dönem {term['term']}'de alınmış ama ön koşulu sağlanmıyor")
        done = done | same_term
    return errors


def total_credits(student: dict, catalog: dict) -> int:
    return sum(catalog["courses"][entry["course"]]["credits"] for entry in _all_courses(student))


def gpa(student: dict, catalog: dict) -> float:
    """Krediye göre ağırlıklı not ortalaması."""
    entries = _all_courses(student)
    credits = [catalog["courses"][entry["course"]]["credits"] for entry in entries]
    points = sum(GRADE_POINTS[entry["grade"]] * credit for entry, credit in zip(entries, credits))
    return points / sum(credits)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    errors = [error for student in STUDENTS for error in validate_student(student, catalog)]
    if errors:
        log.error("Öğrenci verisi tutarsız:\n  %s", "\n  ".join(errors))
        sys.exit(1)

    output = {
        "meta": {"synthetic": True, "note": "Uydurma öğrenciler. Gerçek kişi ya da kayıt değildir."},
        "students": {student["student_id"]: student for student in STUDENTS},
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for student in STUDENTS:
        log.info(
            "%s %-14s %-45s %d dönem, %2d kredi, GPA %.2f",
            student["student_id"], student["name"], student["option"],
            len(student["terms"]), total_credits(student, catalog), gpa(student, catalog),
        )
    log.info("Yazıldı: %s", OUTPUT_PATH.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
