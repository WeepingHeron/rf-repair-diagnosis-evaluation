"""Report audited development findings and explain threshold design without changing gates."""
from collections import Counter
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from run_diagnosis_development import PP,OUT
from run_reference_robustness import read,digest,check
LABELS={'clean':'반올림만','noise':'잡음 σ=0.01 dB','drift_0.1pct':'비균일 L/C 변화 ±0.1%',
        'drift_0.5pct':'비균일 L/C 변화 ±0.5%','model_10pct':'비균일 모델 오차 ±10%','combined':'잡음+L/C+모델 결합'}


def main():
    p=read(PP);check(p);a=read(ROOT/'build/diagnosis_development_v1_audit/summary.json')
    assert a['complete'] and not a['issues'] and a['protocol_sha256']==digest(PP.read_bytes())
    assert a['summary_sha256']==digest((OUT/'summary.json').read_bytes())
    rows=[]
    for f,h in a['row_sha256'].items():
        path=ROOT/f;assert digest(path.read_bytes())==h;rows.append(read(path))
    faults=[r for r in rows if r['kind']=='fault'];controls=[r for r in rows if r['kind']=='control']
    correct=sum(r['score']['correct'] for r in faults);hold=sum(r['score']['abstained'] for r in faults)
    wrong=sum(r['score']['wrong_diagnosis'] for r in faults);alarm=sum(r['score']['false_alarm'] for r in controls)
    rankwrong=[r for r in faults if not r['top_rank_correct']]
    bad=min([r for r in rankwrong if r['features']['second_rmse_db']>=.1],key=lambda r:r['features']['best_rmse_db'])
    control_bad=min([r for r in controls if r['features']['second_rmse_db']>=.1],key=lambda r:r['features']['best_rmse_db'])
    cleanhold=min([r for r in faults if r['family']=='clean' and r['score']['abstained']],key=lambda r:r['features']['best_rmse_db'])
    baseline={r['cohort_id']:r for r in a['baseline']};failed_controls=[r for r in a['baseline'] if r['kind']=='control' and r['verdict']=='FAIL']
    lines=['# 작은 값 변화와 비균일 오차: 개발 확인 및 보류 기준 설계','',
        '**보류 기준을 일괄 완화하면 안 되는 반례를 확인했다.** '
        f'고정된 기존 기준에서 주입 변화 {len(faults):,}건은 정답 {correct}, 보류 {hold:,}, 오진 {wrong}이었다. '
        f'최상위 부품·방향 후보가 틀린 {len(rankwrong)}건은 모두 보류됐다. 값 변화를 주입하지 않은 '
        f'대조군 {len(controls)}건의 단일 부품 오경보는 {alarm}이었다.','',
        '2026-09-06. API 0회, 별도 개발 집합 4설계·2,368행. 새 보류 기준을 선정하거나 적용하지 않았다. '
        '이전 945행과 합산하지 않으며 실측 성능·최종 holdout 결과가 아니다. '
        f'**기준 상태부터 규격 FAIL인 설계도 {len(failed_controls)}개 포함한다** '
        f'({", ".join(r["cohort_id"] for r in failed_controls)}). '
        '사전 계획대로 규격 만족 여부로 제외하지 않았다. 여기서 확인하는 것은 주입한 값 변화의 부품·방향이며, '
        '수리가 필요한 성능 불량 여부와 구별한다.','',
        '## 확인한 조건과 결과','',
        '127/173/217/269 MHz, BW 18/20/22/24%, 주 L/C 초기 공차 ±2%인 새 설계다. '
        '각 설계의 6개 주 부품 모두에 ±1/3/10% 변화를 각각 주입했다. '
        '주입 상태 144개와 무주입 상태 4개에 16개 프로파일을 적용했다. '
        '비균일 변화는 소자마다 다른 고정 난수를 사용하며, 모델 불일치는 각 소자의 Rs와 Cp/ESL에 따로 적용했다. '
        '[고정 계획](diagnosis_development_v1_protocol.md).','',
        '| 조건 | ±1% 변화 정답 | ±3% 변화 정답 | ±10% 변화 정답 | 최상위 후보 오답 | 확정 오진 | 대조군 오경보 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for family,label in LABELS.items():
        fs=[r for r in faults if r['family']==family];cs=[r for r in controls if r['family']==family]
        cell=[]
        for magnitude in [1,3,10]:
            g=a['groups'][family+'/'+str(magnitude)];cell.append(f'{g["correct"]}/{g["faults"]}')
        lines.append(f'| {label} | '+' | '.join(cell)+f' | {sum(not r["top_rank_correct"] for r in fs)}/{len(fs)} | '
            f'{sum(r["score"]["wrong_diagnosis"] for r in fs)} | {sum(r["score"]["false_alarm"] for r in cs)}/{len(cs)} |')
    lines += ['','정답이 아닌 주입 변화 응답은 모두 보류였다. clean은 설계·부품·방향별 1회, '
        '나머지는 3개 난수 draw다. 같은 설계·draw의 오차 벡터를 여러 주입 사례에 공유하므로 '
        '반복 행을 독립 설계 수로 간주하지 않는다.','',
        '| 설계 | 기준 회로 규격 | 주입 변화 진단 정답 | 최상위 후보 오답 |','|---|---|---:|---:|']
    for did in sorted({r['design_id'] for r in faults}):
        rs=[r for r in faults if r['design_id']==did]
        lines.append(f'| {did} | {baseline[did+"_control"]["verdict"]} | {sum(r["score"]["correct"] for r in rs)}/{len(rs)} | {sum(not r["top_rank_correct"] for r in rs)} |')
    counts=Counter((abs(r['change_fraction']),r['verdict']) for r in a['baseline'] if r['kind']=='fault')
    lines += ['','오차를 추가하기 전 native 규격 판정:','']
    for magnitude in [.01,.03,.1]:
        lines.append(f'- ±{magnitude*100:g}% 주입: PASS {counts[(magnitude,"PASS")]}, FAIL {counts[(magnitude,"FAIL")]}, 총 48상태.')
    lines += ['','따라서 ±1%의 위치 진단 실패를 모두 “성능 불량 회로의 수리 실패”로 부를 수 없다. '
        '기준 회로 FAIL 1개를 포함해, 성능 규격과 주입 변화 식별은 서로 다른 평가 축이다.','',
        '## 지금 보류 기준은 무엇인가','',
        '각 부품 하나가 달라졌다는 가설로 과거 측정값을 재현하고, 27개 dB 값의 RMSE를 구한다. '
        'E1은 가장 작은 RMSE, E2는 두 번째로 작은 RMSE다. 현재는 다음 두 조건을 **모두** 만족할 때만 '
        '최상위 부품과 방향을 확정한다.','',
        '```text','E1 ≤ 0.02 dB   AND   E2 ≥ 0.10 dB','하나라도 만족하지 못하면 component=unknown','```','',
        '첫 조건은 가장 좋은 설명도 측정과 잘 맞는지 검사한다. 두 번째는 다른 부품 가설도 비슷하게 '
        '측정을 설명하는지를 거른다. **현재 두 번째 조건은 E2 자체에 대한 문턱이며 E2−E1≥0.10 dB가 아니다.** '
        '두 수치는 거의 무오차·0.01 dB 반올림 조건에서 정한 가정이고, 실측 자료로 교정한 허용치나 '
        '99% 신뢰도 같은 확률을 뜻하지 않는다.','',
        '### 두 종류의 보류를 실제 사례로 보면','']
    for title,r in [('잘 맞는 후보가 있어도 차선 문턱에 걸린 사례',cleanhold),('모델·환경 오차 때문에 최상위 후보 자체가 틀린 사례',bad),('값 변화가 없는 대조군에도 부품 가설이 생기는 사례',control_bad)]:
        f=r['features'];top=r['fit']['hypotheses'][0]
        lines.append(f'- {title}: `{r["profile_id"]}/{r["cohort_id"]}`, 후보 {top["component"]}, '
            f'E0={f["no_change_rmse_db"]:.5f}, E1={f["best_rmse_db"]:.5f}, E2={f["second_rmse_db"]:.5f}, '
            f'간격={f["gap_db"]:.5f} dB. 현재 판정은 보류다.')
    bf=bad['features'];cf=control_bad['features']
    assert .02<bf['best_rmse_db']<=.1 and bf['second_rmse_db']>=.1
    assert .02<cf['best_rmse_db']<=.1 and cf['second_rmse_db']>=.1
    lines += ['',f'두 번째 사례의 E1={bf["best_rmse_db"]:.4f} dB, E2={bf["second_rmse_db"]:.4f} dB를 보면, '
        '**E1 문턱만 0.10 dB로 늘리면 기존 E2 조건도 통과해 오답을 확정하게 된다.** '
        '세 번째 대조군도 같은 완화에서 오경보가 된다. 이는 저장된 점수에 대한 논리적 반례이며 '
        '새 규칙을 채택하거나 전체 성능을 재평가한 결과는 아니다.','',
        '## 보류 기준을 정하는 순서','',
        '1. **오류의 비용과 평가 지표를 먼저 정한다.** 확정 진단 중 오진 비율, 무주입 대조군의 오경보 비율, '
        '확정 진단을 내리는 비율을 함께 본다. 전부 보류하면 오진은 0이지만 쓸모 있는 진단도 0이므로 '
        '오진만 최소화하지 않는다. 허용 오류 수준을 먼저 정하고 그 조건에서 진단 비율을 높이는 방향이다. '
        '이 관계는 선택적 예측의 risk–coverage 관점과 연결된다. '
        '[Geifman & El-Yaniv, 2017](https://arxiv.org/abs/1705.08500).','',
        '2. **기준 측정의 오차와 무고장 변화를 따로 추정한다.** 정상 상태 반복 측정, 자연적인 소자 변화, '
        '주파수 교정·모델 불일치가 만드는 잔차를 개발 자료에서 확인한다. 소자·채널별 오차가 다르면 '
        '오차 크기로 정규화하거나 공분산을 반영한 잔차를 검토할 수 있다. 지금 정규 dB 잡음은 계측 자료가 아니므로 '
        '그대로 장비의 허용치로 쓰지 않는다.','',
        '3. **설명 적합성·후보 분리·변화 증거를 함께 검사하는 규칙을 만든다.** 예를 들어 E1이 오차 범위 안인지, '
        'E2−E1 간격이 충분한지, 단일 고장 가설이 무고장·자연변화 가설보다 충분히 나은지를 본다. '
        '현재 기록한 E0−E1은 참고 특징이다. E0는 drift까지 설명한 무고장 모형이 아니므로, 이 값이 크다는 '
        '이유만으로 고장을 확정하면 안 된다. 위의 대조군에서도 개선량이 컸다. 작은 측정 섭동에 후보가 자주 '
        '바뀌면 보류하는 안정성 기준도 개발 자료에서 검토할 수 있다.','',
        '4. **개발·보정·최종 평가를 설계 단위로 분리한다.** 개발 자료로 규칙 형태를 정하고, 별도 보정 자료로 '
        '숫자를 정한 후 동결한다. 새로운 설계의 최종 평가에서는 숫자를 바꾸지 않고 진단 비율·오진·오경보를 '
        '보고한다. 같은 회로의 난수 반복을 양쪽에 나눠 놓으면 설계가 누설될 수 있다. 유한 표본의 불확실성도 '
        '고려해야 하므로 4설계의 2,368행만으로 작은 오류 확률을 보장하지 않는다.','',
        '**현재 제안은 기준 설계 절차이며, 새 숫자를 확정한 것은 아니다.** 이번에는 기존 0.02/0.10 dB를 '
        '유지했다. 먼저 소자·측정 오차를 허용하는 무고장 모형과 작은 변화의 구분 가능성을 개선해야 한다. '
        '후보 순위가 틀리는 조건에서는 잔차 문턱 완화만으로 문제를 해결할 수 없다.','',
        '## 검증 기록','',
        f'- 입력·가설·점수 {a["rows"]:,}건을 전부 재생성·재실행. fit 전방 계산 {a["fit_forward_evaluations"]:,}회, 무변화 가설 계산 2,368회.',
        f'- 고유 과거 회로와 baseline 상태를 합친 native sweep {a["native_sweeps"]}개, 전체 {a["native_frequency_points"]:,}주파수 점을 ABCD와 대조.',
        f'- 독립 nodal로 생성 회로 {a["nodal_generation_points"]:,}점과 E0/E1/E2의 {a["nodal_feature_points"]:,}점을 검증. 반올림·잡음 측정값 {a["independent_measurements"]:,}개 재계산.',
        f'- 최대 native 크기 차이 {a["max_native_magnitude_error"]:.3g}, nodal 크기 차이 {a["max_nodal_magnitude_error"]:.3g} (각 한계 2e-7). 특징 재계산 차이 {a["max_feature_difference"]:.3g} (한계 1e-7).',
        '- 단위 검사 74개 통과. 기존 실험 입력·코드·문턱과 제출 원고는 보존.','',
        '**검증 판단: 개발 실험과 한계를 명시하면 공유 가능.** 미해결 계산 불일치는 없지만, '
        '4설계·3난수 draw, 주 값이 정확히 알려진 단일 주입 변화와 제한적 모형이라는 한계가 있다. '
        '기준 상태가 규격을 만족하지 않는 설계도 포함했다. 이번 자료는 규칙을 만드는 개발 근거이며 '
        '최종 일반화 성능이나 실제 장비의 오경보 보증으로 사용할 수 없다.','',
        '```bash','.venv/bin/python scripts/run_diagnosis_development.py','.venv/bin/python scripts/audit_diagnosis_development.py',
        '.venv/bin/python scripts/report_diagnosis_development.py','```','',
        '고정 계약: `experiments/diagnosis_development_v1.json`. 원시 결과: `build/diagnosis_development_v1/`. '
        '감사·반례·native 증거: `build/diagnosis_development_v1_audit/summary.json`.','']
    path=ROOT/'docs/diagnosis_development_v1_results.md';path.write_text('\n'.join(lines));print(path)

if __name__=='__main__':main()
