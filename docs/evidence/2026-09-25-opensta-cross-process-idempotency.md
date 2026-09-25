# Cross-process idempotency(교차 프로세스 멱등성) 근거

작성일: 2026-09-25

## Problem(문제)

in-process lock(프로세스 내부 잠금)만으로는 두 independent submitter process(독립 제출자 프로세스)가 동시에 같은 `job_id`의 Run(작업)이 없다고 읽는 경쟁 상태를 막지 못한다. 두 쪽이 execution future(실행 예약)를 만들면 worker lease(작업자 임대)가 후속 실행을 막더라도 잘못된 예약·오류 경로가 남는다.

## Adopted mechanism(채택 기제)

SQLite(라이트급 SQL 저장소)의 `runs.job_id` primary key(기본 키) `INSERT OR IGNORE` 결과를 creation claim(생성 권한)으로 사용한다. insert(삽입)에 성공한 submitter(제출자)만 future(예약)를 만들고, 충돌한 submitter는 durable Run(지속 작업)을 다시 읽는다. canonical spec hash(정규 명세 해시)가 같으면 그 Run(작업)을 반환하며, 다르면 idempotency conflict(멱등성 충돌)로 거절한다.

## Actual experiment(실제 실험)

다음 command(명령)는 서로 다른 두 Python process(파이썬 프로세스)를 ready gate(준비 관문)에서 동시에 풀어 같은 immutable job_id(불변 작업 식별자)를 제출한다. 각 process(프로세스)는 실제 OpenSTA child process(실제 OpenSTA 하위 프로세스)를 관찰해 PID를 공용 기록에 추가한다.

```text
PYTHONPATH=src .venv/bin/python tools/opensta_cross_process_idempotency_benchmark.py
```

원시 결과는 [JSON](2026-09-25-opensta-cross-process-idempotency.json)에 있다. 두 submitter(제출자) 중 하나만 `scheduled=true`였고, 관찰된 OpenSTA child process(하위 프로세스)는 정확히 1개였다. 다른 submitter(제출자)는 미래 실행을 만들지 않고 당시 `RUNNING` Run(작업)을 반환했다. 실행 완료 뒤 durable Run(지속 작업)은 `SUCCEEDED`였다.

## Limits(한계)와 trigger(조건)

이 근거는 한 host(호스트), SQLite WAL(라이트급 SQL 쓰기 전용 로그), fixed OpenSTA workload(고정 OpenSTA 작업부하), 하나의 동일 명세로 제한된다. distributed database(분산 데이터베이스), multi-host worker(다중 호스트 작업자), network partition(네트워크 분할), SQLite write contention(라이트급 SQL 쓰기 경합), process crash(프로세스 충돌) 중 transaction(트랜잭션) 경계는 검증하지 않았다.

다른 host(호스트)·database(데이터베이스) 또는 sustained concurrent submitters(지속 동시 제출자)가 실제 요구가 되면 unique constraint(고유 제약), transactional outbox(트랜잭션 아웃박스), durable queue(지속 대기열)를 challenger(도전 대안)로 같은 job identity(작업 식별성)와 duplicate execution(중복 실행) 지표에서 비교한다. Kafka(카프카)는 replay(재생), retention(보존), independent multi-consumer(독립 다중 소비자), reprocessing(재처리), measured throughput limit(측정된 처리량 한계) 중 하나가 관측될 때만 후보로 연다.
