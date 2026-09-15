"""Minimal package edit of the verified KIPS manuscript; preserve the input."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from copy import deepcopy
import hashlib
import json
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'submission/ACK2026_2026-09-06/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
OUTPUT = ROOT / 'submission/ACK2026_2026-09-06_v4/ACK2026_KimTaehoon_RF_Circuit_Repair.docx'
analysis = json.loads((ROOT / 'build/experiments/budget_transfer_v4/independent_analysis.json').read_text())
assert analysis['complete'] and analysis['completed_trajectories'] == 72
assert analysis['conditions']['no_feedback']['success_at_3'] == 33
assert analysis['conditions']['feedback']['success_at_3'] == 31
assert analysis['offline_audit']['unique_response_ids'] == 97
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
def q(s): return '{' + W + '}' + s
def text(p): return ''.join(p.xpath('.//w:t/text()', namespaces=NS))
def settext(p, value):
    old = p.find('w:r', NS)
    run = deepcopy(old) if old is not None else E.Element(q('r'))
    for child in list(run):
        if child.tag != q('rPr'): run.remove(child)
    E.SubElement(run, q('t')).text = value
    for child in list(p):
        if child.tag != q('pPr'): p.remove(child)
    p.append(run)

with ZipFile(SOURCE) as z: parts = {name: z.read(name) for name in z.namelist()}
root = E.fromstring(parts['word/document.xml'])
body = root.find('w:body', NS)
paragraphs = body.findall('w:p', NS)
sample = next(p for p in paragraphs if text(p).startswith('실험 회로는'))
def paragraph(value):
    p = deepcopy(sample); settext(p, value); return p
for p in root.findall('.//w:p', NS):
    t = text(p)
    if t.startswith('본 연구는 기존 RF 회로에'):
        t = t.replace('본 결과는 이상적', '새 설계 4개의 12개 값 고장을 조건별 3회 반복한 동일 최대 3회 호출 비교에서는 무피드백 33/36, 피드백 31/36으로 피드백의 복구율 향상을 확인하지 못했다. 본 결과는 이상적')
        settext(p, t)
    if t.startswith('본 연구는 제한된 수정과 독립 SPICE'):
        settext(p, '본 연구는 제한된 수정과 독립 SPICE 검증을 결합하여 원인 진단과 기능 복구, 인터페이스 실패와 수치 추론 실패를 분리 평가했다. 반복 실행의 추가 복구는 관찰했으나 새 설계의 동일 최대 호출 예산 비교에서는 피드백 우위가 확인되지 않았다. 따라서 복구 증가를 피드백의 인과적 효과로 단정할 수 없다. 향후 수치 계산 보조와 다른 matching network로 평가를 확장한다.')
    if t.startswith('본 연구는 하나의 이상적 필터 topology'):
        settext(p, t.replace('holdout도 같은 회로의 새 고장 조합이며', '구조 holdout은 같은 회로의 새 고장 조합이며') + ' 새 설계 비교도 같은 topology의 파라미터 전이이고, 72회는 12개 고장의 반복·조건별 실행이므로 독립 회로 표본으로 해석하지 않는다.')

anchor = next(p for p in paragraphs if text(p) == '실험 결과')
setup = paragraph('추가 비교에서는 중심주파수 83·117·149·173 MHz와 대역폭 비율 10·12·14·16%의 새 설계에서 값 고장 12개를 만들고 부품·노드 이름과 행 순서를 바꿨다. 두 조건은 최초 입력, 모델, 스키마, 출력 상한 2000토큰, 최대 3회 호출을 공유한다. 무피드백은 매번 최초 입력만 받고 피드백은 이전 실패 제안과 측정 결과를 받는다. 정상 PASS·고장 FAIL·정답 수정 PASS를 사전 확인한 뒤 3회씩 반복했다. 새 통과대역 경계의 S21 기준은 −4 dB로 별도 고정했으며, 성공 시 조기 종료하고 응답 미완료도 실패 분모에 포함했다.')
anchor.addprevious(setup)
caption = deepcopy(next(p for p in paragraphs if text(p).startswith('<표 1>')))
settext(caption, '<표 4> 새 설계의 동일 최대 호출 예산 비교')
table = deepcopy(body.findall('w:tbl', NS)[1])
rows = table.findall('w:tr', NS)
for row in rows[3:]: table.remove(row)
values = [['조건', '첫 복구', '최종 복구', '호출'], ['무피드백', '28/36', '33/36', '46'], ['피드백', '28/36', '31/36', '51']]
for row, vals in zip(table.findall('w:tr', NS), values):
    for cell, value in zip(row.findall('w:tc', NS), vals):
        ps = cell.findall('w:p', NS)
        settext(ps[0], value)
        for p in ps[1:]: cell.remove(p)
explanation = paragraph('표 4에서 첫 복구는 두 조건 모두 28/36이었다. 재시도에서 무피드백은 5건, 피드백은 3건을 추가 복구하여 최종 복구는 각각 91.7%와 86.1%였다. 최종 위치·방향 진단은 30/36과 32/36으로 복구와 다른 양상을 보였다. 무피드백에는 응답 미완료 1건과 성능 미복구 2건, 피드백에는 성능 미복구 5건이 포함된다. 피드백은 더 긴 후속 입력과 51회 호출을 사용하므로 실제 토큰·비용이 같은 실험은 아니다. 응답 97개와 후보 96개의 재시뮬레이션으로 기록을 검증했다.')
limit = next(p for p in paragraphs if text(p) == '한계 및 결론')
for element in [caption, table, explanation]: limit.addprevious(element)
parts['word/document.xml'] = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as z:
    for name, data in parts.items(): z.writestr(name, data)
with ZipFile(SOURCE) as z:
    assert [n for n in parts if parts[n] != z.read(n)] == ['word/document.xml']
print(json.dumps({'output': str(OUTPUT), 'sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}, ensure_ascii=False))
