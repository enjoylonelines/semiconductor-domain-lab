# Distributed execution ownership(분산 실행 소유권) Deep Dive 1 계획

작성일: 2026-09-26
상태: 계획 승인됨; Phase B(단계 B) 실행 전
원본 기준: 이 프로젝트 repository(저장소). Career OS(커리어 운영체제)는 완료된 bounded cycle(제한된 사이클)의 링크·요약·revision(리비전)만 보관한다.

## 1. Problem framing(문제 정의)

### Observed problem(관측된 문제)

local validation profile(로컬 검증 프로필)는 OpenSTA(정적 타이밍 분석 도구) child process(하위 프로세스)의 timeout(시간 초과), cancellation(취소), Run/Attempt(작업/실행 시도), lease(임대), heartbeat(심장박동), same-host(동일 호스트) reconciliation(상태 재조정)을 검증했다. PostgreSQL operational-path candidate(운영 경로 후보)는 two submitter process(두 제출 프로세스), two worker process(두 작업자 프로세스), central PostgreSQL(중앙 PostgreSQL), eight actual OpenSTA Run(실제 OpenSTA 작업)을 5회 실행해 정상 claim(권한 획득)과 결과 저장을 확인했다.

그러나 PostgreSQL 경로에서 worker loss(작업자 손실)와 completion boundary loss(완료 경계 손실)를 실제 OpenSTA child(하위 프로세스)로 아직 주입하지 않았다. Worker(작업자)가 사라져도 child(하위 프로세스)가 살아 있을 수 있으므로 lease expiry(임대 만료)를 즉시 재실행 신호로 해석하면 duplicate execution(중복 실행)을 만든다.

### Core question(핵심 질문)

> 동일 host(호스트)에서 PostgreSQL(포스트그레스큐엘)을 공유하는 독립 worker process(작업자 프로세스)들이 OpenSTA execution ownership(실행 소유권)을 안전하게 조정할 수 있는가? 즉 worker가 사라져도 original child(기존 하위 프로세스)의 생존 여부를 확인하고, 살아 있으면 보호하며, 종료가 확인된 경우에만 새 Attempt(실행 시도)를 허용하거나 최종 실패로 확정할 수 있는가?

OpenSTA는 checkpoint/resume(중간 저장점/이어서 실행)을 제공하지 않는 현재 fixed setup/max profile(고정 setup/max 프로파일)이다. recovery(복구)는 resume(계속 실행)이 아니라 **original execution liveness decision(기존 실행 생존 판정) → old Attempt abandonment(기존 실행 시도 폐기) → optional full re-execution(선택적 전체 재실행)** 이다.

### Human hypothesis(사람 가설), prediction(예측)

- Human hypothesis(사람 가설): `unrecorded`.
- User-approved scope(사용자 승인 범위): PostgreSQL coordination correctness(조정 정확성)를 먼저 닫고, 그 뒤 현재 coordination limit(조정 한계)을 측정한다. Kafka(카프카)는 측정된 필요가 있을 때만 challenger(대안)로 비교한다.
- Prediction(예측): `unrecorded`.

### Falsification condition(반증 조건)

다음 중 하나가 재현되면 Phase B(단계 B)의 ownership contract(소유권 계약)를 기각하거나 보강한다.

- one Run(한 작업)에 두 worker가 유효한 claim(권한)을 얻는다.
- child alive(하위 프로세스 생존)인데 새 Attempt가 실행된다.
- stale lease token(오래된 임대 토큰) 또는 old Attempt(이전 실행 시도)가 accepted completion(승인된 완료)을 쓴다.
- child confirmed dead(하위 프로세스 종료 확인) 뒤 Run이 영구 `RUNNING`으로 남는다.

### Decision required(필수 결정)

