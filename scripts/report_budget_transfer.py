"""Independently aggregate the fixed v4 experiment; publish only complete data."""
import argparse
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def read(path):
    return json.loads(path.read_text())


def aggregate():
    protocol_path = ROOT / 'experiments/budget_transfer_v4.json'
    protocol = read(protocol_path)
    for name, expected in protocol['file_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    cases = read(ROOT / protocol['manifest'])['cases']
    output = ROOT / 'build/experiments/budget_transfer_v4'
    expected = {(condition, case['case_id'], repeat)
                for condition in protocol['conditions'] for case in cases
                for repeat in range(1, protocol['repetitions'] + 1)}
    trajectories, seen = [], set()
    for path in sorted(output.glob('*/*/repeat_*/final.json')):
        final = read(path)
        key = (final['condition'], final['case_id'], final['repetition'])
        assert key in expected and key not in seen
        seen.add(key)
        rows = [read(path.parent / f'iteration_{i}.json') for i in range(1, final['iterations'] + 1)]
        assert 1 <= len(rows) <= protocol['max_iterations']
        assert len(list(path.parent.glob('iteration_*.json'))) == len(rows)
        for i, row in enumerate(rows, 1):
            assert (row['condition'], row['case_id'], row['repetition'], row['iteration']) == (*key, i)
            if i < len(rows):
                assert not row['recovered'] and row['outcome'] != 'API_OR_SCHEMA_FAILURE'
        assert final['first_recovered'] == rows[0]['recovered']
        assert final['recovered'] == any(row['recovered'] for row in rows)
        assert final['localized'] == rows[-1]['localized']
        assert final['diagnosed'] == rows[-1]['diagnosed']
        case = next(c for c in cases if c['case_id'] == final['case_id'])
        successes = [r for r in rows if r['recovered']]
        compensated = bool(successes and successes[0]['proposal']['repair']['component'] != case['component'])
        trajectories.append({**final, 'design_id': case['design_id'], 'rows': rows,
                             'compensated_recovery': compensated})
    result = {'as_of_utc': datetime.now(timezone.utc).isoformat(),
              'protocol_sha256': hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
              'planned_trajectories': len(expected), 'completed_trajectories': len(seen),
              'complete': seen == expected, 'conditions': {}, 'case_results': []}
    for condition in protocol['conditions']:
        ts = [t for t in trajectories if t['condition'] == condition]
        rows = [r for t in ts for r in t['rows']]
        usage = [r.get('usage', {}) for r in rows]
        input_tokens = sum(u.get('input_tokens', 0) for u in usage)
        cached = sum(u.get('input_tokens_details', {}).get('cached_tokens', 0) for u in usage)
        cache_write = sum(u.get('input_tokens_details', {}).get('cache_write_tokens', 0) for u in usage)
        out_tokens = sum(u.get('output_tokens', 0) for u in usage)
        reasoning = sum(u.get('output_tokens_details', {}).get('reasoning_tokens', 0) for u in usage)
        price = protocol['api_prices_usd_per_million_tokens']
        cost = ((input_tokens - cached) * price['input'] + cached * price['cached_input']
                + out_tokens * price['output']) / 1e6
        historical_cost = cost
        cost += cache_write * price['input'] * .25 / 1e6
        first = sum(t['first_recovered'] for t in ts)
        final = sum(t['recovered'] for t in ts)
        result['conditions'][condition] = {
            'completed': len(ts), 'success_at_1': first, 'success_at_3': final,
            'additional_recoveries': final - first, 'localized': sum(t['localized'] for t in ts),
            'diagnosed': sum(t['diagnosed'] for t in ts),
            'compensated_recoveries': sum(t['compensated_recovery'] for t in ts),
            'api_calls': len(rows), 'candidate_simulations': sum(r['simulation_called'] for r in rows),
            'incomplete_responses': sum(r.get('response_status') == 'incomplete' for r in rows),
            'other_api_schema_failures': sum(r['outcome'] == 'API_OR_SCHEMA_FAILURE' and r.get('response_status') != 'incomplete' for r in rows),
            'final_spec_failures': sum(not t['recovered'] and t['rows'][-1]['outcome'] == 'SPECIFICATION_VIOLATION' for t in ts),
            'patch_rejections': sum(r['outcome'] == 'PATCH_REJECTED' for r in rows),
            'input_tokens': input_tokens, 'cached_input_tokens': cached,
            'cache_write_tokens': cache_write, 'historical_base_price_estimate_usd': historical_cost,
            'output_tokens': out_tokens, 'reasoning_tokens': reasoning,
            'estimated_api_cost_usd': cost,
            'summed_call_seconds': sum(r['elapsed_seconds'] for r in rows),
            'median_call_seconds': statistics.median([r['elapsed_seconds'] for r in rows]) if rows else None,
        }
    for case in cases:
        row = {'case_id': case['case_id'], 'design_id': case['design_id'],
               'frequency_mhz': case['spec']['target_center_frequency_hz'] / 1e6,
               'component': case['component'], 'multiplier': case['multiplier']}
        for condition in protocol['conditions']:
            ts = [t for t in trajectories if t['condition'] == condition and t['case_id'] == case['case_id']]
            row[condition + '_completed'] = len(ts)
            row[condition + '_first'] = sum(t['first_recovered'] for t in ts)
            row[condition + '_final'] = sum(t['recovered'] for t in ts)
        result['case_results'].append(row)
    if result['complete']:
        requests = list(output.glob('*/*/repeat_*/request_*.json'))
        rows = [r for t in trajectories for r in t['rows']]
        assert len(requests) == len(rows) <= protocol['max_api_calls']
        ids = [r['response_id'] for r in rows if 'response_id' in r]
        assert len(ids) == len(set(ids))
        existing = read(output / 'summary.json')
        assert existing['complete'] and existing['actual_api_attempts'] == len(rows)
        for condition, s in result['conditions'].items():
            old = existing['conditions'][condition]
            for new, prior in [('success_at_1', 'first_recovered'), ('success_at_3', 'final_recovered'),
                               ('localized', 'localized'), ('diagnosed', 'diagnosed'),
                               ('candidate_simulations', 'candidate_simulations')]:
                assert s[new] == old[prior]
            assert abs(s['historical_base_price_estimate_usd'] - old['estimated_api_cost_usd']) < 1e-9
    return result, trajectories


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()
    result, trajectories = aggregate()
    protocol = read(ROOT / 'experiments/budget_transfer_v4.json')
    if args.snapshot:
        print(json.dumps({k: v for k, v in result.items() if k != 'case_results'}, indent=2))
        return
    if not result['complete']:
        raise RuntimeError('Experiment incomplete; refusing final report')
    output = ROOT / 'build/experiments/budget_transfer_v4'
    audit = read(ROOT / 'build/budget_transfer_v4_audit/summary.json')
    all_rows = [row for t in trajectories for row in t['rows']]
    assert not audit['issues']
    assert audit['audited_iterations'] == len(all_rows), 'Run the offline audit on all completed evidence first'
    assert audit['unique_response_ids'] == len({r['response_id'] for r in all_rows if 'response_id' in r})
    assert audit['fresh_candidate_simulations'] == sum(r['simulation_called'] for r in all_rows)
    result['offline_audit'] = audit
    (output / 'independent_analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    with (output / 'case_results.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(result['case_results'][0]))
        writer.writeheader()
        writer.writerows(result['case_results'])
    n, b = (result['conditions'][c] for c in ['no_feedback', 'feedback'])
    difference = b['success_at_3'] - n['success_at_3']
    report = [
        '# 새 설계 사례에서 같은 최대 호출 예산의 피드백 비교', '',
        f"집계 시각: {result['as_of_utc']}. 고정 프로토콜 v4의 72개 실행 경로가 모두 완료됐다.",
        f"최종 복구는 no-feedback {n['success_at_3']}/36, feedback {b['success_at_3']}/36으로 차이는 {difference:+d}건({difference/36*100:+.1f}%p)이다.",
        '이는 같은 이상적 필터 topology의 새 파라미터 4개·고장 12개에 대한 관찰이다.',
        f"모델은 `{protocol['model']}`, reasoning `{protocol['reasoning_effort']}`이다. "
        '중심주파수 83/117/149/173 MHz와 대역폭 비율 10/12/14/16%를 사용했다. '
        '12개 사례 모두 API 호출 전에 정상 PASS·고장 FAIL·정답 수정 PASS를 확인했으며 사전 simulation 36회는 후보 비용에서 분리했다.', '',
        '| 지표 | no-feedback | feedback |', '|---|---:|---:|',
    ]
    labels = [('최초 복구 /36', 'success_at_1'), ('최종 복구 /36', 'success_at_3'),
              ('재시도에서 추가 복구', 'additional_recoveries'), ('최종 위치 진단 /36', 'localized'),
              ('최종 위치·방향 진단 /36', 'diagnosed'), ('다른 부품을 수정한 보상 복구', 'compensated_recoveries'),
              ('실제 API 호출', 'api_calls'), ('후보 simulation', 'candidate_simulations'),
              ('응답 미완료', 'incomplete_responses'), ('기타 API/schema 실패', 'other_api_schema_failures'),
              ('마지막까지 specification 실패', 'final_spec_failures'), ('patch 거절', 'patch_rejections'),
              ('입력 토큰 (캐시 포함)', 'input_tokens'), ('캐시 입력 토큰', 'cached_input_tokens'),
              ('출력 토큰 (추론 포함)', 'output_tokens'), ('추론 토큰', 'reasoning_tokens')]
    report += [f'| {label} | {n[key]} | {b[key]} |' for label, key in labels]
    report += [f"| 추정 API 비용 (USD) | {n['estimated_api_cost_usd']:.5f} | {b['estimated_api_cost_usd']:.5f} |",
               f"| 호출 소요시간 합 (초) | {n['summed_call_seconds']:.1f} | {b['summed_call_seconds']:.1f} |", '',
               '시간은 API와 로컬 처리 시간을 포함하며, 조건을 교대로 실행했으므로 조건별 독립 벽시계 시간이 아니다.',
               '비용은 프로토콜에 기록한 공개 단가와 실제 usage로 계산한 추정값이며 청구서가 아니다. '
               f"[단가 출처]({protocol['price_source']}). "
               'Cache write가 일반 입력의 1.25배라는 요율을 반영해 이전 기본 단가 추정치를 보정했다. '
               '고정 runner의 summary와 원시 usage는 보존했고, 독립 분석 JSON에 이전 추정치와 보정치를 함께 기록했다.', '']
    if difference == 0:
        report += ['현재 사례에서는 피드백이 최종 복구율을 높였다는 증거가 없다. '
                   '같은 관찰 비율이 두 방법의 동등성이나 다른 문제에서의 효과 부재를 증명하지는 않는다.', '']
    elif difference < 0:
        report += ['이번 조건에서는 피드백에 따른 최종 복구율 향상을 확인하지 못했다. '
                   '작은 표본의 낮은 관찰 비율을 일반적인 성능 저하의 증거로 확대하지 않는다.', '']
    else:
        report += ['최종 복구율의 관찰 차이와 응답 미완료·최초 성공률 차이를 함께 해석해야 한다. '
                   '이 작은 표본만으로 일반적인 피드백 우위를 확정하지 않는다.', '']
    report += ['## 설계별 최종 복구', '', '| 설계 | no-feedback /9 | feedback /9 |', '|---|---:|---:|']
    for design in sorted({r['design_id'] for r in result['case_results']}):
        group = [r for r in result['case_results'] if r['design_id'] == design]
        report.append(f"| {design} | {sum(r['no_feedback_final'] for r in group)} | {sum(r['feedback_final'] for r in group)} |")
    report += ['',
               '## 사례별 결과', '', '| 사례 | MHz | 고장 부품·배율 | no-feedback 최초→최종 /3 | feedback 최초→최종 /3 |',
               '|---|---:|---|---:|---:|']
    for r in result['case_results']:
        report.append(f"| {r['case_id']} | {r['frequency_mhz']:g} | {r['component']} ×{r['multiplier']} | {r['no_feedback_first']}→{r['no_feedback_final']} | {r['feedback_first']}→{r['feedback_final']} |")
    report += ['', '## 실패와 추가 복구의 원문 추적', '']
    for t in trajectories:
        if not t['recovered'] or not t['first_recovered']:
            chain = ' → '.join(r['outcome'] for r in t['rows'])
            report.append(f"- {t['condition']} / {t['case_id']} / repeat {t['repetition']}: {chain}.")
    report += ['', '## 원고에 반영할 해석', '',
               f"두 조건의 첫 성공은 각각 {n['success_at_1']}/36과 {b['success_at_1']}/36이었고, "
               f"최대 3회까지 실행한 추가 복구는 무피드백 {n['additional_recoveries']}건, 피드백 {b['additional_recoveries']}건이다. "
               '따라서 반복 실행의 추가 복구를 피드백 자체의 효과로 간주하면 안 된다.',
               f"최종 위치·방향 진단은 무피드백 {n['diagnosed']}/36, 피드백 {b['diagnosed']}/36이다. "
               '진단 지표와 성능 복구 지표의 순서가 달라질 수 있어 두 지표를 분리할 필요가 있다.',
               '실패 추적에서는 올바른 부품을 찾고도 근삿값·보간으로 수치 제약을 놓친 경우 '
               '(`transfer_d3_f2`, feedback repeat 1/2)와 잘못된 부품 조정에 머문 경우 '
               '(`transfer_d4_f3`, feedback repeat 1)가 보였다. 이는 완료된 결과를 살펴본 사후 해석이며 새로운 검증 실험이 아니다.',
               '후속 실험 후보는 공진식 등 결정적 수치 계산 도구를 결합하고 값 선택의 실패가 줄어드는지 확인하는 것이다. '
               '현재 사례는 이미 결과를 확인했으므로 변경 방법의 최종 확인에는 별도의 미사용 사례가 필요하다. '
               '기존 원고의 주 결과와 v4의 분모·사양은 분리해서 보고한다.', '',
               '## 비교 계약과 해석 한계', '',
               '두 조건은 같은 모델·prompt·초기 입력·스키마·출력 상한 2000토큰·최대 3회 호출을 사용했다. '
               '성공하면 조기 종료하므로 실제 호출 수는 같지 않다. feedback의 후속 입력은 길어지므로 실제 입력 토큰·달러 비용까지 일치시킨 실험도 아니다.',
               'no-feedback는 실패해도 이전 제안이나 측정 결과를 받지 않는다. feedback는 실패한 제안과 simulator/validator 결과를 받는다. '
               '두 조건의 첫 요청은 동일한 정보이지만 서로 다른 API 표본이므로 첫 성공률 차이는 피드백 효과가 아니다.',
               'API/schema 실패는 최대 3회 중 조기 종료되며 실패 분모에 포함했다. 응답 예산 변경이나 실패 응답 재발급은 없었다. '
               '추가 복구는 각 조건의 최초 대비 최종 증가량으로 보고하며, 최종 비율 차이 하나만으로 인과 효과를 단정하지 않는다.',
               '72개 경로는 12개 고장 ×3회 ×2조건이며 72개 독립 회로가 아니다. 고장은 4개 설계에 묶여 있다. '
               '적은 설계 수와 반복 의존성을 고려해 유의성이나 넓은 일반화 주장을 하지 않는다.',
               '설계별로 중심주파수와 대역폭을 함께 바꿨으므로 설계별 차이를 주파수 하나의 영향으로 해석하지 않는다. '
               '최초 성공률이 높으면 후속 피드백의 효과를 관찰할 기회도 적다.',
               '부품·노드 이름과 행 순서는 바꿨지만 Butterworth 구조와 값 대칭성 단서는 남아 있다. '
               '새 topology, 실제 RF 부품, PCB/RFIC 또는 하드웨어 측정의 근거가 아니다.',
               '최종 진단은 마지막 제안의 부품·고장 방향을 정답과 비교했다. 보상 복구는 성능 PASS이면서 실제 수정 부품이 주입 고장 부품과 다른 경우다.', '',
               '## 재현 및 검증', '',
               '입력·평가 코드 hash는 고정 프로토콜과 대조했다. final 기록을 iteration에서 독립 재구성하고 기존 runner 집계와 대조했다. '
               '원시 요청·응답·수정 회로·ngspice 출력은 `build/experiments/budget_transfer_v4/`에 있다.',
               f"오프라인 감사는 응답 {audit['unique_response_ids']}개와 후보 재시뮬레이션 {audit['fresh_candidate_simulations']}개를 확인했고, 원문·회로·metric·판정의 불일치가 없었다.",
               '```bash', '.venv/bin/python scripts/audit_budget_transfer.py', '.venv/bin/python scripts/report_budget_transfer.py', '```',
               '독립 집계 JSON: `build/experiments/budget_transfer_v4/independent_analysis.json`. '
               '사례별 CSV: 같은 디렉터리의 `case_results.csv`. '
               '새 결과는 기존 원고 수치에 자동으로 합산하지 않았다.', '']
    (ROOT / 'docs/budget_transfer_v4_results.md').write_text('\n'.join(report))
    print(json.dumps(result['conditions'], indent=2))


if __name__ == '__main__':
    main()
