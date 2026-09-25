# Cross-process resource budget(교차 프로세스 자원 예산) 근거

작성일: 2026-09-25

## Baseline(기준선)

9개의 external service(외부 서비스)가 각각 `max_in_flight=8`로 설정되고, 서로 다른 실제 OpenSTA job(정적 타이밍 분석 도구 작업)을 동시에 하나의 SQLite database(라이트급 SQL 데이터베이스)에 제출했다. process-local budget(프로세스 로컬 예산)은 서로 합산되지 않아 OpenSTA child process(하위 프로세스)가 9개 생성되고 거절은 0개였다. 즉, 단일 service(서비스)의 8개 제한을 host-wide budget(호스트 전체 예산)으로 주장할 수 없었다.

## Reinforcement(보강)과 revalidation(재검증)

`runs.job_id` creation claim(작업 생성 권한)과 shared in-flight count(공유 진행 중 실행 수)를 SQLite `BEGIN IMMEDIATE` transaction(즉시 트랜잭션) 안에서 처리한다. existing Run(기존 작업)은 예산보다 먼저 반환해 idempotency(멱등성)를 보존한다. 새 작업만 `QUEUED`/`RUNNING` 수를 확인하며 예산이 가득 차면 Run(작업)을 만들지 않고 `BackpressureError`를 반환한다.

동일 command(명령)를 다시 실행했다.

```text
PYTHONPATH=src .venv/bin/python tools/opensta_cross_process_budget_baseline.py
```

재검증에서는 9개 contender(경쟁 제출자) 중 8개만 예약·실행됐고, 1개는 거절됐으며 관찰된 실제 OpenSTA child process(하위 프로세스)는 8개였다. 원시 기준선·재검증 값은 [JSON](2026-09-25-opensta-cross-process-budget.json)에 있다.

## Decision(결정)과 limits(한계)

이 local SQLite(로컬 라이트급 SQL 저장소) profile(프로파일)에서는 `max_in_flight=8`을 shared host admission budget(공유 호스트 입장 예산)으로 채택한다. persistent queue(영속 대기열), PostgreSQL(포스트그레스큐엘), Redis(레디스), Kafka(카프카)는 이 문제에 도입하지 않는다.

이것은 하나의 host(호스트), 하나의 SQLite file(라이트급 SQL 파일), fixed tiny workload(고정 작은 작업부하), 9개 동시 제출만 검증한다. SQLite lock wait(라이트급 SQL 잠금 대기) p95(상위 95% 지연), long-running Run(장시간 작업), database on network storage(네트워크 저장소 데이터베이스), multi-host(다중 호스트), crash during transaction(트랜잭션 중 충돌), fairness(공정성)는 열려 있다. 실제 workload(작업부하)에서 이들이 한계가 될 때만 durable queue(지속 대기열) 또는 PostgreSQL(포스트그레스큐엘)을 challenger(도전 대안)로 비교한다. Kafka(카프카)는 replay(재생)·retention(보존)·independent multi-consumer(독립 다중 소비자)·reprocessing(재처리)·measured throughput limit(측정된 처리량 한계)이 함께 필요할 때만 연다.