1. confirmed-dead child(종료 확인 하위 프로세스) 뒤 recovery action(복구 동작)을 bounded re-execution(제한된 전체 재실행)으로 할지, `FAILED` 확정으로 할지.
2. Phase C(단계 C) 증거가 PostgreSQL coordination bottleneck(조정 병목)을 보여 주는지.
3. Phase D(단계 D) Kafka challenger(카프카 대안)를 실행할 trigger(조건)가 충족되는지와, 비교 뒤 operational adoption(운영 채택) 여부.

### Stop condition / budget(종료 조건 / 예산)

- Phase B는 actual OpenSTA(실제 OpenSTA)로 정상·child-alive·child-dead·completion-boundary 네 경우를 각 최소 한 번 재현하고, 해당 invariants(불변식)과 raw evidence(원시 근거)를 남기면 멈춘다.
- Phase C는 fixed workload(고정 작업부하)의 coordination microbenchmark(조정 미세 측정)와 actual OpenSTA workload(실제 OpenSTA 작업부하)를 비교한 뒤 PostgreSQL 유지 또는 Kafka challenger의 Human Decision Gate(사람 결정 관문)를 남기면 멈춘다.
- Phase D는 Phase C trigger가 있을 때만 시작한다. 동일 workload(동일 작업부하)에서 Kafka 전후를 한 번의 bounded comparison(제한 비교)으로 측정한 뒤 멈춘다.
- DB replication(데이터베이스 복제), failover(장애 조치), multi-region(다중 리전), Kubernetes(쿠버네티스), Redis(레디스), autoscaling(자동 확장), license server(라이선스 서버)는 이번 budget(예산) 밖이다.

## 2. Current source register(현재 근거 장부)

- [Local execution adoption](../decisions/2026-09-24-eda-deep-dive-adoption.md): local SQLite(로컬 SQLite) profile(프로파일), resource budget(자원 예산), same-host recovery(동일 호스트 복구)의 채택 범위와 한계.
- [Operating profile correction](2026-09-25-operating-profile-correction.md): local SQLite와 PostgreSQL candidate(후보)의 구분 및 Human Decision Gate(사람 결정 관문).
- [PostgreSQL OpenSTA operational-path evidence](../evidence/2026-09-26-postgres-opensta-operational.md): two submitter/two worker, 8 actual Run, 5 repeats의 정상 경로 수치. HTTP sustained load(지속 HTTP 부하)나 multi-host(다중 호스트) 근거가 아님.
- [Cross-process recovery evidence](../evidence/2026-09-25-opensta-cross-process-recovery.md): same-host PID liveness(동일 호스트 프로세스 식별자 생존성)가 original child(기존 하위 프로세스)를 보호해야 한다는 local baseline(로컬 기준선).

## 3. Architecture and state contract(아키텍처와 상태 계약)

```text
HTTP API process(프로세스)
  → PostgreSQL Run Store(작업 저장소): QUEUED Run + immutable spec payload(불변 명세 적재)
  → worker claim(작업자 권한 획득): FOR UPDATE SKIP LOCKED
  → Attempt lease + heartbeat + process PID
  → OpenSTA child process(하위 프로세스)
  → token-fenced terminal persistence(토큰 차단 종단 저장)
```

`Run`은 사용자 요청의 durable identity(지속 식별자)다. `Attempt`는 한 Run의 하나의 실제 OpenSTA execution(실행)이다. `lease expiry`는 상태가 아니라 reconciliation candidate(상태 재조정 후보)다.

| object(객체) | permitted state(허용 상태) | 핵심 규칙 |
| --- | --- | --- |
| Run(작업) | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `CANCELLED` | `job_id`와 immutable spec hash(불변 명세 해시)는 하나의 Run만 식별한다. |
| Attempt(실행 시도) | `RUNNING`, `SUCCEEDED`, `FAILED`, `RETRYABLE_FAILURE`, `CANCELLED`, `ABANDONED` | attempt number(실행 시도 번호)와 lease token(임대 토큰)이 소유권을 식별한다. |
| Reconciliation(상태 재조정) | 상태가 아님 | expired lease(만료 임대)를 읽고 child liveness(하위 프로세스 생존성)와 token fence(토큰 차단)를 판정한다. |

