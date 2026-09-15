"""Derive a core manuscript, then add only evidence directly testing its claim."""
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import json
from lxml import etree as E
from update_paper_diagnosis import ROOT, NS, q, txt, settext, digest
from update_paper_evidence import paired_evidence

SOURCE = ROOT/'submission/ACK2026_2026-09-07_fonts/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
QA = ROOT/'build/paper_focus'

def build(stage):
    assert digest(SOURCE)=='70ed75b6d207bee94aa647c0b83d9a8b5b56e3ec703695cbac92ce15ea911fa7'
    counts, rows, evidence = paired_evidence()
    with ZipFile(SOURCE) as z:
        parts={n:z.read(n) for n in z.namelist()}
    root=E.fromstring(parts['word/document.xml']);body=root.find('w:body',NS)
    def get(prefix):
        items=[p for p in root.findall('.//w:p',NS) if txt(p).startswith(prefix)]
        assert len(items)==1,(prefix,len(items))
        return items[0]
    heading=get('서론');paragraph=get('LLM 회로 자동화 연구는')
    def prose(value):
        p=deepcopy(paragraph);settext(p,value);return p
    def head(value):
        p=deepcopy(heading);settext(p,value);return p
    def result_table(prefix,new_caption):
        p=get(prefix);table=p.getnext();assert table.tag==q('tbl')
        cap=deepcopy(p);settext(cap,new_caption)
        return [cap,deepcopy(table)]
    abstract=('본 연구는 합성 단일 고장이 주입된 집중소자 RF 회로에서 LLM의 성능 복구와 원인 진단을 같은 실행에서 분리 평가한다. '
        '진단은 주입 위치·유형과 대조하고, 복구는 수정 후 독립 SPICE 성능 제약 충족으로 판정한다. '
        '100 MHz 필터의 16고장×3회 실행에서 둘 다 성공 35회, 복구만 성공 11회, 진단만 성공 2회였다. '
        '복구만 성공한 11회는 위치 오진 3회와 위치 정답·유형 오진 8회로 나뉜다. ')
    if stage=='supported':
        abstract+=('별도 손실 모델 탐색에서도 수치 후보를 받은 LLM은 16/16을 복구했지만 위치·방향 진단은 8/16이었다. ')
    abstract+=('따라서 기능 복구 성공률만으로 원인 진단을 평가할 수 없으며, 두 결과를 함께 보고해야 한다. 결과는 제한된 합성 회로 조건에 한정된다.')
    settext(get('본 연구는 합성 단일 고장이'),abstract)
    settext(get('키워드:'),'키워드: LLM, 집중소자 RF 회로, 성능 복구, 원인 진단, SPICE 검증')
    # Reuse exact source sections, typography, title block, figure, and result tables.
    front=[deepcopy(body[0]),deepcopy(body[1])]
    blocks=[head('서론'),prose(
        'LLM을 이용한 회로 자동화는 SPICE 생성[1], RF 필터 설계[2], 회로의 오류 탐지·교정[3]으로 확장되고 있다. '
        '그러나 수정한 회로가 요구 성능을 만족하더라도 고장 원인을 올바르게 설명했다고 볼 수 있는지는 별도의 질문이다. '
        '본 연구는 같은 실행에서 주입 정답과의 진단 일치, 수정 후 RF 성능을 교차 집계하여 복구 성공률에 가려지는 진단 오류를 확인한다.'),
        head('문제 정의 및 평가 절차'),prose(
        '그림 1은 진단과 복구의 두 평가 경로를 나타낸다. 정상 회로에 단일 고장을 주입하고 LLM에는 현재 netlist·목표 사양·시뮬레이션 결과를 제공한다. '
        '진단은 의심 부품과 고장 유형을 비공개 주입 정답과 대조한다. 복구는 제한된 수정을 적용한 뒤 ngspice에서 성능 제약을 모두 만족하는지 독립 판정한다. '
        '주입 정답은 LLM 입력과 실패 피드백에 제공하지 않는다.'),
        deepcopy(get('(그림 1)').getprevious()),deepcopy(get('(그림 1)')),prose(
        '실행기는 set_value, restore_component, set_port_impedance만 허용하고 임의 netlist 재작성을 금지한다. '
        '실패 시 최대 3회까지 수정안을 시도한다. 위치 진단, 위치와 유형을 모두 맞힌 전체 진단, 성능 복구를 각각 채점하고 최종 실행 단위로 교차 집계한다.'),
        head('실험 설정'),prose(
        '대상은 50 Ω 포트를 갖는 이상적 집중소자 100 MHz 3차 Butterworth 대역통과 필터이다. '
        '값 고장 10종과 open·short·임피던스 고장 6종을 각각 3회 실행해 총 48회를 평가했다. '
        'LLM은 gpt-5.6-luna, reasoning effort low로 고정했다. API 자동 재시도를 끄고 모든 실패를 분모에 포함했다. '
        '이 분석은 사전 고정한 strict 인터페이스의 주 결과에 한정하며, 결과 확인 후 수정한 인터페이스의 점수는 합산하지 않는다.'),
        deepcopy(get('복구 제약은 중심주파수')),
        head('실험 결과')]
    blocks+=result_table('<표 2>','<표 1> 고장군별 복구와 원인 진단 결과')
    blocks+=result_table('<표 3>','<표 2> 주 실험 48회의 복구와 전체 진단 교차 결과')
    blocks+=[prose(
        '표 1의 성능 복구는 46/48, 위치 진단은 45/48, 전체 진단은 37/48이다. '
        '표 2는 같은 48회의 최종 출력을 교차 집계한 결과로, 새로운 실험 분모가 아니다. '
        '둘 다 성공한 실행은 35회, 복구만 성공한 실행은 11회, 진단만 성공한 실행은 2회였고 둘 다 실패한 실행은 없었다.'),
        prose('복구만 성공한 11회 중 3회는 L2 고장을 C2 조정으로 보상한 위치 오진이었다. '
        '나머지 8회는 위치는 맞았지만 유형이 틀렸다. 다른 부품의 보상 수정이나 잘못된 유형 판단을 포함해 성능 제약을 만족할 수 있으므로, '
        '복구 성공을 원인 식별 성공으로 치환할 수 없다. 반대로 진단 정답 2회도 복구에 실패해, 진단 정답만으로 실행 가능한 수정의 성공을 보장하지 못했다.')]
    if stage=='supported':
        blocks += [head('손실 모델에서의 보조 확인'),
            prose('주 결과와 별도로, 손실·기생 성분을 포함한 회로에서도 복구와 진단의 불일치가 관찰되는지 탐색했다. '
            '정상 상태의 사양 충족을 확인한 손실 보상 설계 4개에 값 고장 8개를 주입했다. '
            'L의 직렬 R=0.05 Ω·병렬 C=0.1 pF, C의 직렬 R=0.02 Ω·ESL=0.2 nH를 사용했다. '
            '중심 손실≤2 dB, 반사손실≥15 dB, peak 오차≤3%, 통과대역 경계 S21≥−6 dB와 저지대역 S21≤−12 dB의 별도 사양을 적용했다.'),
            prose('수치 탐색은 8/8을 복구했다. 같은 후보를 받은 LLM은 고장별 2회, 총 16/16을 복구했으나 위치·방향 진단은 8/16이었다. '
            'LLM은 16번 모두 수치 탐색의 최상위 후보를 그대로 선택했다. 이 조건에서도 복구 성공이 정확한 진단을 뜻하지 않았으며, '
            '수치 탐색 대비 LLM의 추가 복구 이점은 확인되지 않았다. 이 탐색은 후보와 사양이 주 실험과 다르고 유형 대신 위치·방향을 평가하므로 '
            '주 실험의 48회와 합산하거나 동일한 진단 지표로 직접 비교하지 않는다.')]
    blocks += [head('한계 및 결론'),prose(
        '주 실험은 하나의 이상적 필터와 합성 단일 고장에 한정된다. 48회는 16고장의 반복 실행이며 독립적인 회로 48개가 아니다. '
        '구조 고장의 Blind 조건에서도 누락 부품명·RFAULT1·저항·포트 단서가 남아, 결과를 일반적인 고장 원인 추론 능력으로 확대할 수 없다. '
        +('손실 모델 확인은 앞선 결과를 보고 설계한 탐색이며 수치 후보 제공 조건에 한정된다. ' if stage=='supported' else '')+
        '실제 PCB/RFIC·하드웨어 측정·온도·비선형성에 대한 검증은 수행하지 않았다.'),prose(
        '주입 정답과 SPICE 성능을 같은 실행에서 대조한 결과, 성능 복구 성공에는 위치·유형 오진이 포함됐고 진단 정답에도 복구 실패가 존재했다. '
        '따라서 LLM 회로 복구 평가는 복구율과 진단 정확도를 별도로 보고하고 두 결과의 교차 분포와 보상 수정 사례를 함께 제시해야 한다. '
        '후속 검증은 다양한 회로와 실제 측정 조건에서 이 불일치가 유지되는지 확인하는 데 초점을 둔다.'),
        deepcopy(get('참고문헌'))]
    for old,new in [(1,1),(2,2),(4,3)]:
        ref=deepcopy(get(f'[{old}]'));settext(ref,txt(ref).replace(f'[{old}]',f'[{new}]',1));blocks.append(ref)
    section=deepcopy(body.find('w:sectPr',NS))
    for c in list(body):body.remove(c)
    body.extend(front+blocks+[section])
    parts['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    QA.mkdir(parents=True,exist_ok=True)
    output=QA/f'ACK2026_RF_{stage}.docx'
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        for n,data in parts.items():z.writestr(n,data)
    report=dict(stage=stage,source=str(SOURCE),source_sha256=digest(SOURCE),output=str(output),output_sha256=digest(output),
        result_tables=2,references=3,primary_joint=counts,primary_rows=rows,evidence_sha256=evidence,
        removed_experiments=['one_shot_conditions','interface_development_holdout','budget_transfer',
        'resonance_assistance','matching_network','reference_diagnosis','abstention_calibration'],
        added_direct_support=stage=='supported',character_count=len(txt(root)))
    (QA/f'{stage}_changes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['stage','output','output_sha256','character_count']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['core','supported'],required=True)
    build(parser.parse_args().stage)
