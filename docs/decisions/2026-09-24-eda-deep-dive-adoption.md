# EDA(전자 설계 자동화) deep-dive(심화 검토) adoption(채택) decision(결정)

작성일: 2026-09-24
결정자: 사용자 위임에 따른 구현 결정

## Adopted(채택)

- SQLite(라이트급 SQL 저장소) single-host(단일 호스트) durable Run/Attempt(지속 작업/실행 시도) 기록
- opaque lease token(불투명 임대 토큰), conditional heartbeat(조건부 심장박동), expired-lease reconciliation candidate(만료 임대 조정 후보)
- fixed-template OpenSTA subprocess(고정 템플릿 OpenSTA 하위 프로세스), timeout(시간 초과) termination(종료), explicit cancellation(명시 취소), input provenance hash(입력 출처 추적 해시)
- explicit in-flight budget(명시적 진행 중 실행 예산) backpressure(역압)
- strong Finding identity(강한 발견 항목 식별), fail-closed comparability(실패 안전 비교 가능성), and opt-in composite index(명시 선택 복합 인덱스)
- result correctness(결과 정확성)의 parse/semantic/provenance/trust axis(파싱/의미/출처 추적/신뢰 축) 분리

## Deferred(보류)

Kafka(카프카), Redis(레디스), PostgreSQL(포스트그레스큐엘), partitioning(파티셔닝), distributed fencing(분산 차단), and materialization(사전 계산)은 현재 실제 한계 실험에서 필요성이 관측되지 않아 도입하지 않는다.

## Revalidation trigger(재검증 조건)

다음 중 하나가 실제 workload(작업부하)에서 재현되면 해당 대안을 다시 연다: child process residue(하위 프로세스 잔존), single-host lease ownership ambiguity(단일 호스트 임대 소유권 모호성), sustained queue growth(지속 대기열 증가), in-flight budget rejection(진행 중 실행 예산 거절), SQLite write/index cost(라이트급 SQL 저장소 쓰기/인덱스 비용), retained replay(보존 재생) 또는 independent multi-consumer(독립 다중 소비자) 요구.

이 저장소가 source of truth(원본 기준)이며, Career OS(커리어 운영체제)는 이 문서와 evidence(근거)를 링크·요약만 한다.