목표는 `exactly-once execution(정확히 한 번 실행)`이 아니다. 목표는 **at-least-once execution(최소 한 번 실행) + at-most-one accepted completion(최대 한 번의 승인된 완료)** 이다. 실제 계산이 재실행될 수 있음을 기록하되, old Attempt(이전 실행 시도)의 결과가 new Attempt(새 실행 시도)나 Run의 최종 상태를 덮지 못하게 한다.

### Host assumption(호스트 전제)

Phase B는 worker와 OpenSTA child가 같은 host(호스트)에 있고, reconciliation process(상태 재조정 프로세스)가 그 host의 PID 생존 여부를 확인할 수 있는 local-host assumption(로컬 호스트 전제)에서만 검증한다. PID reuse(프로세스 식별자 재사용), remote child(원격 하위 프로세스), multi-host liveness(다중 호스트 생존성), host reboot(호스트 재부팅)는 명시적으로 미검증이다.

## 4. Alternatives(대안)

| alternative(대안) | expected gain(기대 이득) | decisive downside(결정적 단점) | decision(판단) |
| --- | --- | --- | --- |
| state flag only(상태 플래그만) | 단순함 | worker loss 뒤 orphaned `RUNNING`을 구분하지 못함 | reject(기각) |
| timeout then immediate reclaim(시간 초과 뒤 즉시 재할당) | 빠른 표면 복구 | slow worker(느린 작업자) 또는 live child(생존 하위 프로세스)를 중복 실행 | reject(기각) |
| lease + heartbeat only(임대와 심장박동만) | stale owner(오래된 소유자) 감지 | child liveness(하위 프로세스 생존성)를 보지 않으면 여전히 중복 실행 | insufficient(불충분) |
| lease + heartbeat + PID liveness + token-fenced Attempt(임대·심장박동·PID 생존성·토큰 차단 실행 시도) | live child 보호와 accepted completion 차단 | same-host PID assumption(동일 호스트 PID 전제), 보수적 지연 | Phase B challenger(단계 B 대안) |
| PostgreSQL polling/claim(포스트그레스큐엘 폴링/권한 획득) | 현재 상태·결과 DB를 재사용 | 지속 polling과 claim contention(권한 경합)의 한계 미측정 | Phase C baseline(단계 C 기준선) |
| Kafka delivery + PostgreSQL state(카프카 전달 + 포스트그레스큐엘 상태) | delivery(전달)와 state(상태) 책임 분리 | consumer group(소비자 그룹), partition(파티션), redelivery(재전달), offset/DB boundary(오프셋/DB 경계) 복잡도 | Phase C trigger 뒤 Phase D challenger(단계 D 대안) |

## 5. Phase plan(단계 계획)

### Phase A — Local execution correctness(로컬 실행 정확성) — complete(완료)

완료 근거는 local SQLite lifecycle(로컬 SQLite 수명주기), actual OpenSTA timeout/cancel(실제 OpenSTA 시간 초과/취소), Run/Attempt/lease, same-host reconciliation과 resource budget evidence(자원 예산 근거)다. 이 Phase는 재실행하지 않고 source register(근거 장부)로 참조한다.

### Phase B — PostgreSQL ownership and recovery correctness(소유권과 복구 정확성) — current(현재)

#### Implementation order(구현 순서)

1. PostgreSQL Run/Attempt schema(스키마)에 new Attempt eligibility(새 실행 시도 가능 조건)를 명시한다. old Attempt가 `ABANDONED`가 되기 전에는 new Attempt를 만들지 못하게 한다.
2. reconciliation(상태 재조정)이 `lease expired`와 PID liveness를 함께 검사한다. live child이면 `RUNNING`을 유지하고 new Attempt를 만들지 않는다.
3. confirmed-dead child이면 old Attempt를 token-fenced `ABANDONED`로 확정한다. Human Decision Gate(사람 결정 관문)가 선택한 bounded re-execution 또는 `FAILED` 정책만 수행한다.
4. completion boundary hook(완료 경계 훅)을 추가해 parse/result collection(파싱/결과 수집) 뒤 terminal persistence(종단 저장) 전에 worker kill(작업자 강제 종료)을 주입한다.

