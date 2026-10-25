# 문제 정의와 핵심 주장을 보완한 논문

이 폴더는 문제 정의 보완 단계의 원본 보관본이다. 현재 검토·제출 대상은
[2026-09-07 근거 제시 보완본](../ACK2026_2026-09-07_evidence/README.md)이다.
원제 「SPICE 피드백 기반 LLM 에이전트의 RF 회로 고장 진단 및 복구」를
**「집중소자 RF 회로에서 LLM 기반 복구와 원인 진단의 분리 평가」**로 바꿨다.
영문 제목은 “Separate Evaluation of LLM-Based Repair and Fault Diagnosis in Lumped RF Circuits”다.
앞선 diagnosis 원고는 보존했으며 제출 사이트에 업로드하지 않았다.

## 점검 의견 반영

- 초록·서론·결론의 중심을 LLM 복구·진단의 분리 평가와 피드백·수치 보조의 추가 기여 확인으로 맞췄다. 부정적 결과를 에이전트 우위나 새로운 진단 원리로 확대하지 않는다.
- 2절을 ‘문제 정의 및 평가 절차’로 바꾸고 입력·출력·평가 기준을 명시했다. 진단은 주입 위치·유형과 대조하며 값 변화는 위치·증감 방향을 평가한다. 성능 복구와 판단 보류를 별도로 정의했다.
- 과거 기준 응답을 이용한 확장은 현재 부품값과 고정 등가모형을 아는 조건임을 1쪽에 명시했다. 현재 고장 부품값을 모르는 실제 장비 진단과의 차이를 설명했다.
- 미사용 기본 주입 144상태의 규격 PASS 88·FAIL 56을 모두 포함함을 명시하고, 후속 지표를 성능 고장 복구가 아닌 값 변화 식별로 한정했다.
- 확정 정답 비율 21.1%→26.7%(5.6%p 증가)와 보류 73.3%를 함께 제시했다. 전체 규칙과 잔차·간격·비율만의 판정이 같아 대조·재검사의 추가 기여는 확인되지 않았음을 유지했다.
- 기존 아날로그 진단의 모호성과 선택적 예측 연구를 [6]·[7]로 추가했다. 현 규칙은 경험적 보정이며 기존 방법 대비 성능 우위나 확률적 보증으로 제시하지 않는다.
- 기존 결과표 5개는 그대로 보존했다. 표를 반복하는 설명과 계산 보조·정합회로 파일럿 설명을 압축했으며 수치·사양·분모·실패 포함 원칙은 유지했다.

## 추가 참고문헌

[6] S. Hałgas, “Diagnosis of Analog Circuits: The Problem of Ambiguity of Test Equation Solutions,” Electronics 13(4), 684, 2024. DOI: [10.3390/electronics13040684](https://www.mdpi.com/2079-9292/13/4/684).
앞선 점검에서 출판사 검색 본문과 서지정보를 확인했다. 후속 직접 열기는 429 응답이었으며, 본문에는 여러 파라미터 해가 존재할 수 있다는 확인 범위만 인용했다.

[7] Y. Geifman and R. El-Yaniv, “Selective Classification for Deep Neural Networks,” NIPS, 2017.
[학회 원문](https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html)에서 저자·제목·학회·연도와 판단 비율/오류의 관계를 확인했다. 해당 연구의 위험 보증 알고리즘을 구현했다는 의미는 아니다.

## 재현

번들 Python으로 `scripts/update_paper_framing.py`를 실행한다. 변경 내역과 수치 재집계는
`build/paper_framing_update/changes.json`에 저장된다.
documents 스킬의 `render_docx.py`와 번들 LibreOffice로 렌더링하고,
`scripts/audit_paper_framing.py --template <공식 양식 DOCX> --render-dir <최종 렌더 디렉터리>`로 확인한다.
기존 실험·기본 보류 정책은 변경하지 않았고 추가 API 호출이나 실험 계산은 수행하지 않았다.

## 최종 검증

- 최종 DOCX SHA-256: `89a8f3a6fb8a85c65853730534bbcc5d715dd27e8c9b6488913805bab60d682f`
- 공식 양식의 스타일·구역 설정, 기존 결과표 5개·그림 1개·편집 가능한 수식 1개를 보존했다. 원본은 변경하지 않았다.
- 근거 파일 12개의 해시를 확인하고, 미사용 평가 2,304건의 정답 615·보류 1,689·오판 0과 대조군 64건의 오경보 0을 재집계했다.
- 최종 렌더 `build/paper_framing_update/render_final2`의 3쪽을 모두 시각 검토했다. 절 제목과 첫 문단, 표·수식·참고문헌 배치에서 잘림이나 겹침이 없었다.
- 접근성 자동 검사 지적 0건, 주석·변경 추적 0건이며 상세 결과는 `build/paper_framing_update/verification.json`에 기록했다.
