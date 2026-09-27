# Same-host recovery closure(동일 호스트 복구 보정)와 multi-host readiness(다중 호스트 준비) 계획

작성일: 2026-09-27
상태: same-host correction(동일 호스트 보정) 구현·검증 완료; multi-host M0(다중 호스트 M0) logical-agent contract(논리 에이전트 계약) 구현·검증 완료; M1 single-machine multi-node environment probe(단일 머신 다중 노드 환경 탐침) 완료; actual OpenSTA M1-E2E baseline(실제 OpenSTA M1 종단 간 기준선) 완료; M1 fault-injection(장애 주입) 대기

원본 기준(source of truth, 원본 기준)은 이 repository(저장소)다. Career OS(커리어 운영체제)에는 commit(커밋), evidence(근거), decision(결정)의 링크와 제한 요약만 적재한다.

## 1. Correction trigger(보정 계기)

기존 same-host reconciliation(동일 호스트 상태 재조정)은 lease expiry(리스 만료)를 reconciliation candidate(상태 재조정 후보)로 해석하고, live child(생존 하위 프로세스)에는 duplicate execution(중복 실행)을 막았다. 그러나 worker process(워커 프로세스)가 죽고 OpenSTA child process(하위 프로세스)만 자연 종료한 경우, 종료 코드(exit code, 종료 코드), report/artifact(보고서/산출물), parser(파서), provenance(출처 추적)를 회수해 성공을 확정할 주체가 없었다.

따라서 `child alive → RUNNING 유지`만으로는 Run(작업)이 종료 상태로 수렴한다는 contract(계약)가 아니었다. 이번 보정의 안전한 결론은 orphan child(고아 하위 프로세스)의 성공을 추정하지 않고 **유예 기간 뒤 안전하게 종료 가능한 경우 종료 요청하고, 종료 확인 뒤 `ABANDONED` Attempt(폐기된 실행 시도)와 `FAILED` Run으로 닫는 것**이다.

## 2. Adopted same-host contract(채택한 동일 호스트 계약)

```text
expired lease(만료 리스)
  → recovery claim(복구 권한 획득): DB token(데이터베이스 토큰)으로 한 Worker만 관측
  → local process identity(로컬 프로세스 식별) + dedicated process group(전용 프로세스 그룹) 확인
  → child alive and before orphan deadline(고아 기한 전 생존)
       → recovery claim 해제, 재실행 금지
  → child alive after deadline(고아 기한 후 생존)
       → identity/process group 일치 시 SIGTERM 요청
  → child exited or identity cannot be safely controlled(종료 또는 안전 제어 불가)
       → atomic finalization(원자적 종료): Attempt=ABANDONED, Run=FAILED
```

- recovery claim(복구 권한 획득)은 `RUNNING` Attempt(실행 시도), expired lease(만료 리스), 만료되었거나 없는 기존 recovery token(복구 토큰)에서만 가능하다.
- normal terminal completion(정상 종단 완료)도 lease token(리스 토큰)과 recovery fence(복구 차단)를 확인해 Attempt와 Run을 한 transaction(트랜잭션)에서 갱신한다.
- Worker(워커)는 시작과 polling loop(폴링 루프)마다 recovery scan(복구 스캔)을 수행한다. 이는 별도 Reconciler service(상태 재조정 서비스)를 도입하지 않은 bounded profile(제한된 프로필)의 선택이다.
- `process_identity`는 PID reuse(프로세스 식별자 재사용)를 완전히 해결하는 전역 신원이 아니다. 현재 host(호스트)에서 `ps` 관측값을 비교해 잘못된 PID/process group(프로세스 그룹)에 signal(신호)을 보내지 않기 위한 fail-closed guard(실패 시 닫는 보호장치)다.
- success recovery(성공 복구)는 제공하지 않는다. 원래 Worker가 잃어버린 stdout/stderr(표준 출력/표준 오류), exit code(종료 코드), report validation(보고서 검증)을 새 Worker가 안전하게 재구성하지 못하기 때문이다.

## 3. Proven guarantee(증명된 보장)와 boundary(경계)

검증한 것은 disposable PostgreSQL(일회성 PostgreSQL)과 실제 OpenSTA fixture(고정 OpenSTA 픽스처)를 사용한 **동일 물리 호스트의 독립 프로세스** 범위다.

