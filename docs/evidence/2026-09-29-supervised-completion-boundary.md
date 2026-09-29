# Supervised completion boundary(감독 실행 완료 경계) fault-injection(장애 주입) evidence(근거)

Date(날짜): 2026-09-29

## Question(질문)

OpenSTA child process(하위 프로세스)가 exit code(종료 코드) `0`으로 끝났지만, Host-local Execution Supervisor(호스트 로컬 실행 감독자)가 report(보고서)를 검증하고 accepted completion(승인된 완료)을 기록하기 전에 사라지면 그 Run(작업)을 성공으로 추정하는가?

## Environment(환경)

- shared PostgreSQL(공유 PostgreSQL)과 `host-agent-a`/`host-agent-b` two logical Host Agent(두 논리 호스트 에이전트)를 사용했다.
- 각 Agent(에이전트)는 같은 Mac의 Docker Linux VM(도커 리눅스 가상 머신) 안의 별도 container(컨테이너)다. physical multi-host(물리 다중 호스트) 증거는 아니다.
- `supervisor-a`는 Host A(호스트 A)의 execution request(실행 요청)만 claim(선점)한다.
- OpenSTA는 fixed Linux ARM image(고정 리눅스 ARM 이미지)와 기존 `run.tcl` fixture(픽스처)로 실행했다.
- test-only hold(테스트 전용 대기) `EDA_SUPERVISOR_HOLD_BEFORE_FINALIZE_SECONDS=25`는 `PROCESS_EXITED` termination witness(종료 증거)를 쓴 뒤, validation/finalization(검증/최종 확정) 전에만 적용했다. 운영 기본값은 `0`이다.

## Procedure(절차) and observation(관측)

1. Host B Worker(호스트 B 워커)를 중지해 `completion-boundary-kill-v2`를 Host A로 제한했다.
2. Host A Worker(호스트 A 워커)가 `QUEUED` Run을 claim하고 supervised execution request(감독 실행 요청)를 만들었다.
3. Supervisor A(감독자 A)가 실제 OpenSTA child를 시작했다. durable request(지속 요청)에 `process_pid=6`이 기록됐다.
4. child가 종료되자 Supervisor A가 아래 durable boundary(지속 경계)를 기록하고 test-only hold(테스트 전용 대기)에 들어갔다.

```text
completion-boundary-kill-v2 | RUNNING | RUNNING |
lease_expires_at=1790642484.612146 | request=COMPLETED |
process_pid=6 | witness=PROCESS_EXITED | exit=0
```

5. 이 시점에 Supervisor A container(컨테이너)를 `SIGKILL`했다. container exit(컨테이너 종료)는 `137`이었다.
6. Attempt lease(실행 시도 리스)가 만료된 뒤 Host B Worker를 시작해 recovery scan(복구 스캔)을 수행했다.

```text
completion-boundary-kill-v2 | FAILED | UNKNOWN | ABANDONED |
supervisor_terminated | request=COMPLETED | PROCESS_EXITED | exit=0
```

## Proven result(증명된 결과)

`PROCESS_EXITED` witness(종료 증거)와 exit code(종료 코드) `0`는 accepted success(승인된 성공)가 아니다. Supervisor가 report parsing(보고서 파싱), semantic validation(의미 검증), provenance validation(출처 검증), fenced final write(차단된 최종 기록)를 끝내기 전에 사라지면 recovery(복구)는 Attempt=`ABANDONED`, Run=`FAILED`, trust=`UNKNOWN`으로 fail closed(실패 시 닫기)한다.

이 동작은 duplicate accepted completion(중복 승인 완료)과 stale success inference(오래된 성공 추정)를 막는다. `PROCESS_EXITED` witness는 recovery candidate(복구 후보)를 닫을 권한만 제공하며, 결과의 정상성을 증명하지 않는다.

## Host runtime loss(호스트 런타임 손실) companion injection(동반 주입)

