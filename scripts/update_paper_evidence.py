"""Focus the manuscript on paired repair/diagnosis evidence; preserve its template."""
from collections import Counter
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
import json
import subprocess
from xml.sax.saxutils import escape
from lxml import etree as E
from update_paper_diagnosis import ROOT, NS, q, txt, settext, read, digest

SOURCE = ROOT/'submission/ACK2026_2026-09-06_reframed/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
OUTPUT = ROOT/'submission/ACK2026_2026-09-07_evidence/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
QA = ROOT/'build/paper_evidence_update'

def paired_evidence():
    counts = Counter(); detail = []; hashes = {}
    for name in ['closed_loop_value_repeat_v1_0', 'closed_loop_structural_blind_v2']:
        for p in sorted((ROOT/'build/experiments'/name).glob('*/trajectory_*/final.json')):
            final = read(p)
            ip = p.parent/f"iteration_{final['iterations_used']}.json"
            row = read(ip)
            repaired = final['final_recovered'] is True
            diagnosed = row.get('diagnosis_correct') is True
            group = 'both' if repaired and diagnosed else 'repair_only' if repaired else 'diagnosis_only' if diagnosed else 'neither'
            counts[group] += 1
            detail.append(dict(experiment=name, fault_id=final['fault_id'], trajectory=final['trajectory'],
                repaired=repaired, diagnosed=diagnosed, location_correct=row.get('component_correct') is True, group=group))
            for path in [p, ip]: hashes[str(path.relative_to(ROOT))] = digest(path)
    assert dict(counts) == dict(both=35, repair_only=11, diagnosis_only=2)
    assert sum(r['group']=='repair_only' and not r['location_correct'] for r in detail)==3
    assert sum(r['group']=='repair_only' and r['location_correct'] for r in detail)==8
    return dict(counts, neither=0), detail, hashes

def diagram():
    # New code-native diagram: truth enters only the diagnosis evaluator.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="3.18in" height="1.48in" viewBox="0 0 318 148">',
         '<rect width="318" height="148" fill="white"/>',
         '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#343434"/></marker></defs>']
    def box(x,y,w,h,label,fill='white',style='solid'):
        dash=' stroke-dasharray="3 2"' if style=='dashed' else ''
        svg.append(f'<rect x="{x*318}" y="{(1-y-h)*148}" width="{w*318}" height="{h*148}" rx="2" fill="{fill}" stroke="#343434" stroke-width="0.85"{dash}/>')
        lines=label.split('\n');cy=(1-y-h/2)*148
        for i,line in enumerate(lines):
            svg.append(f'<text x="{(x+w/2)*318}" y="{cy+(i-(len(lines)-1)/2)*10+3}" font-family="Arial, sans-serif" font-size="9" text-anchor="middle">{escape(line)}</text>')
    def arrow(points,color='#343434'):
        coords=' '.join(f'{x*318},{(1-y)*148}' for x,y in points)
        svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="0.9" marker-end="url(#arrow)"/>')
    box(.02,.77,.27,.20,'Injected truth\nEvaluator only',style='dashed')
    box(.02,.43,.27,.22,'Faulty netlist\nSpecs + metrics')
    box(.35,.43,.23,.22,'LLM\nDiagnosis + edit',fill='#f3f3f3')
    box(.69,.66,.29,.22,'Diagnosis score\nLocation + type',fill='#eaf0f7')
    box(.35,.10,.23,.20,'Restricted patch\n+ ngspice')
    box(.69,.10,.29,.20,'Repair score\nSpec satisfaction',fill='#eaf0f7')
    arrow([(.29,.54),(.35,.54)])
    arrow([(.58,.60),(.63,.60),(.63,.73),(.69,.73)])
    arrow([(.29,.87),(.62,.87),(.62,.82),(.69,.82)])
    arrow([(.465,.43),(.465,.30)])
    arrow([(.58,.20),(.69,.20)])
    arrow([(.835,.10),(.835,.025),(.315,.025),(.315,.37),(.41,.37),(.41,.43)],'#365b81')
    for i,line in enumerate(['Failure feedback','(no injected truth)']):
        svg.append(f'<text x="11" y="{119+i*9}" font-family="Arial, sans-serif" font-size="8.2" fill="#365b81">{line}</text>')
    svg.append('</svg>')
    QA.mkdir(parents=True,exist_ok=True)
    (QA/'separate_evaluation.svg').write_text('\n'.join(svg))
    subprocess.run(['/Users/taehoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node',
        '-e',"const sharp=require('/Users/taehoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');sharp(process.argv[1],{density:96}).resize({width:1908}).png().toFile(process.argv[2]).catch(e=>{console.error(e);process.exit(1)});",
        str(QA/'separate_evaluation.svg'),str(QA/'separate_evaluation.png')],check=True)
    return (QA/'separate_evaluation.png').read_bytes()

