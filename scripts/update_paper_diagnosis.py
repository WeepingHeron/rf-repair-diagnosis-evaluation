"""Patch the reviewed manuscript with audited diagnosis extensions; preserve its template."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'submission/ACK2026_2026-09-06_extended/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
OUTPUT = ROOT / 'submission/ACK2026_2026-09-06_diagnosis/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
QA = ROOT / 'build/paper_diagnosis_update'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def q(s): return '{' + NS['w'] + '}' + s
def txt(p): return ''.join(p.xpath('.//w:t/text()', namespaces=NS))
def digest(p): return sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())

def settext(p, value):
    old = p.find('w:r', NS)
    r = deepcopy(old) if old is not None else E.Element(q('r'))
    for c in list(r):
        if c.tag != q('rPr'): r.remove(c)
    t = E.SubElement(r, q('t')); t.text = value
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    for c in list(p):
        if c.tag != q('pPr'): p.remove(c)
    p.append(r)

def main():
    assert digest(SOURCE) == 'fb04b9fa0b58aca4a30683f849bd3c35b3fea69737684b94ed8a4326854f0fc6'
    evidence = {}
    audits = {}
    for name in ['nonideal_screen_v1', 'lossy_repair_v1', 'diagnosis_visibility_v1', 'reference_diagnosis_v2',
                 'abstention_calibration_v1', 'stability_extension_v1']:
        pp = ROOT / f'experiments/{name}.json'
        ap = ROOT / f'build/{name}_audit/summary.json'
        a = read(ap); assert a['complete'] and not a['issues']
        assert a['protocol_sha256'] == digest(pp)
        for p, h in read(pp).get('file_sha256', {}).items():
            assert digest(ROOT / p) == h, p
        for p, h in a.get('row_sha256', {}).items():
            assert digest(ROOT / p) == h, p
        evidence[str(pp.relative_to(ROOT))] = digest(pp)
        evidence[str(ap.relative_to(ROOT))] = digest(ap)
        audits[name] = a
    t = audits['abstention_calibration_v1']['results']['holdout']['totals']
    assert (t['faults'], t['legacy_correct'], t['new_correct'], t['new_wrong'],
            t['new_abstained_faults'], t['controls'], t['new_false_alarm']) == (2304,487,615,0,1689,64,0)
    s = audits['stability_extension_v1']
    assert (s['stable_all_16'],s['additional_fits_replayed'],s['newly_withheld_if_16_required']) == (615,7380,0)
    with ZipFile(SOURCE) as z: parts = {n: z.read(n) for n in z.namelist()}
    original = parts['word/document.xml']
    root = E.fromstring(original); body = root.find('w:body', NS)
    def find(prefix):
        matches = [p for p in root.findall('.//w:p', NS) if txt(p).startswith(prefix)]
        assert len(matches) == 1, (prefix, len(matches))
        return matches[0]
    changes = []
    def replace(prefix, value):
        p = find(prefix); changes.append({'before':txt(p),'after':value});settext(p,value)

    p = find('본 연구는 기존 RF 회로에')
    old = txt(p)
    value = old.replace('본 결과는 이상적 집중소자 회로의 합성 고장에 한정되며 실제 하드웨어 동작을 보장하지 않는다.',
        '별도 손실 모델 확장에서는 수치 역추정과 보류 기준을 평가했다. 미사용 4설계의 주입 변화 2,304건에서 진단 정답은 487건에서 615건으로 늘고 1,689건은 보류되었으며 관찰 오진은 0건이었다. 결과는 합성 회로에 한정되며 실제 하드웨어 성능이나 무오진을 보장하지 않는다.')
    replace('본 연구는 기존 RF 회로에', value)

    # Trim repeated table narration, keeping all original result tables and their caveats.
    replace('표 3의 부품명 비노출',
        '표 3에서 단위 변환과 고장 유형 설명을 분리하고 미사용 확인군으로 재평가했다. 결합 인터페이스의 유일한 미복구는 L2 short의 정상값 3.9788736 nH를 μH 단위로 제안한 1000배 오류였다. ngspice는 수렴했으나 검증기는 specification 미회복으로 판정했다.')
    replace('표 4에서 첫 복구는',
        '표 4에서 무피드백은 재시도로 5건, 피드백은 3건을 추가 복구했다. 위치·방향 진단은 각각 30/36과 32/36이었다. 무피드백에는 응답 미완료 1건과 성능 미복구 2건, 피드백에는 성능 미복구 5건이 포함된다. 피드백은 후속 입력이 더 길어 실제 토큰·비용까지 같지는 않다. 응답 97개와 후보 96개의 재시뮬레이션으로 기록을 검증했다.')
    replace('주 비교는 하나의 이상적 필터',
        '주 비교의 구조 holdout은 같은 회로의 새 고장 6종을 3회 반복한 결과다. Blind에서도 빠진 부품명과 RFAULT1·저항값·포트 정보가 남으므로 일반적인 원인 추론 능력을 뜻하지 않는다. 후속 확장은 앞선 결과를 보고 설계한 탐색이며 주 결과와 분모를 합산하지 않는다. 반복 행은 독립 회로 표본이 아니다. 손실·오차도 합성 가정이며 정확한 현재 부품값과 고정 등가모형, 고장 전 측정, 단일 값 변화에 의존한다. 실제 PCB/RFIC·온도·비선형성 및 통계적 오류 보증은 검증하지 않았다.')
    replace('본 연구는 제한된 수정과 독립 SPICE',
        '독립 SPICE 검증은 원인 진단과 기능 복구를 구분했다. 동일 최대 호출 예산에서 피드백 우위는 없었고, 수치 기준선 대비 LLM의 추가 기여도 확인되지 않았다. 보류 기준 보정은 관찰 오진 없이 구분 가능한 작은 변화의 진단을 늘렸지만 큰 모델 오차는 해결하지 못했다. 후속 과제는 환경·모델 변화의 설명과 실제 측정 불확실성 검증이다.')

    limit = find('한계 및 결론')
    heading = deepcopy(limit); settext(heading, '손실 모델과 진단 보류 확장');limit.addprevious(heading)
    sample = find('실험 회로는')
    new = [
        '손실·기생 성분을 추가한 320조건의 정상 PASS는 8건으로, 손실 보상 설계와 별도 사양을 고정했다. L의 직렬 R=0.05 Ω·병렬 C=0.1 pF, C의 직렬 R=0.02 Ω·ESL=0.2 nH를 사용했다. 중심 손실≤2 dB, 반사손실≥15 dB, peak 오차≤3%, 양 통과대역 경계 S21≥−6 dB, 양 저지대역 측정점 S21≤−12 dB를 적용한 새 4설계·8고장에서 이상적 공진 5/8, 수치 탐색 8/8, 같은 후보를 받은 LLM 16/16 복구였다. LLM은 각 사례 2회 모두 최상위 후보를 골랐으나 위치·방향 진단은 8/16이었다. 수치 탐색의 추가 계산 비용이 있어 동일 총예산 비교는 아니다.',
        '새 8고장의 진단 전용 비교에서도 수정 후보 미공개·공개 모두 정답 0/16이었다. 이어 고장 전 기준 측정을 추가했다. 정상 사양 미달 설계 1개를 제외한 적격 3설계·6고장을 호출 전에 별도 고정했다. 기준 없음·기준만·기준과 역추정의 위치·방향 정답은 각각 3/12·3/12·12/12였다. 결정적 역추정 자체도 6/6으로 LLM의 추가 진단 이점은 없었다.',
        '역추정은 현재 회로의 6개 부품별로 과거값 하나만 바꾸어 고장 전 S11·S21·S22의 9주파수 크기와 모델 예측의 dB RMSE를 최소화한다. 측정값은 0.01 dB로 반올림하며 탐색 범위는 현재값의 0.4~2.5배다. 잡음·비균일 환경 및 모델 오차의 개발 확인 후, 개발·보정·평가를 각 4설계로 분리했다. 보정과 평가는 각각 4설계×6부품×±1·3·10%×16오차 조건의 주입 2,304건과 무주입 대조 64건이다. 잡음 σ=0.01 dB, L/C 변화 ±0.1·0.5%, 모델 오차 ±10%와 결합 조건을 포함하며 규격 PASS인 주입 상태도 제외하지 않았다.',
        '무변화·최선·차선 가설 잔차를 E0·E1·E2라 할 때 E1≤0.02 dB, E2−E1≥0.03 dB, E2/max(E1,0.01)≥3을 요구한다. 또한 (E0−E1)/max(E1,0.01)≥8.054607과 ±0.01 dB 재최적화 4회의 부품·방향 일치를 요구한다. 36개 기준 후보 중 보정 오진·오경보 0인 최다 정답 설정을 평가 전에 고정했다. 무변화 점수 문턱은 보정 대조 최대값에 10% 여유를 둔 경험값이며 확률적 보증이 아니다.',
    ]
    for value in new:
        p = deepcopy(sample);settext(p,value);limit.addprevious(p)
    caption = deepcopy(find('<표 4>'));settext(caption,'<표 5> 미사용 4설계의 진단 보류 기준 비교');limit.addprevious(caption)
    table = deepcopy(body.findall('w:tbl',NS)[3])
    # Reuse the existing three-column table geometry and its header/row styles.
    rows = table.findall('w:tr',NS)
    values = [['지표','기존 기준','새 기준'],['정답 /2,304','487','615'],
              ['보류 /2,304','1,817','1,689'],['오진 /2,304','0','0'],['대조 오경보 /64','0','0']]
    for r in rows[1:]: table.remove(r)
    for i,vals in enumerate(values):
        r=rows[0] if i==0 else deepcopy(rows[1])
        if i:table.append(r)
        cells=r.findall('w:tc',NS);assert len(cells)==3
        for c,v in zip(cells,vals):
            ps=c.findall('w:p',NS);settext(ps[0],v)
            for extra in ps[1:]:c.remove(extra)
    limit.addprevious(table)
    for value in [
        '표 5의 기존 기준은 E1≤0.02 dB와 E2≥0.10 dB다. 새 기준은 기존 정답 손실 없이 128건을 추가했지만 큰 환경·모델 오차는 계속 보류했다. 대조·재검사 조건을 빼도 이 평가의 판정은 같아 두 조건의 추가 이점은 확인되지 않았다. 새 기준에는 재최적화 비용이 추가되며, 관찰 오류 0건은 미래 오류 0의 보장이 아니다.',
        '확정 615건만 ±0.01 dB 재검사를 4회에서 16회로 늘린 사후 확인에서도 모두 같은 부품·방향을 유지했다. 추가 계산은 7,380회이며 새 불안정 사례가 없어 기본 4회를 유지했다. 이는 새로운 미사용 평가나 실측 검증이 아니다.'
    ]:
        p=deepcopy(sample);settext(p,value);limit.addprevious(p)
    # Allow references to flow after the conclusion instead of forcing a mostly empty column.
    ref=find('참고문헌')
    for br in ref.findall('.//w:br',NS):
        if br.get(q('type'))=='column':br.getparent().remove(br)
    # Cloned paragraphs must not duplicate Word's optional paragraph identity metadata.
    seen=set()
    for p in root.findall('.//w:p',NS):
        for key in list(p.attrib):
            if key.endswith('}paraId'):
                if p.attrib[key] in seen:del p.attrib[key]
                else:seen.add(p.attrib[key])
    parts['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
    with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    with ZipFile(SOURCE) as z:assert [n for n in parts if parts[n]!=z.read(n)]==['word/document.xml']
    (QA/'changes.json').write_text(json.dumps({'source_sha256':digest(SOURCE),'output_sha256':digest(OUTPUT),
        'evidence_sha256':evidence,'replacements':changes,'added_section':'손실 모델과 진단 보류 확장'},ensure_ascii=False,indent=2)+'\n')
    print(OUTPUT)

if __name__=='__main__':main()
