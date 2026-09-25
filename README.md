# semiconductor-domain-lab

퀄리타스반도체 SW Engineer 지원을 위한 **반도체/IP/EDA 도메인 학습·검증** 저장소.

현재 상태: **2026-09-25 bounded EDA workflow prototype(범위 제한 EDA 작업흐름 프로토타입).** 실제 OpenSTA(정적 타이밍 분석 도구) `setup-max` 고정 fixture(고정 입력), Run/Attempt(작업/실행 시도) lease(임대), timeout/cancel(시간 초과/취소), worker-loss reconciliation(작업자 손실 상태 조정), single-host resource admission(단일 호스트 자원 입장), result trust(결과 신뢰) 분리를 구현·측정했다. 이 근거는 운영 용량이나 회사 내부 시스템 주장이 아니며, 정확한 경계는 [채택 결정](docs/decisions/2026-09-24-eda-deep-dive-adoption.md)과 `docs/evidence/`를 따른다.

현재 작업은 **고정된 OpenSTA workload(작업부하)의 실행·복구·결과 신뢰 계약을 실제 child process(하위 프로세스)로 검증하고, 확장 조건을 근거와 함께 남기는 것**이다. [첫 번째 딥다이브 계획](docs/plans/2026-09-24-eda-execution-correctness-deep-dive.md), [채택 결정](docs/decisions/2026-09-24-eda-deep-dive-adoption.md), [실제 STA 근거](docs/evidence/2026-09-24-real-sta/README.md)를 따른다.

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
