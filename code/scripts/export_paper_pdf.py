"""Publish the visually checked full manuscript PDF without editing its content."""

from pathlib import Path
import hashlib
import json
import re
import shutil
import zipfile

from lxml import etree
from pypdf import PdfReader
import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "submission/ACK2026_2026-09-07_fonts/ACK2026_KimTaehoon_RF_Circuit_Repair.docx"
RENDER = ROOT / "build/paper_font_alignment/render_final/ACK2026_KimTaehoon_RF_Circuit_Repair.pdf"
OUTPUT = ROOT / "submission/ACK2026_2026-09-07_pdf/ACK2026_KimTaehoon_RF_Circuit_Repair.pdf"
EXPECTED_SOURCE = "70ed75b6d207bee94aa647c0b83d9a8b5b56e3ec703695cbac92ce15ea911fa7"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(text):
    return re.sub(r"\s+", "", text)


def main():
    assert sha(SOURCE) == EXPECTED_SOURCE, "Editable source changed; render it again."
    reader = PdfReader(RENDER)
    texts = [page.extract_text() for page in reader.pages]
    whole = compact("".join(texts))
    # Position-based extraction restores symbols drawn in separate font runs.
    # PDF content-stream order alone can move minus signs after their numbers.
    with pdfplumber.open(RENDER) as positioned:
        columns = []
        for page in positioned.pages:
            for left, right in ((0, page.width / 2), (page.width / 2, page.width)):
                columns.append(page.crop((left, 0, right, page.height)).extract_text(x_tolerance=1, y_tolerance=3) or "")
    positioned_whole = compact("".join(columns))
    assert len(reader.pages) == 3
    assert not reader.is_encrypted
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.3) < 1
        assert abs(float(page.mediabox.height) - 841.89) < 1
    assert "1.서론" in compact(texts[0])
    for number in range(1, 7):
        assert f"<표{number}>" in whole
    assert all(f"[{number}]" in compact(texts[2]) for number in range(1, 8))
    assert "46/48" in whole and "37/48" in whole
    assert "SelectiveClassificationforDeepNeuralNetworks" in whole

    fonts = {}
    for page in reader.pages:
        for reference in page["/Resources"]["/Font"].values():
            font = reference.get_object()
            descendants = font.get("/DescendantFonts")
            child = descendants[0].get_object() if descendants else font
            descriptor = child.get("/FontDescriptor")
            descriptor = descriptor.get_object() if descriptor else {}
            embedded = any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
            unicode_map = "/ToUnicode" in font
            assert embedded and unicode_map, font.get("/BaseFont")
            fonts[str(font.get("/BaseFont"))] = {"embedded": embedded, "to_unicode": unicode_map}
    assert any("NanumGothic" in name for name in fonts)
    assert any("AppleMyungjo" in name for name in fonts)

    with zipfile.ZipFile(SOURCE) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
    # Every text-bearing paragraph must survive, including all table cells.
    # The native equation is checked visually; its text is interleaved by PDF extraction.
    paragraphs = document.xpath("//w:p", namespaces=NS)
    missing = []
    checked = 0
    for paragraph in paragraphs:
        if paragraph.xpath(".//*[local-name()='oMath']"):
            continue
        text = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if not compact(text):
            continue
        checked += 1
        if compact(text) not in whole and compact(text) not in positioned_whole:
            missing.append(text)
    assert not missing, f"Paragraph text missing: {missing}"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RENDER, OUTPUT)
    assert sha(OUTPUT) == sha(RENDER)
    assert sha(SOURCE) == EXPECTED_SOURCE
    report = {
        "source_docx": str(SOURCE), "source_sha256": sha(SOURCE),
        "rendered_pdf": str(RENDER), "output_pdf": str(OUTPUT),
        "pdf_sha256": sha(OUTPUT), "page_count": 3, "page_size": "A4 portrait",
        "source_unchanged": True, "byte_identical_to_inspected_render": True,
        "text_paragraphs_verified": checked, "missing_paragraphs": [],
        "text_verification_method": "Content-stream extraction plus position-based two-column extraction; the latter preserves separate-font minus sign order.",
        "first_page_body": True, "result_tables": 6, "references": 7,
        "fonts": fonts, "encrypted": False,
        "visual_review": "All three render_final PNGs inspected; tables 1-6 remain whole within a column; no clipping or overlap.",
        "pagination_scope": "Fixed PDF is 3 pages. The editable DOCX remains 4 pages when imported by Apple Pages.",
    }
    (OUTPUT.parent / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(OUTPUT), "pages": 3, "verified_paragraphs": checked, "fonts": len(fonts), "sha256": sha(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
