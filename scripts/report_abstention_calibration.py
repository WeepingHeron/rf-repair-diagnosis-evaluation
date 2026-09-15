"""Report calibrated multi-gate criteria, independent evaluation and active scope."""
from collections import Counter
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from run_abstention_calibration import PP,POLICY,OUT
from run_reference_robustness import read,digest,check
LABELS={'clean':'반올림만','noise':'잡음 σ=0.01 dB','drift_0.1pct':'비균일 L/C 변화 ±0.1%',
    'drift_0.5pct':'비균일 L/C 변화 ±0.5%','model_10pct':'비균일 모델 오차 ±10%','combined':'잡음+L/C+모델 결합'}


def main():
    p=read(PP);check(p);policy=read(POLICY);a=read(ROOT/'build/abstention_calibration_v1_audit/summary.json')
    assert a['complete'] and not a['issues'] and a['policy_sha256']==digest(POLICY.read_bytes()) and a['protocol_sha256']==digest(PP.read_bytes())
    for path,h in a['row_sha256'].items():assert digest((ROOT/path).read_bytes())==h
    held=[read(ROOT/path) for path in a['row_sha256'] if '/holdout/rows/' in path]
    checked=[r for r in held if r['bundle']['stability']]
    core_difference=0
    for r in held:
        f=r['bundle']['features'];q=policy['parameters']
        core=f['best_rmse_db']<=q['fit_max_db'] and f['gap_db']>=q['gap_min_db'] and f['separation_ratio']>=q['ratio_min']
        core_difference+=core!=(not r['new_result']['abstained'])
    smoke=read(ROOT/'build/abstention_calibration_v1_runtime_smoke/summary.json')
    assert smoke['complete'] and smoke['checks']==4 and smoke['policy_sha256']==a['policy_sha256']
    configpath=ROOT/'configs/diagnosis_abstention.json';active=False
    if configpath.exists():
        config=read(configpath);active=config['policy_sha256']==a['policy_sha256'] and config['status']=='ACTIVE_SYNTHETIC_VALIDATED'
    assert active==a['eligible_to_activate']
    t=a['results']['holdout']['totals'];ct=a['results']['calibration']['totals'];params=policy['parameters']
    oldhold=t['faults']-t['legacy_correct']-t['legacy_wrong']
    lines=['# 다중 보류 기준 보정·미사용 설계 평가와 적용','',
        f'**미사용 설계의 확정 정답이 기존 {t["legacy_correct"]}/{t["faults"]}에서 '
        f'{t["new_correct"]}/{t["faults"]}로 늘었다.** 새 기준의 관찰 오진은 {t["new_wrong"]}건, '
        f'무주입 대조군 오경보는 {t["new_false_alarm"]}/{t["controls"]}였다. '
        f'사전 적용 조건을 {"통과해 새 진단 명령의 기본 정책으로 연결했다" if active else "통과하지 못해 기본 활성화하지 않았다"}.','',
        '2026-09-06. API 0회. 개발 4설계, 별도 보정 4설계, 미사용 평가 4설계를 분리했다. '
        '보정·평가는 각각 2,368행(주입 변화 2,304 + 무주입 대조 64)이다. '
        '최종 평가 전에 정책을 고정했고 결과를 본 뒤 문턱을 다시 조정하지 않았다. '
        '같은 수동 BPF 구조의 합성 주입 변화 진단이며 실측 성능·수리 성공률·인구집단 오진 확률 보증은 아니다.','',
        '## 적용한 기준','',
        'E0는 현재값을 과거에도 쓴 무변화 가설의 RMSE, E1/E2는 최선/차선 부품 가설 RMSE다. '
        '다음 조건을 모두 만족할 때만 부품과 방향을 확정한다.','',
        '| 항목 | 보정 후 고정 기준 | 역할 |','|---|---|---|',
        f'| 측정 적합성 | E1 ≤ {params["fit_max_db"]:g} dB | 큰 모델·측정 오차를 허용해 오진이 통과하는 것을 억제 |',
        f'| 후보 간격 | E2−E1 ≥ {params["gap_min_db"]:g} dB | 서로 비슷한 부품 가설을 보류 |',
        f'| 후보 비율 | E2/max(E1, 0.01) ≥ {params["ratio_min"]:g} | 오차 크기에 비해 구분이 약한 후보를 보류 |',
        f'| 무고장 대조 | (E0−E1)/max(E1, 0.01) ≥ {params["null_score_min"]:.6f} | 보정 대조군보다 강한 변화 증거를 요구 |',
        '| 재검사 안정성 | 각 측정에 ±0.01 dB를 더한 4회 재최적화에서 부품·방향 4/4 일치 | 작은 입력 변화로 후보가 바뀌면 보류 |','',
        '0.01 dB는 분모가 너무 작아지지 않도록 둔 고정 바닥값이며 실측 분산 추정치가 아니다. '
        '무고장 대조 점수는 환경 변화까지 최적으로 적합한 물리적 무고장 모형이 아니라, '
        '여러 합성 nuisance가 있는 대조군의 경험적 점수 범위를 사용한다. 안정성 4/4도 확률적 신뢰도가 아니다.','',
        '## 숫자를 정한 방법','',
        '개발 자료에서 기준 형태를 정하고 36개 후보 격자를 사전 고정했다. '
        'τfit={0.01,0.015,0.02}, τgap={0.015,0.03,0.05,0.08}, τratio={3,5,10}이다. '
        f'보정 무주입 대조군 64건의 최대 T={policy["null_score_max"]:.6f}에 10% 여유를 더해 '
        f'τnull={params["null_score_min"]:.6f}로 정했다. 10%는 사전 설정한 경험적 여유이며 통계적 보증이 아니다.','',
        f'보정에서 관찰 오진 0·오경보 0인 후보 중 확정 정답 {ct["new_correct"]}건을 얻는 설정을 골랐다. '
        '동률이면 더 작은 τfit, 더 큰 τgap, 더 큰 τratio 순으로 선택했다. '
        '후보·대조 점수·결과와 정책 파일을 고정한 후에만 holdout을 실행하도록 코드에서 순서를 제한했다. '
        '[사전 계획](abstention_calibration_v1_protocol.md).','',
        '판단을 내리는 비율과 그 판단의 오류를 함께 보는 설계는 선택적 예측의 risk–coverage 관점과 연결된다. '
        '[Geifman & El-Yaniv, 2017](https://arxiv.org/abs/1705.08500). '
        '이번 구현은 그 논문의 확률적 보증 알고리즘을 적용한 것이 아니며, 설계 군집 4개만으로 낮은 모집단 오류율을 보장하지 않는다.','',
        '## 미사용 설계에서 기존 기준과 비교','',
        '| 지표 | 기존 E1≤0.02 & E2≥0.10 | 새 다중 기준 |','|---|---:|---:|',
        f'| 주입 변화 정답 | {t["legacy_correct"]}/{t["faults"]} | {t["new_correct"]}/{t["faults"]} |',
        f'| 주입 변화 보류 | {oldhold} | {t["new_abstained_faults"]} |',
        f'| 주입 변화 오진 | {t["legacy_wrong"]} | {t["new_wrong"]} |',
        f'| 무주입 대조군 오경보 | {t["legacy_false_alarm"]}/{t["controls"]} | {t["new_false_alarm"]}/{t["controls"]} |','',
        '| 조건 | 기존 정답 | 새 정답 | 분모 |','|---|---:|---:|---:|']
    groups=a['results']['holdout']['groups']
    for family,label in LABELS.items():
        gs=[v for k,v in groups.items() if k.startswith(family+'/')]
        lines.append(f'| {label} | {sum(g["legacy_correct"] for g in gs)} | {sum(g["new_correct"] for g in gs)} | {sum(g["faults"] for g in gs)} |')
    lines += ['','| 변화 크기 | 기존 정답 | 새 정답 | 분모 |','|---|---:|---:|---:|']
    for mag in [1,3,10]:
        gs=[g for k,g in groups.items() if k.endswith('/'+str(mag))]
        lines.append(f'| ±{mag}% | {sum(g["legacy_correct"] for g in gs)} | {sum(g["new_correct"] for g in gs)} | {sum(g["faults"] for g in gs)} |')
    pair=a['results']['holdout']['paired']
    lines += ['',f'같은 입력별 비교: 둘 다 정답 {pair.get("both_correct",0)}, 기존만 정답 {pair.get("legacy_only",0)}, '
        f'새 기준만 정답 {pair.get("new_only",0)}, 둘 다 비정답 {pair.get("neither_correct",0)}건이다. '
        '합계 차이만으로 모든 사례가 개선됐다고 해석하지 않는다.','',
        '확정 정답의 증가는 주로 반올림만 있거나 작은 잡음이 있는 조건에서 나타났다. '
        '큰 환경 변화·모델 불일치의 진단을 해결한 것은 아니다. 해당 조건을 계속 보류하면서 '
        '구분 가능한 작은 변화의 보류를 줄인 결과다.','',
        '## 평가 집합과 계산 비용','',
        '| 분할 | 설계 주파수 MHz | 기존 정답 | 새 정답 | 주입 변화 분모 | 대조군 분모 |','|---|---|---:|---:|---:|---:|',
        f'| 보정 | 133/179/227/283 | {ct["legacy_correct"]} | {ct["new_correct"]} | 2304 | 64 |',
        f'| 미사용 평가 | 147/193/251/307 | {t["legacy_correct"]} | {t["new_correct"]} | 2304 | 64 |','',
        '각 분할은 6개 주 부품×±1/3/10%와 무주입 상태를 대상으로 같은 16개 프로파일을 썼다. '
        '같은 설계·draw의 오차 벡터가 여러 행에 공유되므로 반복 행을 독립 회로 표본으로 보지 않는다. '
        '기준 회로 및 주입 후 성능 규격으로 제외하지 않는 진단 프로토콜을 유지했다.','']
    for split,label in [('calibration','보정'),('holdout','미사용 평가')]:
        bas=[r for r in a['baseline'] if r['split']==split];cs=[r for r in bas if r['kind']=='control'];fs=[r for r in bas if r['kind']=='fault']
        lines.append(f'- {label}: 기준 회로 PASS {sum(r["verdict"]=="PASS" for r in cs)}/4, '
            f'주입 144상태 중 규격 PASS {sum(r["verdict"]=="PASS" for r in fs)}·FAIL {sum(r["verdict"]=="FAIL" for r in fs)}. '
            '규격 판정으로 주입 상태를 제외하지 않았다.')
    for split,label in [('calibration','보정'),('holdout','미사용 평가')]:
        summ=read(OUT/split/'summary.json')
        lines.append(f'- {label}: 원본 fit {summ["original_fits"]:,}회 + 안정성 fit {summ["stability_fits"]:,}회, '
            f'fit 전방 계산 {summ["fit_forward_evaluations"]:,}회 + E0 계산 {summ["no_change_forward_evaluations"]:,}회.')
    lines += ['','기존 판정은 원본 fit에서 얻고, 새 기준은 추가 재최적화를 사용한다. '
        '따라서 동일 계산 예산 비교가 아니다. 어떤 후보도 통과할 수 없는 입력은 재검사를 생략하므로 '
        'STABILITY_NOT_CONFIRMED는 실제 흔들림과 재검사 미실행을 모두 포함한다.','',
        f'미사용 평가에서 재검사를 수행한 {len(checked)}건은 '
        f'{sum(r["bundle"]["stability_matches"]==4 for r in checked)}건 모두 4/4 후보가 일치했다. '
        f'고정된 점수에서 적합성·간격·비율만 적용한 판정과 전체 판정의 차이도 {core_difference}건이었다. '
        '따라서 이번 개선은 후보 구분 기준 변경에서 관찰됐으며, 무고장 대조와 안정성 조건의 추가 이점은 '
        '이 평가로 입증하지 못했다. 해당 조건을 일반적으로 불필요하다고 결론내리지는 않는다.','',
        '## 적용 및 재현','',
        f'적용 상태: **{"ACTIVE_SYNTHETIC_VALIDATED" if active else "NOT_ACTIVATED"}**. '
        '기존 실험 스크립트는 동결된 기준을 유지한다. 새 진단 명령은 원시 입력에서 fit·점수·재검사를 '
        '다시 계산하고, 정책 또는 입력을 읽거나 검증할 수 없으면 unknown으로 보류한다.','',
        '```bash','.venv/bin/python scripts/diagnose_reference.py --input input.json --output diagnosis.json','```','',
        '입력은 `source`, `public`, `reference` 세 필드를 가진 JSON 또는 실험 기록의 `estimator_input`이다. '
        '현재 주 값과 공용 등가모형이 주어진 기존 합성 회로 입력 계약을 사용한다. '
        'active 설정은 `configs/diagnosis_abstention.json`, 고정 정책은 `experiments/diagnosis_abstention_v1.json`이다. '
        'LLM 호출이나 회로 수정·수리 승인은 하지 않는다.','',
        '```bash','.venv/bin/python scripts/audit_abstention_calibration.py','.venv/bin/python scripts/activate_abstention_policy.py',
        '.venv/bin/python scripts/report_abstention_calibration.py','```','',
        '## 독립 검증과 한계','',
        f'- 보정·평가 {a["rows"]:,}행의 입력·점수·원본/재검사 fit {a["fit_count"]:,}회를 재실행하고, 36개 정책 후보와 선택 결과를 독립 계산.',
        f'- 고유 native sweep {a["native_sweeps"]}개, 전체 {a["native_frequency_points"]:,}주파수 점을 ABCD와 대조.',
        f'- 생성 회로 nodal {a["nodal_generation_points"]:,}점, E0/E1/E2 nodal {a["nodal_feature_points"]:,}점, 반올림·잡음 값 {a["measurements_recomputed"]:,}개 확인.',
        f'- 최대 native/ABCD 크기 차이 {a["max_native_magnitude_error"]:.3g}, nodal 크기 차이 {a["max_nodal_magnitude_error"]:.3g}; 허용 2e-7 미만.',
        '- 단위 검사 79개와 실제 CLI의 신규 확정·대조군·모델 불일치·잘못된 입력 4개 점검 통과. 기존 고정 실험과 제출 원고는 보존.','',
        '**검증 판단: 합성 적용 범위와 개발·보정·평가 분리를 명시하면 공유 가능.** '
        '추가 검증이 필요한 범위는 실제 측정의 오차 분포, 공차/온도 모형, 입력 주 값의 불확실성, 다른 topology와 '
        '보정 범위를 벗어난 분포다. 0건의 관찰 오류가 향후 오류 0을 뜻하지 않으며, 정책을 실제 장비에 '
        '적용하려면 장비별 대조군·측정 오차를 확보하고 별도 보정·검증을 거쳐야 한다.','',
        '원시 기록: `build/abstention_calibration_v1/`. 독립 감사: `build/abstention_calibration_v1_audit/summary.json`.','']
    dest=ROOT/'docs/abstention_calibration_v1_results.md';dest.write_text('\n'.join(lines));print(dest)

if __name__=='__main__':main()
