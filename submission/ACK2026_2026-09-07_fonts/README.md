# 첨부 논문에 글꼴을 맞춘 RF 원고

편집용 검토본은 이 폴더의 **ACK2026_KimTaehoon_RF_Circuit_Repair.docx**다.
현재 제출용 파일은 [전체 내용을 보존한 3쪽 PDF](../ACK2026_2026-09-07_pdf/README.md)다.
앞선 `ACK2026_2026-09-07_evidence` 원고와 첨부 3GPP 원고는 그대로 보존했다.

첨부 `ACK2026_3GPP_normative_fidelity_draft_v3.docx`의 실제 글꼴 설정을 확인해
제목·저자·소속·절 제목은 NanumGothic, 초록·본문·표·문헌은 AppleMyungjo로 맞췄다.
제목 16pt, 저자·소속 10pt, 이메일 9pt, 초록 9pt, 키워드 8pt, 본문·절 제목 10pt,
캡션 9pt, 표 7pt, 참고문헌 8pt다. 캡션은 첨부본처럼 굵게 표시했다.
국문 제목은 ‘복구와’ 앞에서 줄을 나눠 마지막 단어만 다음 줄에 남는 현상을 없앴다.

첫 페이지는 제목·저자·초록 다음에 2단 본문을 바로 시작한다. 첨부본과 보관된 공식
KIPS 양식도 같은 흐름이다. 기존 A4·여백·단 설정은 유지하고 글꼴은 사용자 지정에 따랐다.
따라서 공식 양식의 원래 글꼴과 완전히 동일하다는 의미는 아니다.

## 검증

- 최종 SHA-256: `70ed75b6d207bee94aa647c0b83d9a8b5b56e3ec703695cbac92ce15ea911fa7`
- 전체 문단 텍스트·결과표 6개·그림 1개·편집 가능한 수식 1개·참고문헌 7개 보존.
- 변경된 패키지 항목은 `word/document.xml`, `word/styles.xml`이며, 글자 서식과 국문 제목 줄바꿈만 변경.
- 로컬 PDF 렌더 3쪽 모두 시각 검토. 표·그림·수식·문헌의 잘림·겹침 없음.
- 이후 Apple Pages 실물 확인에서는 같은 DOCX가 4쪽으로 표시됐다. 3쪽은 로컬 PDF 기준이다.
- 접근성 자동 검사 지적 0건. 변경 추적·주석 0건. 원본과 첨부본의 파일 해시 유지.
- 세부 기록: `build/paper_font_alignment/verification.json`.
- 재현 스크립트: `scripts/align_paper_fonts.py`.

내용은 앞선 [근거 제시 보완본](../ACK2026_2026-09-07_evidence/README.md)과 같으므로
[완결성 재평가](../../docs/paper_completeness_review_2026-09-07.md)의 내용상 판단을 그대로 적용한다.
이 수정 과정에서 실험이나 API 호출을 추가하지 않았다.
