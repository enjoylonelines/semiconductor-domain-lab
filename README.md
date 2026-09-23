# semiconductor-domain-lab

퀄리타스반도체 SW Engineer 지원을 위한 **반도체/IP/EDA 도메인 학습·검증** 저장소.

현재 상태: **2026-09-24 synthetic 프로토타입. 기존 테스트 5개 통과, 별도 probe에서 실행 실패의 SUCCEEDED 저장과 비유한 slack의 PASS 재현. 실제 EDA 출력 fixture·Product/Engineering STOP은 미충족. 최초 commit 전이며 파일은 untracked다.**

현재 좁은 목표는 **단일 STA(정적 타이밍 분석) 보고서의 불완전·오류 입력을 정상으로 승격하지 않는 검증 도구**다. [실제 반례](docs/evidence/stage2-validation-matrix.md)와 [Product DoD·Deep Dive·두 STOP](docs/plans/research-and-scope-2026-09-23.md)을 따른다. 다음 코드는 nonzero-exit 성공 오표시의 회귀·최소 수정이다. 실제 tool/version은 환경·공개 fixture 확인 후 확정하며, mock만으로 완료하지 않는다.

- [현재 범위 정본 — 재조사·문제 재정의·확장/종료 조건](docs/plans/research-and-scope-2026-09-23.md)
- [학습 가이드](docs/learning/study-guide.md)
- [Track A 학습·자기 설명 검증 정본](docs/plans/domain-learning-plan-2026-09-23.md)
- [AI와 학습자의 역할 분담](docs/plans/ai-human-division.md)
- [용어 표기 규칙·초기 읽기 표](docs/plans/terminology-plan.md)
- [회사·현행/과거 JD·기술 자료 출처 장부](docs/references/source-register-2026-09-23.md)

Track A는 도메인 학습·synthetic parser이고, Track B는 실제 EDA를 복제하지 않는 workflow platform prototype이다. 2~3일은 Track A 또는 Track B의 최소 vertical slice에만 해당한다.

Track A는 새 서비스 구축 없이 도메인 이해를 검증한다. 현재 Track B는 단일 synthetic flow의 HTTP API·SQLite·프로세스 내 worker로 실행/파싱/검사 상태와 원문 추적을 검증한다([Stage 1 decision](docs/architecture/stage1-decision.md)).
웹 UI·추가 DB/broker 인프라·상용 EDA·회로 설계·100명 운영·동적 풀은 범위 밖이다. 단일 공개 도구 output/작은 design 검증은 현재 완료조건에 포함한다. [범위 정본 §0](docs/plans/research-and-scope-2026-09-23.md)의 증거 기반 trigger와 별도 결정 없이 다음 단계를 자동 진행하지 않는다.

## 후속 작업 경계
@devspace-max 우선, 기존 workspace 재사용. 계획서는 docs/plans에 유지한다.
명시적 요청 없이 구현·커밋·푸시하지 않는다.
출처에 명시된 사실(F), 추론(I), 학습용 단순화(S), 미확인(U)을 분리한다.
