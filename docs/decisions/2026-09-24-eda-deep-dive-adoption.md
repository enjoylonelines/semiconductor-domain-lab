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

## Compute resource envelope(컴퓨팅 자원 경계)

server count(서버 수), CPU(중앙 처리 장치), memory(메모리), disk(디스크), license capacity(라이선스 용량)는 worker count(작업자 수)보다 먼저 명시·측정해야 하는 운영 입력이다. 2026-09-25에 측정한 개발 환경은 host(호스트) 1대, physical/logical CPU(물리/논리 중앙 처리 장치) 10/10, memory(메모리) 64 GiB, repository disk free(저장소 가용 디스크) 약 828 GiB다. 이 값은 배포 사양이 아니라 [고정 OpenSTA 단일 호스트 용량 실험](../evidence/2026-09-25-opensta-single-host-capacity.md)의 환경 경계다.

그 경계에서 fixed OpenSTA profile(고정 OpenSTA 프로파일)은 `max_workers=8`, `max_in_flight=8`, `resource_slots=8`을 채택한다. 같은 tiny workload(작은 작업부하)를 1/2/4/8 동시성에서 각 5회 실행해 8 동시성이 1 대비 평균 처리량 약 6.97배, p95 batch wall time(상위 95% 배치 경과 시간) 약 15.7% 증가를 보였다. 일반 `JobService` 기본값이나 다른 host(호스트)의 한도를 이 수치로 바꾸지 않는다.

resource profile(자원 프로파일)은 호스트별 명시 설정이다. CPU/memory quota(중앙 처리 장치/메모리 할당량), container limit(컨테이너 제한), license seat(라이선스 좌석), netlist size(넷리스트 크기), co-tenant workload(공동 실행 작업부하), queue/deadline requirement(대기열/마감 요구)가 바뀌면 1부터 같은 방법으로 재측정한다. 9개 이상 동시성·multi-host(다중 호스트)·autoscaling(자동 확장)은 한계 실험이 관측될 때만 다음 challenger(도전 대안)로 연다.

`JobService`에서 같은 profile(프로파일)로 8개 actual OpenSTA(실제 OpenSTA) 작업을 실행했을 때 9번째 submit(제출)은 Run(작업)을 만들지 않고 `BackpressureError`로 거절됐고, 8개 완료 뒤 다음 작업은 성공했다. 따라서 이 profile(프로파일)의 현재 admission policy(입장 정책)는 persistent queue(영속 대기열)가 아닌 bounded rejection(제한된 거절)이다. retry delay(재시도 지연), fairness(공정성), priority queue(우선순위 대기열), sustained arrival rate(지속 도착률)는 아직 측정하지 않았으며, [서비스 예산 근거](../evidence/2026-09-25-opensta-service-budget.md)를 넘는 주장으로 승격하지 않는다.

같은 profile(프로파일)의 mixed load/recovery(혼합 부하/복구)에서 normal/tight/timeout(정상/엄격/시간 초과) OpenSTA 작업의 execution/check/trust status(실행/검사/신뢰 상태) 분리가 유지됐다. 실제 child process(하위 프로세스)가 완료된 뒤 terminal persistence(종단 저장) 전에 worker loss(작업자 손실)를 주입하면 reconciliation(상태 재조정)은 `ABANDONED/FAILED`로 끝냈다. 이는 성공 추측을 막는 근거이며, sustained arrival rate(지속 도착률), persistent queue(영속 대기열), multi-host recovery(다중 호스트 복구) 채택 근거는 아니다. 자세한 원시 결과와 한계는 [혼합 부하/복구 근거](../evidence/2026-09-25-opensta-load-recovery.md)에 있다.

fixed arrival wave(고정 도착 파동) 4회에서 9개 요청마다 8개는 성공하고 하나는 즉시 거절됐다. 총 36개 중 32개를 수락해 p95 end-to-end latency(상위 95% 종단 간 지연) 약 273.9ms를 보였고, 거절된 4개는 Run(작업)을 만들지 않았다. 이 workload(작업부하)에서 queue growth(대기열 증가)나 wave 간 지연 누적은 관측되지 않았으므로 persistent queue(영속 대기열)와 Kafka(카프카)는 보류한다. [고정 도착 부하 근거](../evidence/2026-09-25-opensta-fixed-arrival.md)는 batch arrival(배치 도착)만 다루며, 실제 retry behavior(재시도 행동)·fairness(공정성)·priority(우선순위)·license pressure(라이선스 압박)는 포함하지 않는다.

## Finding index(발견 항목 인덱스) 운영 정책

EDA(전자 설계 자동화) revision review(설계 버전 검토)는 한 번의 조회 횟수보다 revision(설계 버전)마다 발생하는 engineer comparison(엔지니어 비교)과 interactive latency(대화형 지연)가 중요하다. 따라서 index(인덱스)는 다음 세 조건이 모두 성립할 때만 해당 service profile(서비스 프로파일)에서 켠다.

1. `new-violations` comparison(새 위반 비교)이 실제 review workflow(검토 흐름)에 포함된다.
2. 동일 설계의 연속 두 revision batch(설계 버전 배치)에서 각각 Finding(발견 항목) 10,000개 이상이 수집된다. 이 값은 현재 측정된 workload(작업부하) 경계이며, production scale(운영 규모) 주장이 아니다.
3. 인덱스 없는 Q2 p95(상위 95% 조회 지연)가 250ms를 넘거나, revision batch(설계 버전 배치) 하나에 Q2 comparison(조회 2 비교)을 3회 이상 수행한다.

세 번째 조건의 3회는 현재 20,000 Finding(발견 항목) workload에서 단일 조회도 CPU time(중앙 처리 장치 시간)만 보면 인덱스 비용을 회수한다는 관측보다 보수적인 운영 기준이다. 이 기준은 단발 exploratory query(탐색 조회)가 index write/storage cost(인덱스 쓰기/저장 비용)를 영구히 만들지 않게 한다. 조건을 만족하지 않으면 기본값 `enable_new_violation_index=False`를 유지한다. 매 30일 또는 데이터 보존 정책 변경 시 write latency(쓰기 지연), database size(데이터베이스 크기), Q2 count(조회 2 횟수)를 다시 측정한다.

## Career OS(커리어 운영체제) 반영 시점

Career OS(커리어 운영체제)는 모든 딥다이브가 끝날 때까지 기다리는 원본 저장소가 아니다. 각 bounded cycle(제한된 사이클)이 plan(계획), implementation(구현), evidence(근거), decision(결정), limitation(한계)을 갖고 commit(커밋)된 뒤에만 짧은 link/summary(링크/요약)를 추가한다. 실행 중 원시 수치, 미확정 판단, 중간 변경은 Career OS(커리어 운영체제)에 적재하지 않는다. 이 저장소가 source of truth(원본 기준)로 남는다.

이 저장소가 source of truth(원본 기준)이며, Career OS(커리어 운영체제)는 이 문서와 evidence(근거)를 링크·요약만 한다.