#### TDD Red-Green-Refactor(테스트 주도 개발 실패-통과-리팩터)

각 failure injection(장애 주입)은 먼저 invariant(불변식)를 깨는 test(테스트)를 Red(실패)로 기록한다. 최소 token fence(토큰 차단), abandonment(폐기), reclaim eligibility(재할당 가능 조건) 구현으로 Green(통과)으로 전환하고, 그 뒤 state transition(상태 전이)와 process observation(프로세스 관측)을 정리한다. Test Scope Review(테스트 범위 검토)는 unit(단위) 성공만으로 끝내지 않고 actual OpenSTA(실제 OpenSTA)와 separate process(분리 프로세스)까지 확장할지 검토한다.

#### Fault-injection matrix(장애 주입 표)

| case(경우) | fixture/workload(픽스처/작업부하) | injection(주입) | invariant(불변식) | metric(측정) |
| --- | --- | --- | --- | --- |
| B0 normal(정상) | fixed setup/max OpenSTA Run | 없음 | one claim, one accepted completion(하나의 권한, 하나의 승인 완료) | elapsed time(경과 시간), attempts, trust status(신뢰 상태) |
| B1 worker kill + child alive(작업자 종료 + 하위 프로세스 생존) | delayed actual OpenSTA child | child 시작 뒤 parent worker `SIGKILL` | expired lease여도 new Attempt=0, Run=`RUNNING` | liveness hold time(생존 보류 시간), duplicate execution=0 |
| B2 worker kill + child dead(작업자 종료 + 하위 프로세스 종료) | B1 child가 자연 종료 또는 확인 가능한 종료 | child exit 확인 뒤 reconciliation | old Attempt=`ABANDONED`; 정책에 따른 one new Attempt 또는 terminal `FAILED` | recovery latency(복구 지연), redundant execution(불필요 재실행) |
| B3 completion boundary kill(완료 경계 종료) | actual report 생성 뒤 terminal write 전 hook | worker `SIGKILL` | stale/old completion accepted=0; Run이 영구 `RUNNING` 아님 | duplicate commit=0, final status, attempt count |

Phase B evidence(근거)는 Run/Attempt row history(행 이력), worker/child PID observation(작업자/하위 프로세스 PID 관측), exit code(종료 코드), reconciliation decision(상태 재조정 판단), raw wall-clock time(원시 경과 시간)을 포함한다.

#### Phase B gate(단계 B 관문)

- **Pass candidate(통과 후보):** B0–B3 모두 invariant를 만족하고, new Attempt가 live child와 overlap(겹침)하지 않으며, accepted completion이 하나다.
- **Fail:** token fence 우회, duplicate accepted completion, child-dead 뒤 무기한 `RUNNING`, 또는 live child 중 새 Attempt 생성.
- **Human decision:** confirmed-dead 이후 bounded re-execution을 채택할지 `FAILED` 확정을 유지할지 결정한다.

### Phase C — PostgreSQL coordination limit(조정 한계) — gated(관문 대기)

Phase B를 통과한 뒤에만 시작한다. 이 Phase의 목적은 worker process count(작업자 프로세스 수)를 늘려 horizontal scaling(수평 확장)을 주장하는 것이 아니다. current single host(현재 단일 호스트)에서 **PostgreSQL coordination cost(조정 비용)가 EDA execution resource(EDA 실행 자원)와 비교해 실제 병목인지** 판별하는 것이다.

#### Workloads(작업부하)