- two recovery contender(두 복구 경쟁자) 중 하나만 recovery claim을 획득한다.
- expired Attempt(만료 실행 시도)의 recovery finalization(복구 종료)은 Attempt=`ABANDONED`, Run=`FAILED`를 함께 기록한다.
- Worker startup(워커 시작) scan(스캔)은 `QUEUED` Run이 없어도 stale Attempt(오래된 실행 시도)를 종료 상태로 수렴시킨다.
- verified orphan child(검증된 고아 하위 프로세스)는 deadline(기한) 후 종료 요청을 받고, 다음 scan에서 fail-closed terminal state(실패 시 닫는 종료 상태)로 수렴한다.
- stale token(오래된 토큰)은 terminal write(종단 기록)를 할 수 없다.

검증하지 않은 것은 remote PID(원격 PID), host reboot(호스트 재부팅), network partition(네트워크 분할), artifact shared storage(산출물 공유 저장소), orphan success acceptance(고아 성공 승인), automatic re-execution(자동 전체 재실행), multi-host throughput(다중 호스트 처리량)이다. 따라서 이 결과는 horizontal scaling(수평 확장)이나 distributed execution recovery(분산 실행 복구)의 증거가 아니다.

## 4. Multi-host cycle(다중 호스트 사이클) 후보

별도 Reconciler process(상태 재조정 프로세스)만 추가해도 잃어버린 Worker의 `waitpid`/report collection(종료 대기/보고서 수집)은 복원되지 않는다. 다중 호스트에서는 host-local execution supervisor(호스트 로컬 실행 감독자)가 durable execution manifest(지속 실행 명세)를 쓰고 결과를 회수하는 구조가 필요하다.

```text
API(응용 프로그래밍 인터페이스)
  → PostgreSQL Run/Attempt authority(작업/실행 시도 원본 권한)
  → Host Agent(호스트 에이전트) on host A/B(호스트 A/B)
      → local execution supervisor(로컬 실행 감독자)
          → OpenSTA dedicated process group(전용 프로세스 그룹)
      → durable execution manifest(지속 실행 명세)
      → fenced completion(차단된 완료 기록)
```

PostgreSQL(포스트그레스큐엘)은 Run/Attempt state(작업/실행 시도 상태), lease token(리스 토큰), host identity(호스트 식별), execution identity(실행 식별), accepted completion(승인된 완료)의 authoritative state(원본 상태)로 남긴다. Host Agent는 local liveness(로컬 생존성), process identity(프로세스 식별), exit collection(종료 수집), artifact validation handoff(산출물 검증 인계)를 책임진다. DB의 lease expiry(리스 만료)는 여전히 failure(실패)가 아니라 reconciliation candidate(상태 재조정 후보)다.

### Candidate comparison(후보 비교)

| candidate(후보) | orphan completion(고아 완료) 책임 | 현재 판단 |
| --- | --- | --- |
| Worker-internal recovery(워커 내부 복구) | 원래 Worker가 살아 있을 때만 가능 | 동일 호스트 bounded profile(제한된 프로필)에만 채택 |
| Separate Reconciler(별도 상태 재조정기) | scan/claim은 가능하나 exit/report 회수는 불가 | 단독 도입 기각 |
| Host Agent + central coordination(호스트 에이전트 + 중앙 조정) | Agent가 local child와 manifest를 감독 | 다중 호스트 challenger(대안) |
| Container/Job runtime supervisor(컨테이너/작업 런타임 감독자) | runtime 상태와 artifact contract가 있으면 회수 가능 | 배포 환경 선택 뒤 challenger(대안) |

## 5. Entry trigger(시작 조건), prediction(예측), falsification(반증), stop condition(종료 조건)

### Human Decision Gate(사람 결정 관문)

사용자 승인으로 M0 logical-agent implementation(논리 에이전트 구현)을 시작했다. 다음 중 하나가 실제 요구나 측정으로 확인되기 전에는 M1 physical-host implementation(물리 호스트 구현)을 시작하지 않는다.

