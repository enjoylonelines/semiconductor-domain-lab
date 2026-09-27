# Same-host recovery closure(동일 호스트 복구 보정) evidence(근거)

Date(날짜): 2026-09-27
Scope(범위): disposable PostgreSQL(일회성 PostgreSQL), 동일 호스트의 separate Worker process(분리 워커 프로세스), actual OpenSTA fixture(실제 OpenSTA 픽스처)

## Change under test(검증 대상 변경)

- recovery claim(복구 권한 획득)과 recovery token(복구 토큰)으로 concurrent recovery(동시 복구)를 차단했다.
- terminal attempt/run persistence(종단 실행 시도/작업 저장)를 one database transaction(하나의 데이터베이스 트랜잭션)으로 묶었다.
- Worker polling loop(워커 폴링 루프)가 startup(시작)과 idle poll(유휴 폴링)에서 stale recovery(오래된 상태 복구)를 실행한다.
- OpenSTA child(하위 프로세스)의 local process identity(로컬 프로세스 식별)와 process group(프로세스 그룹)을 기록한다.
- worker loss(워커 손실) 뒤 live orphan child(생존 고아 하위 프로세스)는 grace period(유예 기간) 동안 재실행하지 않으며, deadline(기한) 뒤 검증된 process group에 종료 요청하고, 종료 확인 뒤 `ABANDONED`/`FAILED`로 fail closed(실패 시 닫기)한다.

## Commands and results(명령과 결과)

```text
EDA_POSTGRES_TEST_DSN=postgresql://…/eda_operational_test \
PYTHONPATH=src uv run python -W error::ResourceWarning \
  -m unittest tests.integration.test_postgres_operational_path.PostgresRecoveryFenceTests -q

Ran 4 tests in 0.138s
OK

PYTHONPATH=src uv run python -W error::ResourceWarning \
  -m unittest discover -s tests -q

Ran 75 tests in 5.544s
OK (skipped=12)

EDA_POSTGRES_TEST_DSN=postgresql://…/eda_operational_test \
PYTHONPATH=src uv run python -W error::ResourceWarning \
  -m unittest discover -s tests -q

Ran 75 tests in 8.041s
OK
```

The PostgreSQL run(포스트그레스큐엘 실행) followed `TRUNCATE eda_runs CASCADE` on the disposable test database. The full suite includes the actual OpenSTA worker-loss fault injection(워커 손실 장애 주입), including the verified orphan deadline(검증된 고아 기한) path.

## Supported claim(뒷받침하는 주장)

이 근거는 same-host(동일 호스트)에서 recovery ownership(복구 소유권), stale token rejection(오래된 토큰 거부), atomic terminal persistence(원자적 종단 저장), 그리고 orphan process(고아 프로세스)의 fail-closed convergence(실패 시 닫는 수렴)를 지지한다.

이 근거는 orphan success recovery(고아 성공 복구), remote liveness(원격 생존성), multi-host recovery(다중 호스트 복구), horizontal throughput(수평 처리량), Kafka adoption(카프카 채택)을 지지하지 않는다.
