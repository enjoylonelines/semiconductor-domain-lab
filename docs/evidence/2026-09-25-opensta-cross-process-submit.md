# Cross-process SQLite submit contention(교차 프로세스 SQLite 제출 경합) 근거

작성일: 2026-09-25

## Prediction(예측)

single-host SQLite WAL(단일 호스트 라이트급 SQL 쓰기 전용 로그)에서 fixed tiny OpenSTA workload(고정 작은 OpenSTA 작업부하) 8개를 independent submitter process(독립 제출자 프로세스)가 동시에 생성하면, short write transaction(짧은 쓰기 트랜잭션)은 completion(완료)을 막지 않아야 한다. database locked(데이터베이스 잠김), missing Run(누락 작업), duplicate child(중복 하위 프로세스)가 발생하면 PostgreSQL(포스트그레스큐엘) 또는 durable queue(지속 대기열) challenger(도전 대안)를 비교할 조건이다.

## Actual experiment(실제 실험)

```text
PYTHONPATH=src .venv/bin/python tools/opensta_cross_process_submit_benchmark.py
```

각 submitter(제출자)는 별도 Python process(파이썬 프로세스), 별도 SQLite connection(라이트급 SQL 연결), 서로 다른 `job_id`, 실제 OpenSTA child process(실제 OpenSTA 하위 프로세스)를 사용한다. 8개가 같은 ready gate(준비 관문) 뒤 동시에 제출됐다.

원시 결과는 [JSON](2026-09-25-opensta-cross-process-submit.json)에 있다. 8개 모두 execution future(실행 예약)를 만들고 8개 child process(하위 프로세스)가 관찰됐으며 8개 Run(작업)이 `SUCCEEDED`로 완료됐다. 전체 wall time(경과 시간)은 약 0.427초였다. 이 값은 단일 반복의 작은 고정 workload(작업부하) 측정이며 production throughput(운영 처리량)이나 장시간 SQLite capacity(라이트급 SQL 용량)를 뜻하지 않는다.

## Decision(결정)과 stop condition(종료 조건)

현재 조건에서는 SQLite write contention(라이트급 SQL 쓰기 경합)의 실패 신호가 없으므로 PostgreSQL(포스트그레스큐엘), persistent queue(영속 대기열), Kafka(카프카)를 채택하지 않는다. 이 cycle(사이클)은 여기서 멈춘다.

다음 중 하나가 실제 workload(작업부하)에서 관측될 때만 동일 조건으로 challenger(도전 대안)를 다시 연다: sustained database locked error(지속 데이터베이스 잠김 오류), retryable submit failure(재시도 가능 제출 실패), p95 submit latency(상위 95% 제출 지연) 성장, longer-lived Run(더 오래 실행되는 작업)의 write pressure(쓰기 압박), host(호스트) 추가, retained replay(보존 재생), independent multi-consumer(독립 다중 소비자), reprocessing(재처리) 요구. Kafka(카프카)는 이 요구들과 measured throughput limit(측정된 처리량 한계)이 함께 확인될 때만 후보가 된다.
