"""Northeastern kataloğundan MPS Informatics programının derslerini indirip data/catalog.json'a yazar.

Kullanım:
    python -m scripts.scrape_catalog            # data/raw/ içindeki kopyaları kullanır, yoksa indirir
    python -m scripts.scrape_catalog --refresh  # sayfaları siteden yeniden indirir

Bu adım (Faz 1.1) sadece ders bilgilerini çıkarıyor. Ön koşulu yapıya çevirmek 1.2'nin,
mezuniyet kuralları 1.3'ün işi.
"""

import argparse
import json
import logging
import re
import time
from datetime import date
from pathlib import Path
from typing import Callable

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://catalog.northeastern.edu"
PROGRAM_URL = f"{BASE_URL}/graduate/professional-studies/masters-degree-programs/informatics-mps/"
CATALOG_YEAR = "2026-2027"
USER_AGENT = "course-advisor-learning-project (student)"
REQUEST_TIMEOUT_SECONDS = 30
DELAY_BETWEEN_REQUESTS_SECONDS = 1.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = PROJECT_ROOT / "data" / "catalog.json"

COURSE_CODE_RE = re.compile(r"^[A-Z]{2,5} \d{4}$")
# Metnin içindeki kodlar. Artık var olmayan derslerin (ITC 6300 gibi) linki yok, bu yüzden metinden okuyoruz.
CODE_IN_TEXT_RE = re.compile(r"\b[A-Z]{2,5} \d{4}\b")
TITLE_RE = re.compile(r"^([A-Z]{2,5} \d{4})\.\s+(.+?)\.\s+\((\S+) Hours?\)$")
CREDITS_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
PREREQ_LABEL = "Prerequisite(s):"
ATTRIBUTE_LABEL = "Attribute(s):"

Credits = int | dict[str, int]
Course = dict
Fetcher = Callable[[str, Path], str]

log = logging.getLogger("scrape_catalog")


def clean_text(text: str) -> str:
    """Bölünmez boşlukları ve fazla boşlukları tek boşluğa indirir."""
    return " ".join(text.replace("\xa0", " ").split())


def parse_credits(text: str) -> Credits:
    """'3' -> 3, '1-4' -> {'min': 1, 'max': 4}."""
    match = CREDITS_RE.match(text.strip())
    if not match:
        raise ValueError(f"Beklenmeyen kredi formatı: {text!r}")
    low, high = match.groups()
    return int(low) if high is None else {"min": int(low), "max": int(high)}


def extract_program_codes(html: str) -> list[str]:
    """Program sayfasındaki bütün ders kodları (tablolar ve dipnotlar dahil)."""
    soup = BeautifulSoup(html, "html.parser")
    codes = {clean_text(a.get_text()) for a in soup.select("a.bubblelink.code")}
    return sorted(c for c in codes if COURSE_CODE_RE.match(c))


def subjects_of(codes: list[str]) -> list[str]:
    """['ITC 6105', 'PJM 6440'] -> ['ITC', 'PJM']."""
    return sorted({code.split()[0] for code in codes})


def _labeled_extra(block: Tag, label: str) -> Tag | None:
    for extra in block.select("p.courseblockextra"):
        strong = extra.find("strong")
        if strong and clean_text(strong.get_text()) == label:
            return extra
    return None


def _text_after_label(extra: Tag | None, label: str) -> str | None:
    if extra is None:
        return None
    return clean_text(extra.get_text(" ")).removeprefix(label).strip()


def _parse_block(block: Tag, url: str) -> Course:
    title_text = clean_text(block.select_one(".courseblocktitle").get_text())
    match = TITLE_RE.match(title_text)
    if not match:
        raise ValueError(f"Ders başlığı ayrıştırılamadı: {title_text!r}")
    code, title, credits_text = match.groups()

    desc = block.select_one(".cb_desc")
    prereq_text = _text_after_label(_labeled_extra(block, PREREQ_LABEL), PREREQ_LABEL)
    attributes = _text_after_label(_labeled_extra(block, ATTRIBUTE_LABEL), ATTRIBUTE_LABEL)
    prereq_codes = CODE_IN_TEXT_RE.findall(prereq_text) if prereq_text else []

    return {
        "code": code,
        "title": title,
        "credits": parse_credits(credits_text),
        "description": clean_text(desc.get_text()) if desc else "",
        "prereq_text": prereq_text,
        "prereq_codes": list(dict.fromkeys(prereq_codes)),
        "attributes": [a.strip() for a in attributes.split(",")] if attributes else [],
        "url": url,
    }


def parse_course_blocks(html: str, url: str) -> dict[str, Course]:
    """Bir bölümün ders sayfasındaki her dersi {kod: ders} olarak döndürür."""
    soup = BeautifulSoup(html, "html.parser")
    courses = [_parse_block(block, url) for block in soup.select("div.courseblock")]
    return {course["code"]: course for course in courses}


def collect_prereq_codes(courses: dict[str, Course]) -> list[str]:
    """Ön koşullarda adı geçen ama henüz katalogda olmayan dersler."""
    wanted = {code for c in courses.values() for code in c["prereq_codes"]}
    return sorted(wanted - set(courses))


def fetch(url: str, cache_path: Path, refresh: bool = False) -> str:
    """Sayfayı önbellekten okur. Yoksa (ya da refresh istenirse) siteden indirip kaydeder."""
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    log.info("İndiriliyor: %s", url)
    time.sleep(DELAY_BETWEEN_REQUESTS_SECONDS)
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text


def subject_url(subject: str) -> str:
    return f"{BASE_URL}/course-descriptions/{subject.lower()}/"


def load_courses(codes: list[str], fetcher: Fetcher) -> tuple[dict[str, Course], list[str]]:
    """İstenen dersleri bölüm sayfalarından alır. (bulunanlar, bulunamayan kodlar) döndürür."""
    found: dict[str, Course] = {}
    for subject in subjects_of(codes):
        url = subject_url(subject)
        page = parse_course_blocks(fetcher(url, RAW_DIR / f"{subject.lower()}.html"), url)
        found = {**found, **{c: page[c] for c in codes if c in page}}
    missing = sorted(set(codes) - set(found))
    return found, missing


def build_catalog(fetcher: Fetcher) -> dict:
    program_codes = extract_program_codes(fetcher(PROGRAM_URL, RAW_DIR / "program.html"))
    program_courses, missing_program = load_courses(program_codes, fetcher)
    prereq_courses, missing_prereq = load_courses(collect_prereq_codes(program_courses), fetcher)

    courses = {**program_courses, **prereq_courses}
    return {
        "meta": {
            "catalog_year": CATALOG_YEAR,
            "program_url": PROGRAM_URL,
            "scraped_at": date.today().isoformat(),
            "program_course_count": len(program_courses),
            "prereq_only_course_count": len(prereq_courses),
            "missing_program_codes": missing_program,
            "missing_prereq_codes": missing_prereq,
        },
        "courses": dict(sorted(courses.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="sayfaları siteden yeniden indir")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    catalog = build_catalog(lambda url, path: fetch(url, path, refresh=args.refresh))
    OUTPUT_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    meta = catalog["meta"]
    log.info("Programdan %d ders, ön koşullardan %d ders.", meta["program_course_count"], meta["prereq_only_course_count"])
    log.info("Programda olup katalogda bulunamayan: %s", meta["missing_program_codes"] or "yok")
    log.info("Ön koşulda olup katalogda bulunamayan: %s", meta["missing_prereq_codes"] or "yok")
    log.info("Yazıldı: %s", OUTPUT_PATH.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
