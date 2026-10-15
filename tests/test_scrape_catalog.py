"""scrape_catalog.py testleri. HTML parçaları gerçek katalog sayfalarından kısaltılarak alındı."""

import pytest

from scripts.scrape_catalog import (
    collect_prereq_codes,
    extract_program_codes,
    parse_course_blocks,
    parse_credits,
    subjects_of,
)

PROGRAM_HTML = """
<table class="sc_courselist"><tbody>
<tr class="even firstrow"><td class="codecol"><a href="/search/?P=ITC%206105" class="bubblelink code">ITC 6105</a></td><td>Foundations of Informatics</td><td class="hourscol">3</td></tr>
<tr class="odd"><td class="codecol"><a href="/search/?P=PJM%206440" class="bubblelink code">PJM 6440</a></td><td>Leading and Managing Technical Projects</td><td class="hourscol">2</td></tr>
<tr class="orclass odd"><td class="codecol orclass">or <a href="/search/?P=COP%206946" class="bubblelink code">COP&#160;6946</a></td><td colspan="2"> Global Co-op</td></tr>
<tr class="even"><td class="codecol"><div class="blockindent"><a href="/search/?P=ITC%206105" class="bubblelink code">ITC 6105</a></div></td><td>Tekrar eden ders</td><td class="hourscol"></td></tr>
</tbody></table>
<p>Footnote: <a href="/search/?P=PJM%206100" class="bubblelink code">PJM 6100</a> tablo dışında.</p>
"""

COURSES_HTML = """
<div class="courseblock">
<p class="courseblocktitle noindent"><strong>ITC&#160;6105.  Foundations of Informatics.  (3 Hours)</strong></p>
<p class="cb_desc">Introduces the fundamental properties of information.</p>
</div>
<div class="courseblock">
<p class="courseblocktitle noindent"><strong>ITC&#160;6680.  CISSP Preparation.  (2 Hours)</strong></p>
<p class="cb_desc">Covers all eight domains.</p>
<p class="courseblockextra noindent"><strong>Prerequisite(s):</strong> <a href="/search/?P=ITC%206610" class="bubblelink code">ITC&#160;6610</a> with a minimum grade of C- ; <a href="/search/?P=ITC%206620" class="bubblelink code">ITC&#160;6620</a> with a minimum grade of C-</p>
<p class="courseblockextra noindent"><strong>Attribute(s):</strong> NUpath Ethical Reasoning, Graduate Level</p>
</div>
<div class="courseblock">
<p class="courseblocktitle noindent"><strong>ITC&#160;7995.  Project.  (1-4 Hours)</strong></p>
<p class="cb_desc">Offers students a focused project experience.</p>
</div>
"""

URL = "https://catalog.northeastern.edu/course-descriptions/itc/"


class TestParseCredits:
    def test_single_number_returns_int(self):
        assert parse_credits("3") == 3

    def test_zero_credit_course(self):
        assert parse_credits("0") == 0

    def test_range_returns_min_max(self):
        assert parse_credits("1-4") == {"min": 1, "max": 4}

    def test_unexpected_text_raises_clear_error(self):
        with pytest.raises(ValueError, match="kredi"):
            parse_credits("three")


class TestExtractProgramCodes:
    def test_finds_codes_in_tables_including_or_rows(self):
        codes = extract_program_codes(PROGRAM_HTML)
        assert {"ITC 6105", "PJM 6440", "COP 6946"} <= set(codes)

    def test_includes_codes_outside_tables_such_as_footnotes(self):
        assert "PJM 6100" in extract_program_codes(PROGRAM_HTML)

    def test_returns_sorted_unique_codes_with_normal_spaces(self):
        codes = extract_program_codes(PROGRAM_HTML)
        assert codes == sorted(set(codes))
        assert all("\xa0" not in c for c in codes)


class TestSubjectsOf:
    def test_returns_unique_sorted_subject_prefixes(self):
        assert subjects_of(["ITC 6105", "PJM 6440", "ITC 6150"]) == ["ITC", "PJM"]


class TestParseCourseBlocks:
    def setup_method(self):
        self.courses = parse_course_blocks(COURSES_HTML, URL)

    def test_parses_every_block(self):
        assert set(self.courses) == {"ITC 6105", "ITC 6680", "ITC 7995"}

    def test_course_without_prereq(self):
        c = self.courses["ITC 6105"]
        assert c["code"] == "ITC 6105"
        assert c["title"] == "Foundations of Informatics"
        assert c["credits"] == 3
        assert c["description"] == "Introduces the fundamental properties of information."
        assert c["prereq_text"] is None
        assert c["prereq_codes"] == []
        assert c["url"] == URL

    def test_course_with_prereq_keeps_original_text_and_codes(self):
        c = self.courses["ITC 6680"]
        assert c["credits"] == 2
        assert c["prereq_text"] == (
            "ITC 6610 with a minimum grade of C- ; ITC 6620 with a minimum grade of C-"
        )
        assert c["prereq_codes"] == ["ITC 6610", "ITC 6620"]

    def test_unlinked_codes_in_prereq_text_are_collected(self):
        # Katalog artık var olmayan derslere (ITC 6300 gibi) link vermiyor, kod düz metin olarak geçiyor.
        html = """
        <div class="courseblock">
        <p class="courseblocktitle"><strong>ITC&#160;6640.  Security Operations and Analytics.  (3 Hours)</strong></p>
        <p class="courseblockextra"><strong>Prerequisite(s):</strong> ITC 6300 with a minimum grade of C- or <a class="bubblelink code">ITC&#160;6610</a> with a minimum grade of C-</p>
        </div>
        """
        course = parse_course_blocks(html, URL)["ITC 6640"]
        assert course["prereq_codes"] == ["ITC 6300", "ITC 6610"]

    def test_attributes_are_split_into_list(self):
        assert self.courses["ITC 6680"]["attributes"] == [
            "NUpath Ethical Reasoning",
            "Graduate Level",
        ]
        assert self.courses["ITC 6105"]["attributes"] == []

    def test_variable_credit_course(self):
        assert self.courses["ITC 7995"]["credits"] == {"min": 1, "max": 4}

    def test_malformed_title_raises_with_title_in_message(self):
        bad = '<div class="courseblock"><p class="courseblocktitle"><strong>Garip başlık</strong></p></div>'
        with pytest.raises(ValueError, match="Garip başlık"):
            parse_course_blocks(bad, URL)


class TestCollectPrereqCodes:
    def test_returns_prereq_codes_not_already_in_catalog(self):
        courses = parse_course_blocks(COURSES_HTML, URL)
        assert collect_prereq_codes(courses) == ["ITC 6610", "ITC 6620"]
