# 개발 작업 규칙

## Engineering loop and source of truth

중요한 설계·성능·안정성 작업은 [AI-assisted engineering workflow](docs/engineering/ai-assisted-engineering-workflow.md)에 따라 기록한다.

- Problem → Human hypothesis (실험 전 Prediction 포함) → Falsification condition → Experiment → Evidence → Human decision → Changed belief → Stop condition 순서로 한 사이클을 닫는다. 종료 조건과 실험 예산은 시작 전에 정하고 마지막에 충족 여부를 확인한다.
- 문제 선택, 실험 전 예측, 결과 해석, 최종 결정과 종료 판단은 사람이 소유한다. AI는 조사·대안·구현·테스트·집계를 지원하며, 사용자 미진술 항목은 `unrecorded` 또는 `pending human decision`으로 남긴다.
- 새 기능이 현재 대표 문제 해결에 필수인지 먼저 확인한다. 필수가 아니면 backlog로 보내고, 기존 프로젝트별 Human Gate·실행 승인·종료 기준을 유지한다.
- 코드·실험·decision/evidence의 source of truth는 해당 프로젝트의 로컬 repo다. 루트에는 상시 규칙, `docs/plans/`에는 계획, `docs/decisions/`에는 판단, `docs/evidence/`에는 실행 결과와 원시 증거 참조를 둔다. 기존 원본 경로는 유지하고 링크로 연결한다.
- Career OS는 프로젝트 경험의 인덱스·요약·역량 연결을 담당한다. 원본 링크/참조 revision, 제한을 포함한 요약, 역량 증거 연결, 포트폴리오 재사용 상태/위치만 적재한다. decision/evidence 전문이나 원시 로그를 중복 관리하지 않는다.
- 원본을 먼저 갱신한 뒤 Career OS 요약을 갱신한다. 불일치하면 repo 원본을 확인하고 요약을 오래된 상태로 표시한다. 기존 변경사항과 과거 기록은 보존한다.
