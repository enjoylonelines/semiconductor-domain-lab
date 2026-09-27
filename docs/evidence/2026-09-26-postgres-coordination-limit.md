# PostgreSQL coordination limit(조정 한계) Phase C evidence(근거)

Date: 2026-09-26
Raw result: [`2026-09-26-postgres-coordination-limit.json`](2026-09-26-postgres-coordination-limit.json)

## Question and bounded method(질문과 제한된 방법)

The question was whether PostgreSQL polling/claim(폴링/권한 획득), rather
than the fixed actual OpenSTA workload(실제 OpenSTA 작업부하), became the
meaningful source of end-to-end latency as independent workers increased on
one host. This is not a horizontal-scaling claim.

A dedicated disposable PostgreSQL 16 database ran three repeats at worker
counts 1, 2, 4, and 8. The coordination microbenchmark(조정 미세 측정) used
32 zero-duration synthetic Runs(합성 작업); the actual workload used 8
recorded OpenSTA setup/max Runs(실제 작업) with the same durable Run/Attempt
and claim path. Each worker ran one execution at a time. A connection sample
was taken after every worker had opened its database connection and before
claiming began.

## Results

| workload(작업부하) | workers(작업자) | throughput p50(처리량 중앙값) | claim p95(권한 획득 상위 95%) | elapsed p95(경과 상위 95%) | connections(연결 수) |
| --- | ---: | ---: | ---: | ---: | ---: |
| coordination | 1 | 26.771 runs/s | 2.520 ms | 1222.277 ms | 2 |
| coordination | 2 | 49.566 runs/s | 4.213 ms | 645.709 ms | 3 |
| coordination | 4 | 88.748 runs/s | 6.965 ms | 362.701 ms | 5 |
| coordination | 8 | 130.937 runs/s | 6.794 ms | 244.941 ms | 9 |
| actual OpenSTA | 1 | 3.899 runs/s | 3.984 ms | 2071.969 ms | 2 |
| actual OpenSTA | 2 | 7.555 runs/s | 4.999 ms | 1061.407 ms | 3 |
| actual OpenSTA | 4 | 14.086 runs/s | 4.745 ms | 571.794 ms | 5 |
| actual OpenSTA | 8 | 22.472 runs/s | 8.254 ms | 359.900 ms | 9 |

Every sample had `SUCCEEDED` Runs(성공 작업), `TRUSTED` results(신뢰 결과),
and exactly one Attempt(실행 시도) per Run. At 8 workers, actual OpenSTA
claim p95 was 8.254 ms against 359.900 ms elapsed p95, about 2.3% of that
bounded end-to-end time. No claim error(권한 획득 오류), lock failure(잠금
실패), connection pressure(연결 압박), duplicate execution(중복 실행), or
accepted duplicate completion(승인된 중복 완료) was observed.

## Falsification and decision gate(반증과 결정 관문)

The Phase C Kafka trigger would have been supported if repeated measurements
showed PostgreSQL claim/polling latency as a meaningful portion of end-to-end
latency, or if lock/connection pressure or delivery requirements stopped
throughput. None occurred in this experiment. Retained replay(보존 재생),
independent multi-consumer(독립 다중 소비자), reprocessing(재처리), and
sustained backlog(지속 적체) were also not observed requirements.

AI recommendation(인공지능 권고): retain PostgreSQL coordination for this
bounded profile and do not open the Kafka challenger. Human decision(사람
결정) and Changed belief(변경된 판단) remain pending. The experiment cannot
justify production capacity, remote database behavior, multi-host liveness,
long-running designs, licensing pressure, or a Kafka rejection beyond this
workload.