1. 서로 다른 두 host(호스트)에 실제 OpenSTA execution(실행)을 배치해야 하는 운영 요구가 승인된다.
2. single-host resource-aware concurrency(단일 호스트 자원 인지 동시성)의 CPU/memory/license slot(중앙 처리 장치/메모리/라이선스 슬롯) 한계가 workload(작업부하)로 확인된다.
3. host failure domain(호스트 장애 영역)을 분리해야 한다는 reliability requirement(신뢰성 요구)가 승인된다.

M0 scope(범위)는 shared PostgreSQL(공유 PostgreSQL)과 two logical Host Agent(두 논리 호스트 에이전트)다. 각 Agent는 `host_id`, `host_epoch`, `session_id`, `execution_id`를 Attempt(실행 시도)에 기록한다. 새 host epoch(호스트 세대)는 이전 session(세션)의 heartbeat(심장박동)와 terminal completion(종단 완료)을 fence(차단)한다. foreign execution(외부 실행)은 local PID(로컬 PID)로 관측·종료하지 않고 `deferred_remote_execution`으로 남긴다.

Prediction(예측): Host Agent(호스트 에이전트)가 host identity(호스트 식별)와 execution manifest(실행 명세)를 기록하면, central Worker(중앙 워커)는 remote PID를 관측하지 않고도 stale attempt(오래된 실행 시도)의 재조정 권한을 안전하게 판정할 수 있다.

Falsification(반증): agent loss(에이전트 손실), host reboot(호스트 재부팅), network partition(네트워크 분할), duplicated completion(중복 완료) 중 하나에서 stale Agent(오래된 에이전트)가 accepted completion(승인된 완료)을 기록하거나, 새 Attempt(새 실행 시도)가 confirmed-live execution(생존 확인 실행)과 overlap(중첩)하면 구조를 기각·보강한다.

M1 baseline(기준선): fixed Linux ARM OpenSTA image(고정 리눅스 ARM OpenSTA 이미지)에서 Agent A/B가 각각 실제 fixture(픽스처)를 `SUCCEEDED/TRUSTED`로 끝내고 Agent별 artifact volume(산출물 볼륨)에 report(보고서)를 남겼다. 상세 결과는 `docs/evidence/2026-09-27-multihost-m1-opensta-e2e.md`에 기록한다.

Stop condition(종료 조건): two-host fault-injection(2호스트 장애 주입)에서 agent loss + child alive/dead(에이전트 손실 + 하위 프로세스 생존/종료), completion boundary loss(완료 경계 손실), host reboot simulation(호스트 재부팅 모의)을 한 번씩 실행하고, 각각의 Run/Attempt/manifest row(행)와 limitation(한계)을 기록한 뒤 Human Decision Gate로 멈춘다. Kafka(카프카)는 이 Cycle의 기본 구성 요소가 아니다. 2026-09-26 Phase C(단계 C)의 PostgreSQL coordination limit(조정 한계) 측정은 Kafka trigger(카프카 조건)를 충족하지 않았다.

## 6. Required test portfolio(필수 테스트 포트폴리오)

| type(유형) | same-host correction(동일 호스트 보정) | later multi-host(후속 다중 호스트) |
| --- | --- | --- |
| unit(단위) | identity/deadline/fence(식별/기한/차단) | manifest validation(명세 검증), host epoch(호스트 세대) |
| integration(통합) | PostgreSQL recovery claim(복구 권한) | two host agent(두 호스트 에이전트) + shared DB(공유 DB) |
| regression(회귀) | portable/full PostgreSQL suite(이식 가능/전체 PostgreSQL 묶음) | same-host contract(동일 호스트 계약) 유지 |
| fault-injection(장애 주입) | Worker SIGKILL(워커 강제 종료) + live child(생존 하위 프로세스) | agent/host/network/artifact loss(에이전트/호스트/네트워크/산출물 손실) |
| contract(계약) | one recovery owner(하나의 복구 소유자), atomic terminal state(원자적 종료 상태) | host epoch + accepted completion fence(호스트 세대 + 승인 완료 차단) |

각 변경은 TDD Red-Green-Refactor(테스트 주도 개발 실패-통과-리팩터)로 시작하고 Test Scope Review(테스트 범위 검토)에서 실제 OpenSTA와 분리된 host(호스트) 경계까지 확장할지를 결정한다.
