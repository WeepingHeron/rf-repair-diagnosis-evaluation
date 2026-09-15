# 확장 결과를 반영한 논문

이 폴더는 계산 보조·정합회로까지 반영한 이전 원고의 보존본이다.
현재 검토 대상은 [진단 확장을 반영한 최신 원고](../ACK2026_2026-09-06_diagnosis/README.md)다.
앞선 2026-09-03, 2026-09-06, v4 중간 원고는 보존했다.

## 반영 내용

- 기존 주 결과 46/48, 위치 45/48, 전체 진단 37/48과 구조 holdout 결과 유지.
- 새 설계의 동일 최대 호출 예산 비교 표 4 추가: 무피드백 33/36, 피드백 31/36.
  초록과 결론에 피드백 우위가 확인되지 않았다는 결과 반영.
- 탐색적 공진 계산 보조 비교: 일반 피드백 12/16, 계산 보조 15/16,
  실제 호출은 각각 25회. 첫 시도는 11/16과 8/16으로 따로 표시.
- 결정적 공진 기준선: LLM 없이 11회 시뮬레이션으로 8/8 복구.
- 다른 topology의 L형 정합회로 one-shot 파일럿: 복구 5/8, 진단 6/8,
  응답 미완료 1건 포함. 일반화 근거로 확대하지 않음.
- v4와 후속 탐색적 확장의 분모·사양·주장을 분리. 부품 편차·기생성분을
  포함한 미사용 사례를 다음 검증 대상으로 제안.

## 검증

- 공식 KIPS 양식의 styles.xml 및 두 section의 A4·여백·2단 설정과 정확히 일치.
- 최종 렌더 3쪽의 모든 페이지를 직접 확인. 한글·수식·그림·표 잘림 없음.
- 편집 가능한 Word 공진식 1개, 결과표 4개, 그림 1개. 상단 배치용 표는 별도.
- 접근성 검사 high/medium/low 모두 0, 추적 변경 0, 중복 paragraph ID 0.
- 소스 v4 DOCX 대비 word/document.xml만 변경했고 나머지 패키지 구성은 보존.
- 프로젝트 테스트 49개 통과. 신규 응답 58개와 후보 57개를 감사·재시뮬레이션,
  결정적 기준선 11개도 별도로 재시뮬레이션하여 불일치 없음.
- 최종 SHA-256: `fb04b9fa0b58aca4a30683f849bd3c35b3fea69737684b94ed8a4326854f0fc6`.

이 환경에서는 문서 내부의 공식 양식 글꼴을 유지하고 로컬 fontconfig의 대체 글꼴로
렌더한다. 실제 제출 미리보기에서도 3쪽과 한글 표시를 확인한다.

## 재현 경로

v4 결과와 원고 갱신: `scripts/report_budget_transfer.py`, `scripts/update_paper_v4.py`.
후속 실험과 감사: `scripts/run_extension.py`, `scripts/audit_extensions.py`.
최종 보고서와 원고: `scripts/report_extensions.py`, `scripts/update_paper_extensions.py`.
DOCX 스크립트는 bundled Python에서 실행한다.

상세 결과: `docs/budget_transfer_v4_results.md`, `docs/priority_extensions_results.md`.
원시 API·시뮬레이션 결과는 `build/experiments/`에 보존되며 기존 Git ignore 대상이다.
이 작업에서는 제출 사이트 업로드나 Git commit/push를 수행하지 않았다.
