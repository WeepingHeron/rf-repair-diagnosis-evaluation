"""Verify the reframed paper against its source, evidence, template, and final render."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from pypdf import PdfReader
from update_paper_framing import ROOT,SOURCE,OUTPUT,QA,TITLE_KO,TITLE_EN
from update_paper_diagnosis import NS,txt,read,digest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--render-dir',type=Path,required=True)
    args=parser.parse_args();m=read(QA/'changes.json')
    assert digest(SOURCE)==m['source_sha256'] and digest(OUTPUT)==m['output_sha256']
    for p,h in m['evidence_sha256'].items():assert digest(ROOT/p)==h,p
    def parts(path):
        with ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}
    old,new,template=parts(SOURCE),parts(OUTPUT),parts(args.template)
    assert old.keys()==new.keys() and [n for n in new if new[n]!=old[n]]==['word/document.xml']
    a,b,t=[E.fromstring(x['word/document.xml']) for x in [old,new,template]]
    assert new['word/styles.xml']==template['word/styles.xml']
    assert [E.tostring(s) for s in b.findall('.//w:sectPr',NS)]==[E.tostring(s) for s in t.findall('.//w:sectPr',NS)]
    at,bt=[x.find('w:body',NS).findall('w:tbl',NS) for x in [a,b]]
    assert len(at)==len(bt)==6
    assert [E.tostring(x) for x in at[1:]]==[E.tostring(x) for x in bt[1:]]
    ap,bp=[x.findall('.//w:p',NS) for x in [a,b]]
    for i in range(1,6):
        assert [txt(p) for p in ap if txt(p).startswith(f'[{i}]')]==[txt(p) for p in bp if txt(p).startswith(f'[{i}]')]
    assert len([p for p in bp if txt(p).startswith(('[1]','[2]','[3]','[4]','[5]','[6]','[7]'))])==7
    whole=txt(b)
    for phrase in [TITLE_KO,TITLE_EN,'문제 정의 및 평가 절차','현재 부품값과 고정 등가모형을 알고',
            '주입 위치·유형과의 일치','주입 값 변화의 식별','88개는 규격 PASS, 56개는 FAIL',
            '21.1%에서 26.7%로 5.6%p','73.3%는 보류','잔차·간격·비율만으로도',
            '시험한 조건에서','현재 부품값의 불확실성','미래 무오진의 보장이 아니다']:
        assert phrase in whole,phrase
    assert '폐루프 방법을 제안한다' not in whole
    assert '독립 SPICE 검증은 원인 진단과 기능 복구를 구분했다' not in whole
    assert all(f'[{i}]' in ''.join(txt(p) for p in bp if not txt(p).startswith('[')) for i in range(1,8))
    for tag in ['ins','del','commentReference','commentRangeStart','commentRangeEnd']:
        assert not b.findall('.//w:'+tag,NS)
    ids=b.xpath('//@w14:paraId',namespaces={'w14':'http://schemas.microsoft.com/office/word/2010/wordml'})
    assert len(ids)==len(set(ids))
    core=E.fromstring(new['docProps/core.xml'])
    for key in ['creator','lastModifiedBy']:
        assert not core.xpath('//*[local-name()="'+key+'" and normalize-space(text())!=""]')
    for tag in ['{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath',
                '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline']:
        assert len(b.findall('.//'+tag))==1
        assert [E.tostring(x) for x in a.findall('.//'+tag)]==[E.tostring(x) for x in b.findall('.//'+tag)]
    assert read(QA/'a11y.json')['counts']==dict(high=0,medium=0,low=0)
    pdf=args.render_dir/OUTPUT.with_suffix('.pdf').name
    pages=PdfReader(pdf).pages;assert len(pages)==3
    assert len(list(args.render_dir.glob('page-*.png')))==3
    rendered=''.join(p.extract_text() for p in pages)
    assert '[6]' in rendered and '[7]' in rendered and '26.7%' in rendered
    r=dict(complete=True,sha256=digest(OUTPUT),source_preserved=True,template_styles_and_sections_equal=True,
        original_result_tables_preserved=5,figures=1,editable_equations=1,references=7,pages=3,
        a11y=dict(high=0,medium=0,low=0),comments=0,tracked_changes=0,hidden_author_metadata_empty=True,
        duplicate_paragraph_ids=0,evidence_files_verified=len(m['evidence_sha256']),
        holdout_recount=m['holdout_recount'],render_dir=str(args.render_dir),render_sha256=digest(pdf),issues=[])
    (QA/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))

if __name__=='__main__':main()
