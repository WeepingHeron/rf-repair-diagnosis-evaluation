"""Verify manuscript evidence, unchanged template and original results, and rendered pages."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from pypdf import PdfReader
from update_paper_diagnosis import ROOT, SOURCE, OUTPUT, QA, NS, txt, digest, read

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--template',type=Path,required=True)
    args=parser.parse_args()
    manifest=read(QA/'changes.json')
    assert digest(SOURCE)==manifest['source_sha256']
    assert digest(OUTPUT)==manifest['output_sha256']
    for p,h in manifest['evidence_sha256'].items():assert digest(ROOT/p)==h,p
    with ZipFile(SOURCE) as z: old={n:z.read(n) for n in z.namelist()}
    with ZipFile(OUTPUT) as z: new={n:z.read(n) for n in z.namelist()}
    with ZipFile(args.template) as z: template={n:z.read(n) for n in z.namelist()}
    assert old.keys()==new.keys()
    assert [k for k in new if new[k]!=old[k]]==['word/document.xml']
    a=E.fromstring(old['word/document.xml']);b=E.fromstring(new['word/document.xml'])
    t=E.fromstring(template['word/document.xml'])
    assert new['word/styles.xml']==template['word/styles.xml']
    assert [E.tostring(x) for x in b.findall('.//w:sectPr',NS)]==[E.tostring(x) for x in t.findall('.//w:sectPr',NS)]
    at=a.find('w:body',NS).findall('w:tbl',NS)
    bt=b.find('w:body',NS).findall('w:tbl',NS)
    assert len(at)==5 and len(bt)==6
    for x,y in zip(at[1:],bt[1:5]):assert E.tostring(x)==E.tostring(y)
    for r in ['[1]','[2]','[3]','[4]','[5]']:
        assert [txt(p) for p in a.findall('.//w:p',NS) if txt(p).startswith(r)]==[txt(p) for p in b.findall('.//w:p',NS) if txt(p).startswith(r)]
    expected=[['지표','기존 기준','새 기준'],['정답 /2,304','487','615'],['보류 /2,304','1,817','1,689'],['오진 /2,304','0','0'],['대조 오경보 /64','0','0']]
    actual=[[txt(c) for c in r.findall('w:tc',NS)] for r in bt[-1].findall('w:tr',NS)]
    assert actual==expected
    evidence=read(ROOT/'build/abstention_calibration_v1_audit/summary.json')['results']['holdout']['totals']
    assert (evidence['legacy_correct'],evidence['new_correct'],evidence['faults']-evidence['legacy_correct']-evidence['legacy_wrong'],evidence['new_abstained_faults'])==(487,615,1817,1689)
    loss=read(ROOT/'build/lossy_repair_v1_audit/summary.json')
    assert (loss['llm']['final_recovered'],loss['llm']['diagnosed'],loss['llm']['top_numerical_candidate_used'])==(16,8,16)
    assert (loss['baselines']['ideal_resonance']['recovered'],loss['baselines']['numerical_search']['recovered'])==(5,8)
    vis=read(ROOT/'build/diagnosis_visibility_v1_audit/summary.json')['conditions']
    assert [v['diagnosed'] for v in vis.values()]==[0,0]
    ref=read(ROOT/'build/reference_diagnosis_v2_audit/summary.json')['conditions']
    assert [ref[k]['diagnosed'] for k in ['current_only','historical_reference','reference_with_fit']]==[3,3,12]
    full=txt(b)
    for phrase in ['46/48','45/48','37/48','33/36','31/36','487건에서 615건','4설계×6부품','관찰 오류 0건','대조·재검사 조건을 빼도','새로운 미사용 평가나 실측 검증이 아니다','7,380회','기본 4회']:
        assert phrase in full,phrase
    for stale in ['부품 편차, 기생성분, 비선형성 및 측정 오차를 반영하지 않아','후속 연구에서는 부품 편차·기생성분을 포함한 새 사례로']:
        assert stale not in full,stale
    for tag in ['ins','del','commentRangeStart','commentRangeEnd','commentReference']:
        assert not b.findall('.//w:'+tag,NS),tag
    ids=b.xpath('//@w14:paraId',namespaces={'w14':'http://schemas.microsoft.com/office/word/2010/wordml'})
    assert len(ids)==len(set(ids))
    core=E.fromstring(new['docProps/core.xml'])
    for key in ['creator','lastModifiedBy']:
        assert not core.xpath('//*[local-name()="'+key+'" and normalize-space(text())!=""]')
    maths=b.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath')
    images=b.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline')
    assert len(maths)==1 and len(images)==1
    assert read(QA/'a11y.json')['counts']=={'high':0,'medium':0,'low':0}
    pdf=QA/'render'/OUTPUT.with_suffix('.pdf').name
    pages=PdfReader(pdf).pages; assert len(pages)==3
    assert len(list((QA/'render').glob('page-*.png')))==3
    lengths=[len(p.extract_text()) for p in pages];assert all(x>500 for x in lengths)
    result={'complete':True,'output':str(OUTPUT.relative_to(ROOT)),'sha256':digest(OUTPUT),
        'source_preserved':True,'official_template_styles_and_sections_equal':True,
        'original_result_tables_preserved':4,'result_tables':5,'editable_equations':1,'figures':1,
        'pages':len(pages),'pdf_text_lengths':lengths,'a11y':{'high':0,'medium':0,'low':0},
        'comments':0,'tracked_changes':0,'duplicate_paragraph_ids':0,'hidden_authors_empty':True,
        'evidence_files_verified':len(manifest['evidence_sha256']),
        'render_sha256':digest(pdf),'issues':[]}
    (QA/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
