"""Append audited exploratory extensions to the v4 manuscript without rewriting it."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from copy import deepcopy
import json
import hashlib
from lxml import etree as E
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'submission/ACK2026_2026-09-06_v4/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
OUTPUT=ROOT/'submission/ACK2026_2026-09-06_extended/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';NS={'w':W}
def q(s):return '{'+W+'}'+s
def text(p):return ''.join(p.xpath('.//w:t/text()',namespaces=NS))
def settext(p,s):
    original=p.find('w:r',NS);r=deepcopy(original) if original is not None else E.Element(q('r'))
    for c in list(r):
        if c.tag!=q('rPr'):r.remove(c)
    t=E.SubElement(r,q('t'));t.text=s;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    for c in list(p):
        if c.tag!=q('pPr'):p.remove(c)
    p.append(r)

def resonance_equation(p):
    literal='f=1/(2π√LC)'
    if literal not in text(p):return
    before,after=text(p).split(literal)
    settext(p,before)
    mathns='http://schemas.openxmlformats.org/officeDocument/2006/math'
    def mq(t):return '{'+mathns+'}'+t
    equation=E.SubElement(p,mq('oMath'))
    def mr(parent,value):
        r=E.SubElement(parent,mq('r'));rp=E.SubElement(r,q('rPr'));E.SubElement(rp,q('sz')).set(q('val'),'20')
        E.SubElement(r,mq('t')).text=value
    mr(equation,'f=');fraction=E.SubElement(equation,mq('f'))
    mr(E.SubElement(fraction,mq('num')),'1')
    denominator=E.SubElement(fraction,mq('den'));mr(denominator,'2π')
    radical=E.SubElement(denominator,mq('rad'));properties=E.SubElement(radical,mq('radPr'))
    E.SubElement(properties,mq('degHide')).set(mq('val'),'1');E.SubElement(radical,mq('deg'))
    mr(E.SubElement(radical,mq('e')),'LC')
    r=E.SubElement(p,q('r'));E.SubElement(r,q('t')).text=after

calc=json.loads((ROOT/'build/calculator_v5_audit/summary.json').read_text())
match=json.loads((ROOT/'build/matching_v1_audit/summary.json').read_text())
assert calc['complete'] and match['complete'] and not calc['issues'] and not match['issues']
a,b=calc['conditions']['feedback'],calc['conditions']['calculator_feedback'];d=calc['deterministic_baseline'];m=match['conditions']['matching_one_shot']
with ZipFile(SOURCE) as z:parts={n:z.read(n) for n in z.namelist()}
root=E.fromstring(parts['word/document.xml']);body=root.find('w:body',NS);paragraphs=body.findall('w:p',NS)
sample=next(p for p in paragraphs if text(p).startswith('실험 회로는'))
limit=next(p for p in paragraphs if text(p)=='한계 및 결론')
newtext=[
    '탐색적 후속 실험으로 97·127·157·193 MHz, 대역폭 비율 11·13·15·17%의 새 필터 설계에서 값 고장 8개를 만들었다. 일반 피드백과 공진 계산 보조 피드백을 각 2회, 최대 3회 호출로 비교했다. 후자는 관측 netlist의 LC 연결과 목표 주파수만으로 f=1/(2π√LC)에서 유도한 수정 후보를 입력에 추가한다. 정상값이나 고장 정답은 사용하지 않는다. 두 조건 모두 앞선 새 설계의 수치 제약을 적용했다.',
    f"일반 피드백과 계산 보조의 첫 복구는 {a['first_recovered']}/16과 {b['first_recovered']}/16, 최종 복구는 {a['final_recovered']}/16과 {b['final_recovered']}/16이었다. API 호출은 각각 {a['api_calls_recorded']}회와 {b['api_calls_recorded']}회였다. 같은 공진식에서 오차가 큰 LC 쌍의 후보를 부품명 순서로 최대 3개 검증한 결정적 기준선도 LLM 없이 {d['candidate_simulations']}회 시뮬레이션으로 {d['recovered']}/8을 복구했다. 따라서 이 이상적 공진 회로 집합에서 계산 보조의 결과가 LLM의 필수성을 입증하지는 않는다.",
    f"다른 topology의 절차 작동 확인을 위해 91·131·181·223 MHz의 직렬 L·병렬 C 정합회로에서 고장 8개를 one-shot으로 평가했다. 50 Ω source와 100·150·200·250 Ω load 포트는 고정했다. 중심 S11≤−20 dB·S21≥−0.25 dB, 0.9f·1.1f에서 S11≤−12 dB·S21≥−0.5 dB의 전용 제약을 사용했다. 복구는 {m['final_recovered']}/8, 위치·방향 진단은 {m['diagnosed']}/8이며 응답 미완료 {m['incomplete_responses']}건도 실패에 포함했다. 단일 실행 파일럿이므로 일반적인 topology 전이 성능을 주장하지 않는다."
]
for value in newtext:
    p=deepcopy(sample);settext(p,value);resonance_equation(p);limit.addprevious(p)
for p in root.findall('.//w:p',NS):
    t=text(p)
    if t.startswith('본 연구는 기존 RF 회로에'):
        settext(p,t.replace('본 결과는 이상적 집중소자 필터의 합성 고장에','본 결과는 이상적 집중소자 회로의 합성 고장에'))
    if t.startswith('추가 비교에서는 중심주파수'):
        settext(p,t+' 각 후보는 초기 고장 회로에 독립적으로 적용하며 이전 수정에 누적하지 않는다.')
    if t.startswith('본 연구는 하나의 이상적 필터 topology'):
        settext(p,t.replace('본 연구는 하나의 이상적 필터 topology와 합성 단일 고장을 다룬다.','주 비교는 하나의 이상적 필터 topology와 합성 단일 고장을 다룬다.')+' 계산 보조와 정합회로는 주 비교 결과를 본 뒤 정한 탐색적 확장이고 새로 생성한 미사용 사례에서 수행했다.')
    if t.startswith('본 연구는 제한된 수정과 독립 SPICE'):
        settext(p,'본 연구는 제한된 수정과 독립 SPICE 검증으로 원인 진단과 기능 복구를 분리 평가했다. 새 설계의 동일 최대 호출 예산 비교에서 피드백 우위는 확인되지 않았다. 계산 보조와 정합회로에서도 수치 선택 및 진단의 실패를 관찰했으며, 공진식 기준선의 성공은 이 제한된 과제에서 LLM의 필요성을 추가 검토해야 함을 보여준다. 후속 연구에서는 부품 편차·기생성분을 포함한 새 사례로 계산과 후보 선택의 역할을 검증한다.')
    if t=='참고문헌':
        # The expanded final page has body text and references in separate columns.
        r=E.Element(q('r'));br=E.SubElement(r,q('br'));br.set(q('type'),'column')
        index=1 if p.find('w:pPr',NS) is not None else 0;p.insert(index,r)
parts['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
    for name,data in parts.items():z.writestr(name,data)
with ZipFile(SOURCE) as z:assert [n for n in parts if parts[n]!=z.read(n)]==['word/document.xml']
print(json.dumps({'output':str(OUTPUT),'sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest()},ensure_ascii=False))
