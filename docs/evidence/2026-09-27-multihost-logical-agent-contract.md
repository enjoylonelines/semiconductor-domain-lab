# Multi-host M0(다중 호스트 M0) logical-agent contract(논리 에이전트 계약) evidence(근거)

Date(날짜): 2026-09-27

## Scope(범위)

M0는 two logical Host Agent(두 논리 호스트 에이전트)가 shared PostgreSQL(공유 PostgreSQL)을 통해 execution ownership(실행 소유권)을 기록하는 contract(계약)이다. `host_id`, `host_epoch`, `session_id`, `execution_id`가 Attempt(실행 시도)에 기록되고, 새 host epoch(호스트 세대)가 old session(이전 세션)의 heartbeat(심장박동)와 accepted completion(승인된 완료)을 차단한다.

foreign execution(외부 실행)이 stale(오래됨)으로 보여도 다른 Agent가 local PID(로컬 PID)를 확인·종료하지 않는다. 결과는 `deferred_remote_execution`이며, remote child liveness(원격 하위 프로세스 생존성)는 Host Agent(호스트 에이전트) 또는 runtime supervisor(런타임 감독자)가 있는 M1의 책임으로 남긴다.

## Commands and results(명령과 결과)

```text
PYTHONPATH=src uv run python -W error::ResourceWarning \
  -m unittest tests.contract.test_host_agent -v

Ran 2 tests in 0.030s
OK

EDA_POSTGRES_TEST_DSN=postgresql://…/eda_operational_test \
PYTHONPATH=src uv run python -W error::ResourceWarning \
  -m unittest tests.integration.test_host_agent_postgres -v

Ran 1 test in 0.056s
OK
```

The PostgreSQL test(포스트그레스큐엘 테스트)는 independent connections(독립 연결) 둘을 사용했다. `boot-b` session(세션)이 같은 `host-a`를 등록한 뒤 `boot-a` session(세션)의 terminal completion(종단 완료)은 거부됐고, 새 session(세션)은 old execution(이전 실행)을 `deferred_remote_execution`으로만 관측했다.

## Supported claim(뒷받침하는 주장) and limit(한계)

이 근거는 central PostgreSQL(중앙 PostgreSQL)에서 host epoch fencing(호스트 세대 차단)과 foreign PID non-interference(외부 PID 비간섭)를 지지한다.

이 근거는 physical multi-host(물리 다중 호스트), network partition(네트워크 분할), remote OpenSTA exit/report collection(원격 OpenSTA 종료/보고서 수집), artifact shared storage(산출물 공유 저장소), horizontal throughput(수평 처리량), automatic recovery(자동 복구)를 지지하지 않는다.
