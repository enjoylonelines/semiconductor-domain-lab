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

## Finding index(발견 항목 인덱스) 운영 정책

EDA(전자 설계 자동화) revision review(설계 버전 검토)는 한 번의 조회 횟수보다 revision(설계 버전)마다 발생하는 engineer comparison(엔지니어 비교)과 interactive latency(대화형 지연)가 중요하다. 따라서 index(인덱스)는 다음 세 조건이 모두 성립할 때만 해당 service profile(서비스 프로파일)에서 켠다.

1. `new-violations` comparison(새 위반 비교)이 실제 review workflow(검토 흐름)에 포함된다.
2. 동일 설계의 연속 두 revision batch(설계 버전 배치)에서 각각 Finding(발견 항목) 10,000개 이상이 수집된다. 이 값은 현재 측정된 workload(작업부하) 경계이며, production scale(운영 규모) 주장이 아니다.
3. 인덱스 없는 Q2 p95(상위 95% 조회 지연)가 250ms를 넘거나, revision batch(설계 버전 배치) 하나에 Q2 comparison(조회 2 비교)을 3회 이상 수행한다.

세 번째 조건의 3회는 현재 20,000 Finding(발견 항목) workload에서 단일 조회도 CPU time(중앙 처리 장치 시간)만 보면 인덱스 비용을 회수한다는 관측보다 보수적인 운영 기준이다. 이 기준은 단발 exploratory query(탐색 조회)가 index write/storage cost(인덱스 쓰기/저장 비용)를 영구히 만들지 않게 한다. 조건을 만족하지 않으면 기본값 `enable_new_violation_index=False`를 유지한다. 매 30일 또는 데이터 보존 정책 변경 시 write latency(쓰기 지연), database size(데이터베이스 크기), Q2 count(조회 2 횟수)를 다시 측정한다.

## Career OS(커리어 운영체제) 반영 시점

Career OS(커리어 운영체제)는 모든 딥다이브가 끝날 때까지 기다리는 원본 저장소가 아니다. 각 bounded cycle(제한된 사이클)이 plan(계획), implementation(구현), evidence(근거), decision(결정), limitation(한계)을 갖고 commit(커밋)된 뒤에만 짧은 link/summary(링크/요약)를 추가한다. 실행 중 원시 수치, 미확정 판단, 중간 변경은 Career OS(커리어 운영체제)에 적재하지 않는다. 이 저장소가 source of truth(원본 기준)로 남는다.

이 저장소가 source of truth(원본 기준)이며, Career OS(커리어 운영체제)는 이 문서와 evidence(근거)를 링크·요약만 한다.
