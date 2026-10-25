"""Independently validate the paired result, preservation, and rendered manuscript."""
import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from pypdf import PdfReader
from update_paper_evidence import ROOT, SOURCE, OUTPUT, QA
from update_paper_diagnosis import NS, q, txt, read, digest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--render-dir',type=Path,required=True)
    args=parser.parse_args();m=read(QA/'changes.json')
    assert digest(SOURCE)==m['source_sha256'] and digest(OUTPUT)==m['output_sha256']
    for path,h in m['evidence_sha256'].items():assert digest(ROOT/path)==h,path
    def unpack(path):
        with ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}
    old,new,template=map(unpack,[SOURCE,OUTPUT,args.template])
    assert old.keys()==new.keys()
    changed=[n for n in new if new[n]!=old[n]]
    assert set(changed)=={'word/document.xml','word/media/image3.png'}
    a,b,t=[E.fromstring(x['word/document.xml']) for x in [old,new,template]]
    assert new['word/styles.xml']==template['word/styles.xml']
    assert [E.tostring(s) for s in b.findall('.//w:sectPr',NS)]==[E.tostring(s) for s in t.findall('.//w:sectPr',NS)]
    # Compare all original tables after removing only the intentional keepNext additions.
    def canon_table(table):
        table=E.fromstring(E.tostring(table))
        for p in table.findall('.//w:p',NS):
            for k in list(p.attrib):
                if k.endswith('}paraId'):del p.attrib[k]
        for n in table.findall('.//w:keepNext',NS):n.getparent().remove(n)
        return E.tostring(table)
    at,bt=[x.find('w:body',NS).findall('w:tbl',NS) for x in [a,b]]
    assert len(at)==6 and len(bt)==7
    for i,j in [(1,1),(2,2),(3,4),(4,5),(5,6)]:assert canon_table(at[i])==canon_table(bt[j]),(i,j)
    joint=Counter();errors=Counter();files=0
    for exp in ['closed_loop_value_repeat_v1_0','closed_loop_structural_blind_v2']:
        for p in (ROOT/'build/experiments'/exp).glob('*/trajectory_*/final.json'):
            f=read(p);r=read(p.parent/f"iteration_{f['iterations_used']}.json")
            repaired=f['final_recovered'] is True;diagnosed=r.get('diagnosis_correct') is True
            joint[(repaired,diagnosed)]+=1;files+=1
            if repaired and not diagnosed:errors['type_only' if r.get('component_correct') is True else 'location']+=1
    assert files==48 and dict(joint)=={(True,True):35,(True,False):11,(False,True):2}
    assert errors==dict(type_only=8,location=3)
    values=[[''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in row.findall('w:tc',NS)] for row in bt[3].findall('w:tr',NS)]
    assert values==[['복구 판정','진단 정답','진단 오답'],['성공','35','11'],['실패','2','0']]
    # Verify the retained holdout numbers against hash-bound rows rather than the paper text.
    audit=read(ROOT/'build/abstention_calibration_v1_audit/summary.json');hold=Counter()
    for path,h in audit['row_sha256'].items():
        if '/holdout/rows/' not in path:continue
        assert digest(ROOT/path)==h
        r=read(ROOT/path);d=r['new_result'];accepted=not d['abstained']
        if r['kind']=='fault':
            correct=d['diagnosis']['component']==r['truth']['component'] and d['diagnosis']['fault_type']==r['truth']['fault_type']
            hold['injected']+=1;hold['correct']+=accepted and correct;hold['wrong']+=accepted and not correct;hold['held']+=not accepted
        else:hold['controls']+=1;hold['false_alarm']+=accepted
    assert hold==dict(injected=2304,correct=615,wrong=0,held=1689,controls=64,false_alarm=0)
    ap,bp=[x.findall('.//w:p',NS) for x in [a,b]]
    for i in range(1,8):assert [txt(p) for p in ap if txt(p).startswith(f'[{i}]')]==[txt(p) for p in bp if txt(p).startswith(f'[{i}]')]
    whole=txt(b)
    for phrase in ['복구 성공 46회에는 진단 오답 11회','위치 오진 3회','유형이 틀린 8회',
                   '진단 증거와 식별 한계의 보조 탐색','관찰 차이로 두 방법의 동등성',
                   '개선을 다중 장치 전체의 효과로 해석하지 않는다','73.3%는 보류',
                   '진단·성능·계산 비용을 함께 보고해야 한다']:
        assert phrase in whole,phrase
    captions=[txt(p) for p in bp if txt(p).startswith('<표 ')]
    assert [c.split('>')[0]+'>' for c in captions]==[f'<표 {i}>' for i in range(1,7)]
    assert all(f'표 {i}' in ''.join(txt(p) for p in bp if not txt(p).startswith('<표 ')) for i in range(1,7))
    for tag in ['ins','del','commentReference','commentRangeStart','commentRangeEnd']:assert not b.findall('.//w:'+tag,NS)
    ids=b.xpath('//@w14:paraId',namespaces={'w14':'http://schemas.microsoft.com/office/word/2010/wordml'})
    assert len(ids)==len(set(ids))
    for tag in ['creator','lastModifiedBy']:
        assert not E.fromstring(new['docProps/core.xml']).xpath(f'//*[local-name()="{tag}" and normalize-space(text())!=""]')
    math='{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'
    assert len(b.findall('.//'+math))==1
    assert [E.tostring(x) for x in a.findall('.//'+math)]==[E.tostring(x) for x in b.findall('.//'+math)]
    assert len(b.xpath('//*[local-name()="inline"]'))==1
    assert read(QA/'a11y.json')['counts']==dict(high=0,medium=0,low=0)
    pdf=args.render_dir/OUTPUT.with_suffix('.pdf').name;pages=PdfReader(pdf).pages
    assert len(pages)==3 and len(list(args.render_dir.glob('page-*.png')))==3
    for page in pages:
        assert abs(float(page.mediabox.width)*25.4/72-210)<.1
        assert abs(float(page.mediabox.height)*25.4/72-297)<.1
    render_text=''.join(p.extract_text() for p in pages)
    assert all(f'[{i}]' in render_text for i in range(1,8))
    result=dict(complete=True,output_sha256=digest(OUTPUT),source_preserved=True,
        changed_package_parts=changed,template_styles_sections_preserved=True,original_result_tables_preserved=5,
        new_joint_table=values,location_errors=3,type_only_errors=8,primary_records_verified=48,
        evidence_hashes_verified=len(m['evidence_sha256']),holdout_recount=dict(hold),pages=3,all_pages_A4=True,
        figures=1,editable_equations=1,references=7,a11y=dict(high=0,medium=0,low=0),
        comments=0,tracked_changes=0,render_dir=str(args.render_dir),render_sha256=digest(pdf),issues=[])
    (QA/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