def main():
    assert digest(SOURCE)=='89a8f3a6fb8a85c65853730534bbcc5d715dd27e8c9b6488913805bab60d682f'
    previous=read(ROOT/'build/paper_framing_update/changes.json')
    for path,h in previous['evidence_sha256'].items():assert digest(ROOT/path)==h,path
    counts,detail,evidence=paired_evidence()
    evidence.update(previous['evidence_sha256'])
    with ZipFile(SOURCE) as z:parts={n:z.read(n) for n in z.namelist()}
    root=E.fromstring(parts['word/document.xml']);body=root.find('w:body',NS);changes=[]
    def find(prefix):
        matches=[p for p in root.findall('.//w:p',NS) if txt(p).startswith(prefix)]
        assert len(matches)==1,(prefix,len(matches))
        return matches[0]
    def replace(prefix,value):
        p=find(prefix);changes.append(dict(before=txt(p),after=value));settext(p,value)

    replace('본 연구는 합성 단일 고장이',
        '본 연구는 합성 단일 고장이 주입된 집중소자 RF 회로에서 LLM의 성능 복구와 원인 진단을 같은 실행에서 분리 평가한다. 진단은 주입 위치·유형과 대조하고 복구는 독립 SPICE 성능 제약 충족으로 판정한다. 100 MHz 필터의 48회 중 복구 성공 46회에는 진단 오답 11회가 포함됐고, 진단 정답에도 복구하지 못한 실행이 2회였다. 복구만 성공한 11회는 위치 오진 3회와 위치는 맞지만 유형이 틀린 8회다. 새 4설계의 동일 최대 호출 예산 비교는 무피드백 33/36, 피드백 31/36으로 피드백 우위가 확인되지 않았다. 수치 기준선 대비 LLM의 추가 기여도 시험한 조건에서는 확인되지 않았다. 별도 기준 측정 탐색은 정확한 현재값·고정 모델에 의존하며 보류를 포함한 식별 한계를 확인했다. 결과는 합성 조건에 한정된다.')
    replace('LLM 회로 자동화 연구는',
        'LLM 회로 자동화 연구는 SPICE 생성[1], 수치 도구를 이용한 RF 필터 설계[2], 증폭기 sizing[3]과 트로이목마 탐지·교정[4]을 다룬다. NetlistBench[5]는 netlist 조작의 구조적 정확성을 평가한다. 본 연구는 주입 정답과의 진단 일치와 수정 후 RF 성능을 같은 실행에서 대조하여, 기능 복구 성공률만으로 가려지는 진단 오류를 분석한다. 측정을 설명하는 파라미터 해의 모호성[6]과 판단 비율·오류의 관계[7]는 별도 식별 탐색의 근거로 삼는다.')
    replace('본 연구의 질문은',
        '연구 질문은 성능을 회복한 수정이 주입 원인도 올바르게 식별하는지, 반복 피드백과 수치 보조가 추가 기여를 하는지이다. 복구·진단의 교차 결과와 보상 수정 사례를 제시하고, 피드백은 동일 최대 호출 예산에서 비교한다. 기준 측정·보류 실험은 진단에 필요한 정보와 식별 범위를 확인하는 보조 탐색으로 분리한다.')
    replace('그림 1의 평가기는',
        '그림 1은 두 평가 경로를 분리한다. 정상 회로에 단일 고장을 주입하고 LLM에는 현재 netlist·목표 사양·시뮬레이션 결과만 제공한다. 진단 경로는 의심 부품·유형을 비공개 주입 정답과 대조한다. 복구 경로는 제한된 수정 후 성능 제약을 검사한다. 값 변화의 진단은 위치·증감 방향을 평가하며, 판단 보류는 부품을 특정하지 않는 출력이다.')
    replace('(그림 1)', '(그림 1) 진단 정답 대조와 SPICE 복구 평가')
    replace('실행기는 set_value',
        '실행기는 set_value, restore_component, set_port_impedance만 허용하며 임의 netlist 재작성을 금지한다. 수정본이 주파수·S21·S11·통과 및 저지대역 제약을 모두 만족해야 복구 성공이다. 실패 시 최대 3회까지 시도하며 주입 정답은 피드백하지 않는다. 기준 측정 탐색은 현재 부품값과 고정 모델을 알고 과거 응답을 설명하는 변화 위치·방향을 추정한다. 현재 고장 부품값을 모르는 장비 진단과 입력 조건이 다르다.')
    replace('비교 조건은 netlist만',
        '비교군은 netlist-only 및 최초 SPICE 추가 one-shot, 반복 feedback, 고장 비율에 맞춘 deterministic grid다. 주 결과는 사전 고정한 strict 조건이다. 결과 후 추가한 단위 변환·유형 설명은 개발 집합에서 분리 평가하고, 미사용 확인군에서 strict와 결합 조건을 비교했다.')
    replace('추가 비교에서는 중심주파수',
        '동일 예산 비교는 83·117·149·173 MHz, 대역폭 10·12·14·16%의 새 설계에서 값 고장 12개를 만들고 부품·노드명과 행 순서를 바꿨다. 두 조건은 최초 입력·모델·스키마·출력 2000토큰·최대 3회 호출을 공유한다. 무피드백은 최초 입력만 반복하고 피드백은 이전 실패 제안·측정 결과를 받는다. 정상 PASS·고장 FAIL·정답 수정 PASS를 사전 확인한 뒤 각 3회 실행했다. 통과대역 경계 S21≥−4 dB를 별도 고정하고 성공 시 종료하며 미완료도 실패에 포함했다. 후보는 초기 고장 회로에 독립 적용한다.')

    # Keep five original result tables; add a paired table directly after the primary table.
    replace('<표 3>', '<표 4> 인터페이스 개발 및 미사용 확인군(holdout)')
    replace('표 3에서',
        '표 4의 유형 설명은 주입 유형 명칭과 출력 해석의 정합성을 점검하는 별도 인터페이스 실험이다. 진단 점수 상승을 모두 새로운 물리적 원인 추론으로 해석하지 않는다. 확인군 결합 조건의 미복구 1건은 L2 short의 3.9788736 nH를 μH로 제안한 1000배 오류였다. 시뮬레이션은 수렴했지만 성능 제약을 충족하지 못했다.')
    # Find old table 4 by its full caption since the preceding rename also starts with <표 4>.
    replace('<표 4> 새 설계', '<표 5> 새 설계의 동일 최대 호출 예산 비교')
    replace('표 4에서 무피드백',
        '표 5에서 무피드백은 재시도로 5건, 피드백은 3건을 추가 복구했다. 위치·방향 진단은 각각 30/36과 32/36이었다. 무피드백의 응답 미완료 1건·성능 미복구 2건과 피드백의 미복구 5건을 포함했다. 실제 토큰·비용은 같지 않으며, 관찰 차이로 두 방법의 동등성이나 일반적 열등성을 입증하지 않는다. 응답 97개·후보 96개를 재검증했다.')
    replace('<표 5> 미사용', '<표 6> 보조 탐색의 미사용 4설계 식별 결과')
    oldparagraph=find('표 2의 복구는')
    replace('표 2의 복구는',
        '표 3은 표 2의 최종 출력을 실행별로 교차 집계한 결과다. 복구만 성공한 11회 중 3회는 L2 고장을 C2 조정으로 보상한 위치 오진이고, 8회는 위치는 맞으나 유형이 틀렸다. 전체 진단 정답에도 복구하지 못한 실행은 2회다. 따라서 성능 회복, 위치 식별과 유형 정답을 구분해야 한다. Grid는 10/10 복구했지만 고장 비율의 역수 후보와 65회 시뮬레이션을 써 동등한 비교가 아니다.')
    caption=deepcopy(find('<표 2>'));settext(caption,'<표 3> 주 실험 48회의 복구와 전체 진단 교차 결과')
    oldparagraph.addprevious(caption)
    table=deepcopy(body.findall('w:tbl',NS)[3])
    rows=table.findall('w:tr',NS)
    for row in rows[1:]:table.remove(row)
    for i,values in enumerate([['복구 판정','진단 정답','진단 오답'],['성공','35','11'],['실패','2','0']]):
        row=rows[0] if i==0 else deepcopy(rows[1])
        if i:table.append(row)
        for cell,value in zip(row.findall('w:tc',NS),values):
            ps=cell.findall('w:p',NS);settext(ps[0],value)
            for extra in ps[1:]:cell.remove(extra)
    oldparagraph.addprevious(table)

    replace('L형 정합회로 전이 파일럿은',
        'L형 정합회로는 91·131·181·223 MHz의 직렬 L·병렬 C, source 50 Ω·load 100·150·200·250 Ω의 8고장을 각 1회 one-shot으로 평가했다. 포트를 고정하고 중심 S11≤−20 dB·S21≥−0.25 dB, 0.9f·1.1f에서 S11≤−12 dB·S21≥−0.5 dB를 요구했다. 미완료 1건 포함 복구 5/8·위치와 방향 진단 6/8로, 전이 일반화는 미검증이다.')

    replace('손실 모델과 값 변화 식별','진단 증거와 식별 한계의 보조 탐색')
    replace('손실·기생 성분을 추가한',
        '주 결과의 보상 수정과 수치 보조 해석을 점검하기 위해 손실 모델에서 별도로 탐색했다. 320조건의 정상 PASS는 8건이어서 손실 보상 설계·사양을 고정했다. L의 직렬 R=0.05 Ω·병렬 C=0.1 pF, C의 직렬 R=0.02 Ω·ESL=0.2 nH를 사용했다. 중심 손실≤2 dB, 반사손실≥15 dB, peak 오차≤3%, 통과대역 경계 S21≥−6 dB, 저지대역 S21≤−12 dB의 새 4설계·8고장에서 이상적 공진 5/8, 수치 탐색 8/8, 같은 후보+LLM 16/16 복구였다. LLM은 모두 최상위 후보를 골랐지만 진단은 8/16으로, 복구와 진단의 불일치가 다시 관찰됐다. 수치 탐색 비용 때문에 동일 총예산 비교는 아니다.')
    replace('새 8고장의 진단 전용',
        '수정 후보만으로 원인 식별이 개선되는지 새 8고장의 진단 전용 조건에서 확인했으나 후보 미공개·공개 모두 정답 0/16이었다. 기준 측정 탐색은 정상 사양 미달 1설계를 제외한 3설계·6고장을 호출 전에 고정했다. 기준 없음·기준만·기준+역추정은 각 3/12·3/12·12/12 정답이고 역추정 자체도 6/6이었다. 이는 수치 식별 결과를 받은 효과이며 LLM의 추가 진단 기여는 확인되지 않았다.')
    replace('역추정은 6개 부품별로',
        '식별의 적용 한계는 현재값·모델을 아는 조건에서 평가했다. 6부품별 과거값 하나를 현재값의 0.4~2.5배에서 탐색하고, 0.01 dB로 반올림한 과거 S11·S21·S22의 9주파수 크기 RMSE를 최소화한다. 개발·보정·평가는 각 4설계로 분리했다. 보정·평가는 각각 6부품×±1·3·10%×16오차 조건×4설계의 주입 2,304건과 대조 64건이다. 오차는 잡음 σ=0.01 dB, L/C ±0.1·0.5%, 모델 ±10% 및 결합 조건이다. 미사용 기본 주입 144상태의 규격 PASS 88·FAIL 56을 모두 포함하므로 복구율과 합산하지 않는다.')
    replace('무변화·최선·차선 가설',
        '무변화·최선·차선 잔차를 E0·E1·E2라 할 때 E1≤0.02 dB, E2−E1≥0.03 dB, E2/max(E1,0.01)≥3과 무변화 대비 개선비≥8.054607, ±0.01 dB 재최적화 4회 일치를 요구했다. 개선비는 (E0−E1)/max(E1,0.01)이다. 36후보 중 보정 오진·오경보 0인 최다 정답 설정을 평가 전에 고정했다. 개선비 문턱은 보정 대조 최대값의 1.1배인 경험값이다.')
    replace('표 5의 기존 기준은',
        '표 6의 기존 기준은 E1≤0.02 dB와 E2≥0.10 dB다. 정답 128건을 추가해 21.1%→26.7%였으나 73.3%는 보류했고 큰 환경·모델 오차는 해결하지 못했다. 잔차·간격·비율만으로도 전체 판정과 같아 개선을 다중 장치 전체의 효과로 해석하지 않는다. 재최적화 비용이 들며 오진 0의 관찰은 미래 무오진·실측 성능을 보장하지 않는다.')
    p=find('확정 615건만');changes.append(dict(before=txt(p),after='[앞 문단에 통합]'));p.getparent().remove(p)
    replace('주입 정답과의 진단 대조',
        '같은 실행의 진단 정답과 SPICE 성능을 대조해 복구 성공만으로 원인 진단을 평가할 수 없음을 보였다. 위치 오진과 유형 오진도 구분해야 한다. 시험한 조건에서 동일 최대 호출 예산의 피드백 우위와 수치 기준선 대비 LLM의 추가 기여는 확인되지 않았다. 따라서 진단·성능·계산 비용을 함께 보고해야 한다. 기준 측정·후보 구분 보정은 식별 한계를 설명하는 보조 결과이며, 현재값 불확실성·다른 모델·실측 일반화는 후속 과제다.')

    # Keep captions with their table and the short paired/abstention tables together.
    for p in root.findall('.//w:p',NS):
        if txt(p).startswith('<표 '):
            prop=p.find('w:pPr',NS)
            if prop is None:prop=E.Element(q('pPr'));p.insert(0,prop)
            item=prop.find('w:keepNext',NS)
            if item is None:item=E.SubElement(prop,q('keepNext'))
            item.set(q('val'),'true')
    for table in [table,body.findall('w:tbl',NS)[-1]]:
        rows=table.findall('w:tr',NS)
        for row in rows[:-1]:
            for p in row.findall('.//w:p',NS):
                prop=p.find('w:pPr',NS)
                if prop is None:prop=E.Element(q('pPr'));p.insert(0,prop)
                item=prop.find('w:keepNext',NS)
                if item is None:item=E.SubElement(prop,q('keepNext'))
                item.set(q('val'),'true')

    # Replace only the figure media and its aspect ratio/alternative text.
    parts['word/media/image3.png']=diagram()
    inline=root.xpath('//*[local-name()="inline"]')[0]
    for element in inline.xpath('.//*[local-name()="extent" or local-name()="ext"]'):
        if 'cx' in element.attrib:element.set('cx','2907792');element.set('cy',str(round(2907792*1.48/3.18)))
    inline.xpath('.//*[local-name()="docPr"]')[0].set('descr',
        'LLM의 진단은 비공개 주입 정답과 대조하고, 제한된 수정은 ngspice 성능 제약으로 독립 평가한다. 복구 실패 피드백에는 주입 정답을 넣지 않는다.')
    inline.xpath('.//*[local-name()="cNvPr"]')[0].set('name','separate_evaluation.png')
    # Remove duplicated optional identities on cloned table paragraphs.
    seen=set()
    for p in root.findall('.//w:p',NS):
        for key in list(p.attrib):
            if key.endswith('}paraId'):
                if p.attrib[key] in seen:del p.attrib[key]
                else:seen.add(p.attrib[key])
    parts['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
        for n,data in parts.items():z.writestr(n,data)
    manifest=dict(source_sha256=digest(SOURCE),output_sha256=digest(OUTPUT),replacements=changes,
        primary_joint=counts,primary_rows=detail,evidence_sha256=evidence,
        existing_evidence_sha256=previous['evidence_sha256'],
        holdout_recount=previous['holdout_recount'],figure_sha256=digest(QA/'separate_evaluation.png'))
    (QA/'changes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(OUTPUT)

if __name__=='__main__':main()