1. **Coordination microbenchmark(조정 미세 측정):** fixed Run payload(고정 작업 적재), no OpenSTA 또는 controlled short adapter(제어된 짧은 어댑터)로 API count/worker count를 1/2/4/8 단계로 바꾼다. DB claim(권한 획득), lock wait(잠금 대기), transaction latency(트랜잭션 지연), connection count(연결 수)를 측정한다.
2. **Actual OpenSTA workload(실제 OpenSTA 작업부하):** 같은 `max_in_flight`와 actual setup/max fixture(실제 setup/max 픽스처)를 유지해 end-to-end latency(종단 간 지연), accepted/rejected(수락/거절), worker distribution(작업자 분배), execution slot utilization(실행 슬롯 활용률)을 측정한다.

두 workload의 result(결과)를 섞지 않는다. microbenchmark의 처리량은 DB 조정 비용 근거이고, actual OpenSTA의 처리량은 EDA execution resource(EDA 실행 자원)까지 포함한 결과다.

#### Metrics(측정 지표) and trigger(조건)

- p50/p95 claim latency(중앙/상위 95% 권한 획득 지연), submit latency(제출 지연), end-to-end latency(종단 간 지연)
- database lock wait(데이터베이스 잠금 대기), serialization/deadlock error(직렬화/교착 오류), connection count(연결 수)
- worker utilization(작업자 활용률), execution slot utilization(실행 슬롯 활용률), accepted/rejected ratio(수락/거절 비율), queue wait time(대기 시간)
- duplicate execution(중복 실행), duplicate accepted completion(중복 승인 완료), retry/reclaim count(재시도/재할당 횟수)

Kafka challenger trigger(카프카 대안 조건)는 fixed workload(고정 작업부하)에서 다음 중 하나가 반복 관측될 때만 연다.

1. worker 증가에도 OpenSTA CPU/slot(중앙 처리 장치/실행 슬롯)이 아니라 PostgreSQL claim/polling(권한 획득/폴링) 지연이 end-to-end latency의 유의미한 부분을 차지한다.
2. lock wait, connection pressure(연결 압박), claim error(권한 획득 오류)가 처리량 향상을 막는다.
3. retained replay(보존 재생), independent multi-consumer(독립 다중 소비자), reprocessing(재처리), sustained backlog(지속 적체)가 실제 요구 또는 관측으로 생긴다.

절대 SLO(서비스 수준 목표)는 현재 `unrecorded`다. 관측된 비율·반복·환경 값을 evidence(근거)에 기록한 뒤 Human Decision Gate에서 해석한다.

### Phase D — Kafka delivery challenger(카프카 전달 대안) — conditional(조건부)

Phase C trigger가 Human Decision Gate에서 승인된 경우에만 구현한다. Kafka는 source of truth(원본 상태)가 아니다.

```text
API → Kafka topic(토픽) → consumer group(소비자 그룹) worker
                               ↓
                     PostgreSQL Run/Attempt/result(작업/실행 시도/결과)
```

- Kafka responsibility(카프카 책임): job/event delivery(작업/이벤트 전달), partitioned worker distribution(파티션 기반 작업자 분배), redelivery(재전달).
- PostgreSQL responsibility(포스트그레스큐엘 책임): durable Run/Attempt(지속 작업/실행 시도), token-fenced accepted completion(토큰 차단 승인 완료), result/provenance(결과/출처 추적).
- delivery key(전달 키): `job_id`; partition count(파티션 수)와 consumer count(소비자 수)는 실험 기록에 고정한다.
- offset commit(오프셋 커밋) 이전 worker failure(작업자 실패)는 redelivery를 허용한다. delivery 중복을 Kafka가 해결한다고 주장하지 않으며 PostgreSQL idempotency(멱등성)와 Attempt fence(실행 시도 차단)로 accepted completion을 보호한다.

#### Kafka comparison(카프카 비교)

PostgreSQL polling/claim baseline(포스트그레스큐엘 폴링/권한 획득 기준선)과 동일 Run payload(작업 적재), worker count(작업자 수), OpenSTA resource budget(자원 예산), arrival pattern(도착 패턴)으로 비교한다.

