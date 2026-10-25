"""Match the supplied parallel paper's typography without changing RF content."""
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
from lxml import etree as E
from update_paper_diagnosis import ROOT, NS, q, txt, digest

SOURCE = ROOT/'submission/ACK2026_2026-09-07_evidence/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
REFERENCE = ROOT.parent/'졸업논문/outputs/paper/ACK2026_3GPP_normative_fidelity_draft_v3.docx'
OUTPUT = ROOT/'submission/ACK2026_2026-09-07_fonts/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
QA = ROOT/'build/paper_font_alignment'
SERIF, SANS = 'AppleMyungjo', 'NanumGothic'
SANS_STYLES = {'Style15', 'Style16', 'Style17', 'Style18', 'Style22'}
SIZES = {'Normal':20, 'Style15':32, 'Style16':20, 'Style17':32,
         'Style18':20, 'Style19':18, 'Style20':20, 'Style21':18,
         'Style22':20, 'Style23':16}

def child(parent, name):
    node = parent.find('w:'+name, NS)
    if node is None:
        node = E.SubElement(parent, q(name))
    return node

def typography(rpr, font, size=None, bold=None):
    fonts = child(rpr, 'rFonts')
    for key in list(fonts.attrib):
        if E.QName(key).localname.endswith('Theme'):
            del fonts.attrib[key]
    for name in ('ascii', 'hAnsi', 'eastAsia'):
        fonts.set(q(name), font)
    if size is not None:
        for name in ('sz', 'szCs'):
            child(rpr, name).set(q('val'), str(size))
    if bold is not None:
        for name in ('b', 'bCs'):
            child(rpr, name).set(q('val'), '1' if bold else '0')

def without_typography(root):
    root = deepcopy(root)
    # Normalize the single intentional Korean title line break for comparison.
    for p in root.findall('.//w:p', NS):
        sid = p.find('w:pPr/w:pStyle', NS)
        if sid is not None and sid.get(q('val')) == 'Style15':
            for run in p.findall('w:r', NS):
                text_nodes = run.findall('w:t', NS)
                value = ''.join(n.text or '' for n in text_nodes)
                for node in run.findall('w:br', NS) + text_nodes[1:]:
                    run.remove(node)
                if text_nodes:
                    text_nodes[0].text = value
    for node in root.xpath('//w:rFonts | //w:sz | //w:szCs | //w:b | //w:bCs', namespaces=NS):
        node.getparent().remove(node)
    for node in root.xpath('//w:rPr[not(*) and not(@*)]', namespaces=NS):
        node.getparent().remove(node)
    return E.tostring(root, method='c14n')

def main():
    source_hash, reference_hash = digest(SOURCE), digest(REFERENCE)
    assert source_hash == '36e26889b77ffb3864552291b7669771043bc44518cc54df87e97cb878d9e7b7'
    with ZipFile(SOURCE) as z:
        parts = {n:z.read(n) for n in z.namelist()}
    original = dict(parts)
    root = E.fromstring(parts['word/document.xml'])
    styles = E.fromstring(parts['word/styles.xml'])
    for style in styles.findall('w:style', NS):
        sid = style.get(q('styleId'))
        if sid in SIZES:
            typography(child(style, 'rPr'), SANS if sid in SANS_STYLES else SERIF, SIZES[sid])
    defaults = styles.find('w:docDefaults/w:rPrDefault/w:rPr', NS)
    if defaults is not None:
        typography(defaults, SERIF)
    role_counts = {}
    for p in root.findall('.//w:p', NS):
        style = p.find('w:pPr/w:pStyle', NS)
        sid = style.get(q('val')) if style is not None else 'Normal'
        if sid not in SIZES:
            continue
        text = txt(p)
        font, size, bold = SANS if sid in SANS_STYLES else SERIF, SIZES[sid], None
        if sid == 'Style16':
            size, bold = (18 if '@' in text else 20), False
        elif sid == 'Style18':
            bold = False
        elif sid in {'Style15', 'Style17', 'Style21', 'Style22'}:
            bold = True
        elif sid == 'Style19':
            size = 16 if text.startswith('키워드:') else 20 if text.replace(' ', '') == '요약' else 18
        elif sid == 'Style23':
            size, bold = (18, True) if text == '참고문헌' else (16, False)
        elif sid == 'Normal' and p.xpath('ancestor::w:tc', namespaces=NS):
            size = 14
        role_counts[sid] = role_counts.get(sid, 0) + 1
        paragraph_rpr = p.find('w:pPr/w:rPr', NS)
        if paragraph_rpr is not None:
            typography(paragraph_rpr, font, size, bold)
        for run in p.findall('.//w:r', NS):
            if run.find('w:t', NS) is not None:
                rpr = run.find('w:rPr', NS)
                if rpr is None:
                    rpr = E.Element(q('rPr')); run.insert(0, rpr)
                typography(rpr, font, size, bold)
    title = root.xpath('//w:p[w:pPr/w:pStyle/@w:val="Style15"]', namespaces=NS)[0]
    title_text = title.find('.//w:t', NS)
    first, second = title_text.text.split('복구와', 1)
    title_text.text = first
    after = E.Element(q('t')); after.text = '복구와' + second
    for key, value in title_text.attrib.items():
        after.set(key, value)
    title_text.addnext(after)
    title_text.addnext(E.Element(q('br')))
    for name, tree in [('word/document.xml',root), ('word/styles.xml',styles)]:
        assert without_typography(E.fromstring(original[name])) == without_typography(tree), name
        parts[name] = E.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    assert digest(SOURCE) == source_hash and digest(REFERENCE) == reference_hash
    changed = [n for n in parts if parts[n] != original[n]]
    assert changed == ['word/document.xml', 'word/styles.xml'] or set(changed) == {'word/document.xml', 'word/styles.xml'}
    report = dict(source=str(SOURCE), source_sha256=source_hash,
        reference=str(REFERENCE), reference_sha256=reference_hash,
        output=str(OUTPUT), output_sha256=digest(OUTPUT), changed_parts=changed,
        role_counts=role_counts, fonts=dict(title_heading=SANS, body=SERIF),
        font_sizes_pt=dict(title=16, author_affiliation=10, email=9, abstract=9,
            keywords=8, body=10, heading=10, caption=9, table=7, reference=8),
        non_typographic_xml_unchanged_except_title_line_break=True,
        title_line_break_before='복구와', other_package_parts_byte_identical=True)
    QA.mkdir(parents=True, exist_ok=True)
    (QA/'changes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