별도 Run(작업) `host-runtime-loss-v1`에서는 Host A Worker(호스트 A 워커)와 Host A Supervisor(호스트 A 감독자)를 모두 `SIGKILL`했다. 주입 직전 durable request(지속 요청)는 `RUNNING`, `process_pid=7`이었으므로 실제 child start(하위 프로세스 시작) 뒤의 손실이었다.

테스트 하니스가 두 container exit(컨테이너 종료) `137`을 확인한 뒤에만 `RUNTIME_TERMINATED` witness(런타임 종료 증거)를 기록했다. lease expiry(리스 만료) 후 Host B Worker(호스트 B 워커)는 다음 상태를 기록했다.

```text
host-runtime-loss-v1 | FAILED | UNKNOWN | ABANDONED |
supervisor_terminated | request=COMPLETED | RUNTIME_TERMINATED
```

따라서 foreign Host Agent(외부 호스트 에이전트)는 remote PID(원격 PID)를 생존/종료 증거로 사용하지 않았고, durable runtime witness(지속 런타임 증거)가 있을 때만 failed closure(실패 종료)를 수행했다.

## Worker loss with surviving Supervisor(감독자 생존 워커 손실)

`worker-loss-supervisor-heartbeat`에서는 Supervisor A(감독자 A)가 child start(하위 프로세스 시작) 뒤 test-only hold(테스트 전용 대기) `35`초를 유지하도록 했다. Attempt lease(실행 시도 리스)는 `30`초였고, Worker A(워커 A)는 child가 `RUNNING`, `process_pid=8`인 것을 확인한 뒤 `SIGKILL`했다.

Supervisor는 execution owner(실행 소유자)의 host session(호스트 세션)과 attempt lease(실행 시도 리스)를 주기적으로 갱신했다. Worker 손실 뒤 42초가 지난 결과는 다음과 같다.

```text
worker-loss-supervisor-heartbeat | SUCCEEDED | TRUSTED | SUCCEEDED |
request=COMPLETED | PROCESS_EXITED | exit=0
```

따라서 살아 있는 Supervisor는 Worker의 `waitpid`/report collection(종료 대기/보고서 수집) 공백을 대신하는 execution owner(실행 소유자)이며, lease expiry(리스 만료)만으로 child failure(하위 프로세스 실패)를 추정하지 않는다.

## Related checks(관련 검증)

- portable regression suite(이식 가능 회귀 묶음): `81` tests passed, `13` skipped.
- contract suite(계약 묶음): `8` tests passed. 이 묶음에는 foreign `PROCESS_EXITED` witness(외부 종료 증거)가 success(성공)를 뜻하지 않는 회귀 검증이 포함된다.
- disposable PostgreSQL regression suite(일회성 PostgreSQL 회귀 묶음): `81` tests passed.

## Limits(한계)

- Supervisor container loss(감독자 컨테이너 손실)의 runtime termination witness(런타임 종료 증거)는 Supervisor 자체가 쓸 수 없다. 이 문서의 host-runtime-loss injection(호스트 런타임 손실 주입)도 test harness(테스트 하니스)가 Docker runtime(도커 런타임) 관측 뒤 `RUNTIME_TERMINATED` witness를 썼다. 배포 가능한 durable runtime observer(지속 런타임 관찰자)는 아직 구현하지 않았다.
- execution owner(실행 소유자)인 Supervisor는 자기 child를 감독하는 동안 host session(호스트 세션)과 attempt lease(실행 시도 리스)를 갱신한다. 그러나 Supervisor 자체가 사라졌을 때 자동 runtime witness(런타임 증거)를 쓰는 배포 구성은 여전히 없다.
- physical-host failure(물리 호스트 장애), remote process liveness(원격 프로세스 생존성), shared artifact storage(공유 산출물 저장소), automatic retry(자동 재시도), throughput scaling(처리량 확장)은 검증하지 않았다.