| dimension(관점) | PostgreSQL baseline(포스트그레스큐엘 기준선) | Kafka challenger(카프카 대안) |
| --- | --- | --- |
| delivery(전달) | queued Run polling(대기 작업 폴링) | topic/partition/consumer group(토픽/파티션/소비자 그룹) |
| state(상태) | PostgreSQL | PostgreSQL |
| worker failure(작업자 실패) | lease/reconciliation(임대/상태 재조정) | redelivery + lease/reconciliation(재전달 + 임대/상태 재조정) |
| comparison metric(비교 측정) | Phase C metrics(단계 C 측정) | 동일 metrics + redelivery/offset boundary(재전달/오프셋 경계) |

Kafka queue throughput(카프카 대기열 처리량)가 상승해도 actual OpenSTA end-to-end throughput(실제 OpenSTA 종단 간 처리량)이 유의미하게 늘지 않으면, EDA execution resource(EDA 실행 자원)가 병목이라는 결론으로 기록한다. Kafka operational adoption(카프카 운영 채택)은 보류할 수 있다.

## 6. Verification portfolio(검증 포트폴리오)

| type(유형) | Phase B(단계 B) | Phase C/D(단계 C/D) |
| --- | --- | --- |
| unit(단위) | token, attempt generation, reclaim eligibility(재할당 가능 조건) | metric aggregation(측정 집계), trigger classification(조건 분류) |
| integration(통합) | PostgreSQL + API + separate worker + actual OpenSTA | multi-process submit/claim/delivery path(다중 프로세스 제출/권한 획득/전달 경로) |
| regression(회귀) | full suite(전체 묶음), local SQLite contract 유지 | baseline/challenger 동일 contract(기준선/대안 동일 계약) |
| fault-injection(장애 주입) | B1–B3 kill boundary(종료 경계) | consumer loss/redelivery/offset boundary(소비자 손실/재전달/오프셋 경계), 단 Phase D만 |
| contract(계약) | one effective claim, one accepted completion(하나의 유효 권한, 하나의 승인 완료) | PostgreSQL state authority(상태 원본 권한), delivery duplicate safety(전달 중복 안전성) |

CI/CD gate(CI/CD 관문)는 dependency lockfile(의존성 잠금 파일) 설치와 full software contract suite(전체 소프트웨어 계약 묶음)를 유지한다. actual OpenSTA / PostgreSQL fault injection(실제 OpenSTA / PostgreSQL 장애 주입)은 dedicated disposable database(전용 일회성 데이터베이스)와 recorded local fixture(기록된 로컬 픽스처)를 요구하므로, 실행 여부와 skip reason(건너뜀 이유)을 별도 기록한다. skipped test(건너뛴 테스트)를 live failure evidence(실제 장애 근거)로 승격하지 않는다.

## 7. Explicit exclusions(명시적 제외)

- multi-host child liveness(다중 호스트 하위 프로세스 생존성), remote execution supervisor(원격 실행 감독자), PID reuse 해결
- PostgreSQL replication/failover(복제/장애 조치), backup/restore(백업/복원), network partition(네트워크 분할), DB restart(데이터베이스 재시작)
- Kubernetes, autoscaling, Redis, priority scheduler(우선순위 스케줄러), license server
- Kafka production adoption(카프카 운영 채택)은 Phase D evidence와 Human Decision Gate 전에는 제외
- exactly-once execution, multi-region, distributed transaction, consensus/leader election

## 8. Decision and evidence records(결정과 근거 기록)

각 Phase(단계)는 implementation(구현) 전에 Red test(실패 테스트)와 계획을 기록하고, 실행 뒤 `docs/evidence/`에 raw output(원시 출력), fixture(픽스처), environment(환경), revision(리비전), limitation(한계)을 기록한다. `docs/decisions/`에는 Human Decision(사람 결정), Changed belief(판단 변화) 또는 `pending human decision`을 기록한다.

Career OS에는 계획 전문, raw metric(원시 측정), 미확정 판단을 복제하지 않는다. project repository(프로젝트 저장소)의 commit(커밋)된 plan/evidence/decision 링크와 제한 요약만 적재한다.
