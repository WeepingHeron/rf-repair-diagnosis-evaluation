"""Apply the reviewed problem definition and bounded claims to the existing manuscript."""
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
import json
from lxml import etree as E
from update_paper_diagnosis import ROOT, NS, q, txt, settext, read, digest

SOURCE=ROOT/'submission/ACK2026_2026-09-06_diagnosis/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
OUTPUT=ROOT/'submission/ACK2026_2026-09-06_reframed/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
QA=ROOT/'build/paper_framing_update'
TITLE_KO='집중소자 RF 회로에서 LLM 기반 복구와 원인 진단의 분리 평가'
TITLE_EN='Separate Evaluation of LLM-Based Repair and Fault Diagnosis in Lumped RF Circuits'

def main():
    assert digest(SOURCE)=='f4151c2c3f6eb956162e9ee818288a7474f87c2f0c003d94fc513186f56e9856'
    previous=read(ROOT/'build/paper_diagnosis_update/changes.json')
    for path,h in previous['evidence_sha256'].items():assert digest(ROOT/path)==h,path
    audit=read(ROOT/'build/abstention_calibration_v1_audit/summary.json')
    assert audit['complete'] and not audit['issues']
    # Recount the held-out rows independently, without refitting or changing the policy.
    counts=dict(faults=0,correct=0,abstained=0,wrong=0,controls=0,false_alarm=0,core_difference=0)
    for path,h in audit['row_sha256'].items():
        if '/holdout/rows/' not in path:continue
        assert digest(ROOT/path)==h,path
        r=read(ROOT/path);d=r['new_result'];f=r['bundle']['features'];accepted=not d['abstained']
        core=f['best_rmse_db']<=.02 and f['gap_db']>=.03 and f['separation_ratio']>=3
        counts['core_difference']+=core!=accepted
        if r['kind']=='fault':
            counts['faults']+=1
            correct=d['diagnosis']['component']==r['truth']['component'] and d['diagnosis']['fault_type']==r['truth']['fault_type']
            counts['correct']+=accepted and correct;counts['wrong']+=accepted and not correct
            counts['abstained']+=not accepted
        else:counts['controls']+=1;counts['false_alarm']+=accepted
    assert counts==dict(faults=2304,correct=615,abstained=1689,wrong=0,controls=64,false_alarm=0,core_difference=0)
    baseline=[r for r in audit['baseline'] if r['split']=='holdout' and r['kind']=='fault']
    assert len(baseline)==144 and sum(r['verdict']=='PASS' for r in baseline)==88
    with ZipFile(SOURCE) as z:parts={n:z.read(n) for n in z.namelist()}
    root=E.fromstring(parts['word/document.xml']);body=root.find('w:body',NS);changes=[]
    def find(prefix):
        out=[p for p in root.findall('.//w:p',NS) if txt(p).startswith(prefix)]
        assert len(out)==1,(prefix,len(out))
        return out[0]
    def replace(prefix,value):
        p=find(prefix);changes.append(dict(before=txt(p),after=value));settext(p,value)

    replace('SPICE 피드백 기반 LLM 에이전트의',TITLE_KO)
    replace('SPICE-Grounded LLM Agent for RF',TITLE_EN)
    replace('본 연구는 기존 RF 회로에',
        '본 연구는 합성 단일 고장이 주입된 집중소자 RF 회로에서 LLM의 성능 복구와 원인 진단을 분리 평가하고, 반복 피드백과 수치 계산 보조의 추가 기여를 분석한다. 진단은 주입 정답과 대조하고 복구는 독립 SPICE 시뮬레이션의 성능 제약 충족으로 판정한다. 100 MHz 필터의 48회 주 실험에서 복구 46/48, 위치 진단 45/48, 전체 진단 37/48을 기록했다. 새 4설계의 동일 최대 호출 예산 비교는 무피드백 33/36, 피드백 31/36으로 피드백 우위가 확인되지 않았다. 수치 기준선 대비 LLM의 추가 기여도 시험한 조건에서는 확인되지 않았다. 현재 부품값과 고정 모델을 아는 별도 값 변화 식별에서, 보류 기준 보정은 미사용 2,304건의 확정 정답 비율을 21.1%에서 26.7%로 높였으나 73.3%는 보류했다. 관찰 오진은 0건이며 실제 계측 성능이나 미래 무오진을 보장하지 않는다.')
    replace('키워드:', '키워드: LLM, 집중소자 RF 회로, 성능 복구, 원인 진단, 판단 보류')
    replace('최근 LLM을 활용한 회로 자동화',
        'LLM 회로 자동화 연구는 SPICE 생성[1], 수치 최적화 도구를 이용한 RF 필터 설계[2], 증폭기 sizing[3]과 트로이목마 탐지·교정[4]을 다룬다. NetlistBench[5]는 netlist 조작을 외부 기준으로 평가한다. 아날로그 회로 진단에는 측정을 설명하는 여러 파라미터 해의 모호성이 존재하며[6], 선택적 예측은 판단 비율과 오류를 함께 평가한다[7]. 따라서 LLM·시뮬레이터의 연결이나 보류 자체를 새로운 원리로 주장하지 않고, 제한된 RF 과제에서 각 요소의 기여를 구분한다.')
    replace('LLM의 자연언어 판단은',
        '본 연구의 질문은 합성 단일 고장에서 성능을 회복한 수정이 원인도 올바르게 식별하는지, 동일 최대 호출 예산의 피드백과 수치 보조가 추가 기여를 하는지이다. 다른 부품을 바꿔 성능만 회복하는 보상 수정을 별도로 평가한다. 후속 기준 측정·보류 실험은 진단에 필요한 정보와 식별 범위를 확인하는 탐색이며, 주 복구 실험과 분리해 보고한다.')
    replace('제안 방법','문제 정의 및 평가 절차')
    replace('그림 1은 제안 파이프라인을',
        '그림 1의 평가기는 정상 회로에 단일 고장을 주입한다. LLM 입력은 현재 회로 netlist, 목표 사양과 시뮬레이션 결과이고 출력은 의심 부품·유형과 제한된 수정이다. 정상값과 주입 정답은 공개하지 않는다. 진단 정답은 주입 위치·유형과의 일치이며, 값 변화에서는 위치·증감 방향을 평가한다. 복구는 수정 후 정해진 성능 제약 충족이고, 판단 보류는 부품을 특정하지 않는 출력이다.')
    p=find('실행기는 set_value')
    replace('실행기는 set_value',txt(p)+' 기준 측정 확장에서는 현재 부품값과 고정 등가모형을 알고 저장된 과거 응답을 설명하는 변화 위치·방향을 식별한다. 현재의 고장 부품값을 모른 채 측정만으로 찾는 장비 진단과는 다른 입력 조건이다.')
    replace('표 1은 동일한 값 고장',
        '표 1은 같은 값 고장 10종의 3회 반복이다. 피드백 조건은 첫 복구 26/30에서 최종 30/30으로 4건을 추가 복구했다. 다만 35회 호출로 one-shot의 30회보다 비용이 커, 피드백 자체의 인과 효과로 단정하지 않는다.')
    replace('표 2의 최종 복구는',
        '표 2의 복구는 46/48(95.8%)이다. 구조 고장은 부품명 직접 표식을 제거한 Blind strict다. L2 값 고장 3회는 C2 조정으로 성능만 회복해 복구와 원인 진단이 달랐다. Grid 기준선은 10/10 복구했으나 고장 비율의 역수 후보와 65회 시뮬레이션을 사용해 동등한 비교는 아니다.')
    # Compact supporting pilots to make room for the problem definition and references.
    # Retain the original editable OMML equation while shortening its surrounding prose.
    p=find('탐색적 후속 실험으로')
    equation=deepcopy(p.find('{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))
    before='공진 계산 보조는 새 4설계(97·127·157·193 MHz, BW 11·13·15·17%)의 고장 8개에서 일반 피드백과 각 2회·최대 3회 호출로 비교했다. 관측 LC 연결과 목표 주파수의 '
    after='에서 구한 후보를 추가하며 정상값·고장 정답은 사용하지 않는다. 사양은 앞선 새 설계 비교와 같다.'
    changes.append(dict(before=txt(p),after=before+'f=1/(2π√LC)'+after))
    settext(p,before);p.append(equation)
    run=deepcopy(p.find('w:r',NS))
    run.find('w:t',NS).text=after;p.append(run)
    replace('일반 피드백과 계산 보조의 첫 복구는',
        '일반/계산 보조의 첫 복구는 11/16·8/16, 최종은 12/16·15/16이며 API는 각 25회다. 같은 공진식으로 오차가 큰 LC 쌍부터 부품명 순서로 최대 3후보를 검증한 결정적 기준선은 11회 시뮬레이션으로 8/8을 복구했다. 이 결과는 LLM의 필수성을 입증하지 않는다.')
    replace('다른 topology의 절차 작동 확인을 위해',
        'L형 정합회로 전이 파일럿은 91·131·181·223 MHz의 직렬 L·병렬 C 회로에서 8고장을 one-shot으로 평가했다. 50 Ω source와 100·150·200·250 Ω load 포트를 고정하고, 중심 S11≤−20 dB·S21≥−0.25 dB, 0.9f·1.1f에서 S11≤−12 dB·S21≥−0.5 dB를 적용했다. 복구 5/8, 위치·방향 진단 6/8이며 미완료 1건도 실패에 포함했다. 단일 실행이므로 일반적인 topology 전이 성능을 주장하지 않는다.')
    replace('손실 모델과 진단 보류 확장','손실 모델과 값 변화 식별')
    replace('역추정은 현재 회로의',
        '역추정은 6개 부품별로 과거값 하나를 현재값의 0.4~2.5배에서 탐색해, 고장 전 S11·S21·S22의 9주파수 크기와 모델 예측의 dB RMSE를 최소화한다. 측정값은 0.01 dB로 반올림했다. 개발·보정·평가를 각 4설계로 분리하고, 보정·평가는 각각 4설계×6부품×±1·3·10%×16오차 조건의 주입 2,304건과 대조 64건이다. 잡음 σ=0.01 dB, L/C 변화 ±0.1·0.5%, 모델 오차 ±10%와 결합 조건을 포함한다. 미사용 기본 주입 144상태 중 88개는 규격 PASS, 56개는 FAIL이며 둘 다 포함했다. 따라서 성능 고장 복구율이 아닌 주입 값 변화의 식별을 평가한다.')
    replace('표 5의 기존 기준은',
        '표 5의 기존 기준은 E1≤0.02 dB와 E2≥0.10 dB다. 확정 정답 비율은 21.1%에서 26.7%로 5.6%p 늘었으나 73.3%는 보류했다. 기존 정답 손실 없이 128건을 추가했지만 큰 환경·모델 오차는 계속 보류했다. 잔차·간격·비율만으로도 전체 기준과 판정이 같아 대조·재검사의 추가 이점은 입증되지 않았다. 새 기준에는 재최적화 비용이 들며 관찰 오진 0건은 미래 무오진의 보장이 아니다.')
    replace('주 비교의 구조 holdout은',
        '구조 holdout은 같은 회로의 새 6고장×3회 반복이다. Blind에도 누락 부품명·RFAULT1·저항·포트 단서가 남아 일반적 원인 추론 능력을 뜻하지 않는다. 후속 탐색은 앞선 결과를 보고 설계했고 주 결과와 합산하지 않으며 반복 행은 독립 회로가 아니다. 손실·오차는 합성이며 과거값 역추정은 단일 값 변화 가정이다. 실제 부품값 확보·PCB/RFIC·온도·비선형성·통계적 오류 보증은 미검증이다.')
    replace('독립 SPICE 검증은',
        '주입 정답과의 진단 대조 및 독립 SPICE 성능 판정으로 복구 성공과 원인 진단의 불일치를 확인했다. 시험한 조건에서 동일 최대 호출 예산의 피드백 우위와 수치 기준선 대비 LLM의 추가 기여는 확인되지 않았다. 경험적 보류 기준 보정은 작은 값 변화의 확정 진단을 늘렸지만 큰 모델 오차는 해결하지 못했다. 후속 연구는 현재 부품값의 불확실성 및 환경·모델 변화와 기존 진단 기법 대비 이점을 검증해야 한다.')
    # Keep the new section heading with its opening paragraph, not a lone line at the page foot.
    opening=find('손실·기생 성분을 추가한')
    props=opening.find('w:pPr',NS)
    if props is None:props=E.Element(q('pPr'));opening.insert(0,props)
    keep=props.find('w:keepLines',NS)
    if keep is None:keep=E.SubElement(props,q('keepLines'))
    keep.set(q('val'),'true')
    ref=find('[5]')
    for value in [
        '[6] S. Hałgas, "Diagnosis of Analog Circuits: The Problem of Ambiguity of Test Equation Solutions," Electronics, vol. 13, no. 4, Art. no. 684, 2024, doi:10.3390/electronics13040684.',
        '[7] Y. Geifman and R. El-Yaniv, "Selective Classification for Deep Neural Networks," in NIPS, 2017.'
    ]:
        p=deepcopy(ref);settext(p,value)
        for k in list(p.attrib):
            if k.endswith('}paraId'):del p.attrib[k]
        ref.addnext(p);ref=p
    parts['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
    with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    with ZipFile(SOURCE) as z:assert [n for n in parts if parts[n]!=z.read(n)]==['word/document.xml']
    manifest=dict(source_sha256=digest(SOURCE),output_sha256=digest(OUTPUT),replacements=changes,
        evidence_sha256=previous['evidence_sha256'],holdout_recount=counts,
        baseline_injected_states={'total':144,'PASS':88,'FAIL':56},
        rates_pct={'legacy':487/2304*100,'new':615/2304*100,'gain_pp':128/2304*100,'abstained':1689/2304*100},
        added_references=[{'id':6,'url':'https://www.mdpi.com/2079-9292/13/4/684','doi':'10.3390/electronics13040684'},
            {'id':7,'url':'https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html'}])
    (QA/'changes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(OUTPUT)

if __name__=='__main__':main()
