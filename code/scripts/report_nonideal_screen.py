"""Produce the condition-screen readout only from complete independently audited evidence."""
import json
from pathlib import Path
from run_nonideal_screen import sha

ROOT=Path(__file__).resolve().parents[1]

def main():
    pp=ROOT/'experiments/nonideal_screen_v1.json'
    audit=json.loads((ROOT/'build/nonideal_screen_v1_audit/summary.json').read_text())
    assert audit['complete'] and not audit['issues'] and audit['protocol_sha256']==sha(pp.read_bytes())
    protocol=json.loads(pp.read_text())
    for p,h in protocol['file_sha256'].items(): assert sha((ROOT/p).read_bytes())==h
    rows=audit['conditions']; s=audit['summary']
    lines=['# 유한 Q·기생 성분·공차 조건 확인 결과', '',
        '기존 성능 기준을 유지한 새 BPF 설계 4개의 320개 조건 중 정상 상태 PASS는 **8/320**이었다. '
        '유한 Q 조건에서는 정상 PASS가 없었다. 현재의 이상적 설계값과 성능 기준을 그대로 두고 '
        '비이상적 LLM 복구 비교로 넘어가는 것은 적절하지 않다.', '',
        '실행·검증일: 2026-09-06. 합성 모델의 적용 범위 확인이며 실측·제품 검증이 아니다. '
        'API 호출은 0회다. 기존 논문과 v4/v5/정합 실험의 고정 파일을 보존했다.', '',
        '## 1. 무엇을 확인했는가', '',
        '103/139/167/211 MHz, 상대 대역폭 12/14/16/18%의 미사용 설계 4개에서 '
        'Q=무손실/200/100/50, 기생 성분 off/on, 공차 0/1/3/5%를 평가했다. '
        '공차가 있는 조건은 고정 난수 3회이며 0%는 1회다. 모든 320조건과 640고장 조건을 보존했다. '
        '조건당 정상·고장 2종·oracle 2종을 시뮬레이션했다.', '',
        'L과 C에 같은 명목 Q를 적용한 고정 직렬 저항 모델이다. L의 Cp=0.1 pF와 C의 '
        'ESL=0.2 nH를 함께 켰다. 각 숫자는 Assumed/Synthetic이며 특정 부품에서 측정한 값이 아니다. '
        '저항은 명목 f₀와 부품값에서 한 번 계산하고 공차·고장·수정 후에도 고정했다. '
        '고장은 주 L/C 값만 0.55배 또는 1.8배로 바꾸며 oracle은 고장 직전의 공차 포함 값으로 복원한다.', '',
        '중심 S21≥−0.25 dB, S11≤−20 dB, peak 주파수 오차≤2% 등 기존 7개 제약을 유지했다. '
        '정상 FAIL은 현재 설계가 기준을 만족하지 않는다는 뜻이며 모든 재설계의 불가능성을 증명하지 않는다. '
        '정상 FAIL을 복구 알고리즘 실패로 세지 않았다. [고정 계획](nonideal_screen_v1_protocol.md).', '',
        '## 2. 정상 회로부터 기존 기준을 만족하는가', '',
        '아래 표는 공차 0%의 설계 4개씩이다. 중심 손실은 −S21이며 수치 반올림으로 −0.00 dB가 나오면 0으로 표시했다.', '',
        '| 명목 Q | 기생 성분 | 정상 PASS /4 | 중심 손실 범위 (dB) |',
        '|---|---|---:|---:|']
    for q in [None,200,100,50]:
        for p in [False,True]:
            group=[r for r in rows if r['q']==q and r['parasitics']==p and r['tolerance']==0]
            loss=[max(0,-r['center_s21_db']) for r in group]
            lines.append(f'| {q or "무손실"} | {"on" if p else "off"} | {sum(r["healthy_pass"] for r in group)} | {min(loss):.3f}–{max(loss):.3f} |')
    lines += ['', 'Q=200, 기생 off, 공차 0%에서도 중심 손실은 0.965–1.446 dB다. '
        '이미 기존 0.25 dB 한계를 넘는다. 유한 Q의 전체 240조건에서는 정상 PASS가 0이었다.', '',
        '무손실·기생 on·공차 0%의 중심 손실은 약 0.10 dB이지만, peak 이동 4.4–6.1%, '
        '중심 정합 및 상측 통과대역 조건 때문에 4개 모두 탈락했다. 손실만 완화해도 모든 문제가 해결되는 것은 아니다. '
        '이번 기생 on은 Cp/ESL을 함께 켠 조건이므로 어느 하나의 독립 효과로 해석하지 않는다.', '',
        '공차만 추가한 무손실·기생 off 조건:', '',
        '| 공차 폭 | 정상 PASS /조건 수 | 평가 가능한 고장 수 | 결정적 공진 복구 /평가 가능 고장 |',
        '|---|---:|---:|---:|']
    for t in [0,.01,.03,.05]:
        group=[r for r in rows if r['q'] is None and not r['parasitics'] and r['tolerance']==t]
        eligible=sum(r['eligible'] for r in group); recovered=sum(r['recovered'] for r in group)
        lines.append(f'| ±{t*100:g}% | {sum(r["healthy_pass"] for r in group)}/{len(group)} | {eligible} | {str(recovered)+"/"+str(eligible) if eligible else "평가 대상 없음"} |')
    lines += ['', '3회 공차 표본은 제조 수율이나 최악 조건을 추정하기에 부족하다. '
        '또한 320개는 4개 설계의 반복 조건이며 독립 회로 320개가 아니다.', '',
        '## 3. 정상 기준을 통과한 조건에서의 복구', '',
        f'정상 PASS·고장 FAIL·정확한 단일 값 oracle PASS인 고장은 {s["eligible_faults"]}/640이었다. '
        f'관측 회로의 주 L/C 연결과 현재값으로 계산한 결정적 기준선은 {s["baseline_recovered"]}/{s["eligible_faults"]}을 '
        f'{s["baseline_simulations"]}회 후보 시뮬레이션으로 복구했다. '
        '이 중 완전 이상적·공차 0%는 8/8이고, 공차가 있는 적격 고장은 2/8이다. '
        '나머지 624개는 정상 설계가 FAIL이므로 복구율 분모에서 제외하되 원본 기록과 정상 탈락 표에는 포함했다.', '',
        '기준선은 주 회로의 공개 연결 정보를 사용해 기생 소자로 인한 파서 누락을 피했고, '
        '후보 순서는 공진 오차와 부품명으로 고정했다. 정상값·정답 부품을 제공하지 않았다. '
        '최대 3후보 중 먼저 성공하면 종료하며 각 후보는 최초 고장 회로의 주 L/C 한 값만 수정한다. '
        '기생값·손실 R·포트는 그대로다.', '',
        '공차 조건의 실패 6건도 oracle 복원은 PASS다. 따라서 이 6건은 단일 값으로 복구 가능한 '
        '문제에서 이상적 공진 후보의 계산 또는 순위/3회 예산이 충분하지 않았다는 관찰이다. '
        'LLM을 실행하지 않았으므로 LLM이 이를 해결하거나 더 우수하다고 주장할 수 없다.', '',
        '## 4. 검증', '',
        f'- SPICE 기록 {audit["records"]:,}개: 정상 320 + 고장 640 + oracle 640 + 후보 28.',
        f'- 원본 주파수 표 {audit["raw_frequency_points"]:,}행의 전체 S11/S21/S22를 별도 복소 임피던스·ABCD 계산과 비교했다.',
        f'- S-parameter 크기 최대 절대 차이 {audit["max_absolute_sparameter_magnitude_error"]:.3g}; 허용 한계 2e-7 이내.',
        f'- 공차 0%의 전체 Q×기생×설계 셀 {audit["fresh_ngspice_replays"]}개를 새 ngspice 실행으로 재검증했다.',
        '- 고정 hash, 전체 조건 누락/중복, 수정 회로, 원본 표→metric, 7개 판정, 후보 순서, 적격 분모와 집계에서 불일치 없음.', '',
        '원시 기록: `build/experiments/nonideal_screen_v1/`. 독립 감사: '
        '`build/nonideal_screen_v1_audit/summary.json`. 전체 그리드와 수치는 감사 JSON의 conditions에 있다.', '',
        '```bash', '.venv/bin/python scripts/run_nonideal_screen.py',
        '.venv/bin/python scripts/audit_nonideal_screen.py', '.venv/bin/python scripts/report_nonideal_screen.py', '```', '',
        '## 5. 다음 실험의 우선순위', '',
        '1. 유한 Q 비교 전에 손실을 포함한 정상 설계를 만들고, 용도에 근거한 삽입 손실·정합·대역 기준을 '
        '사전에 정한다. 기존 −0.25 dB 결과를 나중에 완화해 같은 실험의 성공으로 바꾸지 않는다.',
        '2. L/C Q와 Cp/ESL의 효과를 분리하고, 실제 부품 모델을 쓸 경우 출처와 사용 조건을 고정한다. '
        '정상 설계와 oracle의 통과를 먼저 확인한다.',
        '3. 그다음 새 미사용 공차 사례에서 이상적 공진 계산, 기생/공차를 고려한 수치 탐색, '
        '계산 보조 LLM을 같은 후보 평가 예산으로 비교한다. 이번에 본 6실패는 개발·분석용으로만 쓴다.', '',
        '**검증 판단: 한계를 명시하면 공유 가능.** 결과는 고정한 합성 모델과 작은 공차 표본 안에서 재현된다. '
        '전 제조사·실측 회로·현실 RF 복구율로 일반화할 수 없다. 이번 결과로 제출 원고의 실험 분모를 늘리거나 '
        'LLM 우위를 추가하지 않았다.', '',
        '모델 형태의 참고: [Coilcraft Q·자체 공진 설명](https://www.coilcraft.com/en-us/resources/application-notes/testing-inductors-at-application-frequencies/), '
        '[Murata ESR/ESL 등가 모델](https://article.murata.com/en-eu/article/impedance-esr-frequency-characteristics-in-capacitors). '
        '여기서 사용한 수치 자체는 제조사 보증치가 아니다.', '']
    path=ROOT/'docs/nonideal_screen_v1_results.md'; path.write_text('\n'.join(lines)); print(path)

if __name__=='__main__': main()
