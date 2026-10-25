# 참고문헌 검증 기록 (2026-09-03)

상태: `VERIFIED_FOR_DRAFT`  
대상: `paper/ACK2026_RF_LLM_repair_draft_ko_v0.3.docx`의 참고문헌 [1]~[5]

아래 서지정보는 출판사 페이지, DOI 또는 arXiv 원문 기록과 대조했다. 여기서 `verified`는
서지정보와 논문 초안의 인용 맥락이 해당 원문과 일치한다는 뜻이며, 각 연구 결과를 본 연구가
재현했다는 뜻은 아니다.

| 번호 | 검증 결과 | 원문 | 초안에서 뒷받침하는 범위 |
|---|---|---|---|
| [1] | verified | [SPICEPilot, arXiv:2410.20553](https://arxiv.org/abs/2410.20553) | LLM을 이용한 SPICE 코드 생성과 시뮬레이션 연계 |
| [2] | verified; DOI 추가 | [WiseEDA, Microelectronics Journal 158, 106607](https://doi.org/10.1016/j.mejo.2025.106607) | RF 필터 topology 및 파라미터 최적화 |
| [3] | verified | [RFAmpDesigner, arXiv:2605.10093](https://arxiv.org/abs/2605.10093) | multi-agent 기반 RF 증폭기 설계 자동화 |
| [4] | verified; DOI 추가 | [SPICED+, IEEE TVLSI 33(4), 1118–1131](https://doi.org/10.1109/TVLSI.2025.3527382) | A/MS 회로 트로이목마 탐지·교정 반복 절차 |
| [5] | verified | [NetlistBench, arXiv:2608.12197](https://arxiv.org/abs/2608.12197) | SPICE netlist 조작을 구조 기반 결정적 기준으로 평가 |

## 반영 사항

- [2]와 [4]에 DOI를 추가했다.
- [3]과 [5]는 현재 초안에서 arXiv 식별자를 유지한다.
- 관련 연구와 본 연구의 차이는 “설계 생성·최적화” 대 “고장 삽입→진단→수정→재시뮬레이션”으로
  제한해 기술한다.
- 외부 문헌은 본 연구의 46/48 복구율 등 실험 수치의 근거가 아니다. 이 수치는 저장된 실험
  산출물과 `paper/primary_results_audit.ipynb`에서 별도로 재계산한다.
