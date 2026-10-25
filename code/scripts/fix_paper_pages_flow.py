"""Remove the ambiguous next-page section flag without changing paper content."""
import json
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from update_paper_diagnosis import ROOT, NS, q, digest

SOURCE = ROOT/'submission/ACK2026_2026-09-07_fonts/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
OUTPUT = ROOT/'submission/ACK2026_2026-09-07_pages/ACK2026_KimTaehoon_RF_Circuit_Repair_Pages.docx'
QA = ROOT/'build/paper_pages_flow'

def main():
    before = digest(SOURCE)
    assert before == '70ed75b6d207bee94aa647c0b83d9a8b5b56e3ec703695cbac92ce15ea911fa7'
    with ZipFile(SOURCE) as z:
        parts = {n:z.read(n) for n in z.namelist()}
    root = E.fromstring(parts['word/document.xml'])
    sections = root.findall('.//w:sectPr', NS)
    assert len(sections) == 2
    first_type = sections[0].find('w:type', NS)
    assert first_type.get(q('val')) == 'nextPage'
    first_type.set(q('val'), 'continuous')
    parts['word/document.xml'] = E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    assert digest(SOURCE) == before
    QA.mkdir(parents=True, exist_ok=True)
    report = dict(source=str(SOURCE),source_sha256=before,output=str(OUTPUT),
        output_sha256=digest(OUTPUT),change='first section type nextPage to continuous')
    (QA/'changes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
