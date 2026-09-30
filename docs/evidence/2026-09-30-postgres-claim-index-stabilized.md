# PostgreSQL claim index stabilized measurement

Date: 2026-09-30  
Base revision: `69ad647`

## Purpose

The first PostgreSQL coordination cycle showed that a partial queue-order index removed an avoidable sequential scan and sort, but the end-to-end synthetic coordination result was noisy.

This follow-up exists only to produce a defensible improvement number for portfolio/resume use.

## Fixed condition

Each condition was executed five times.

- PostgreSQL 16 Alpine
- PostgreSQL CPU: 0.5
- PostgreSQL memory: 384 MiB
- 32 concurrent workers
- 1024 queued jobs per repeat
- fresh database per repeat
- SyntheticTimingAdapter
- same benchmark code and container image
- only difference: presence of `idx_eda_runs_queued_updated_at`

This remains a coordination-only benchmark. It is not OpenSTA or EDA throughput.

## Five-repeat result

### Baseline: queue-order index removed

| repeat | throughput | claim p50 | claim p95 | claim p99 | max sampled lock waits |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 204.4 Runs/s | 2.95 ms | 97.8 ms | 168.1 ms | 10 |
| 2 | 214.9 Runs/s | 2.57 ms | 91.6 ms | 95.9 ms | 10 |
| 3 | 189.5 Runs/s | 3.05 ms | 92.3 ms | 180.5 ms | 11 |
| 4 | 169.2 Runs/s | 3.47 ms | 95.1 ms | 104.0 ms | 8 |
| 5 | 191.9 Runs/s | 2.83 ms | 96.3 ms | 167.2 ms | 10 |

Median:

- throughput: **191.9 Runs/s**
- claim p50: **2.95 ms**
- claim p95: **95.1 ms**
- claim p99: **167.2 ms**
- max sampled lock waits: **10**

### Indexed

| repeat | throughput | claim p50 | claim p95 | claim p99 | max sampled lock waits |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 216.5 Runs/s | 2.25 ms | 89.2 ms | 92.6 ms | 6 |
| 2 | 207.1 Runs/s | 1.92 ms | 89.2 ms | 108.2 ms | 10 |
| 3 | 242.5 Runs/s | 1.98 ms | 76.5 ms | 114.0 ms | 6 |
| 4 | 211.1 Runs/s | 2.10 ms | 92.6 ms | 162.3 ms | 21 |
| 5 | 234.1 Runs/s | 2.00 ms | 91.6 ms | 167.7 ms | 5 |

Median:

- throughput: **216.5 Runs/s**
- claim p50: **2.00 ms**
- claim p95: **89.2 ms**
- claim p99: **114.0 ms**
- max sampled lock waits: **6**

## Median improvement

| metric | baseline | indexed | change |
| --- | ---: | ---: | ---: |
| throughput | 191.9 Runs/s | 216.5 Runs/s | **+12.8%** |
| claim p50 | 2.95 ms | 2.00 ms | **-32.0%** |
| claim p95 | 95.1 ms | 89.2 ms | **-6.1%** |
| claim p99 | 167.2 ms | 114.0 ms | **-31.8%** |
| max sampled lock waits | 10 | 6 | **-40.0%** |

All ten repeats completed all 1024 jobs successfully.

## How to use these numbers

The most defensible portfolio-level result is:

> 동일한 32-way 데이터베이스 부하를 5회 반복 측정해, 대기 작업 조회 인덱스 적용 후 처리량 중앙값을 **191.9 → 216.5 Runs/s(+12.8%)**로 높이고 작업 선점 지연 중앙값을 **2.95 → 2.00ms(-32.0%)**로 줄였습니다.

A second technical-detail result is:

> `EXPLAIN ANALYZE`에서 대기 작업 탐색의 전체 조회·정렬을 인덱스 조회로 바꾸며, 기록된 단일 쿼리 실행시간을 **0.726 → 0.273ms(-62.4%)**로 줄였습니다.

The 62.4% value is a captured single-query plan observation, while +12.8% / -32.0% are five-repeat median system-level measurements. They must not be presented as the same metric.

## Metrics not recommended as headline claims

- p99 improved by 31.8% on the five-repeat median, but individual runs were highly variable.
- sampled lock-wait median improved by 40%, but one indexed repeat observed 21 waiters.
- p95 improved only 6.1%, showing that high-concurrency coordination pressure remains.

These should stay as supporting evidence rather than headline resume numbers.

## Interpretation

The index made the PostgreSQL claim path measurably more efficient, but did not eliminate the broader 32-way coordination ceiling.

This is useful because the improvement claim and the architecture decision remain consistent:

1. a concrete query inefficiency was found and improved;
2. the same workload was remeasured rather than assumed fixed;
3. the remaining high-concurrency limit was preserved as evidence;
4. current real SS Heavy OpenSTA throughput remains far below this database coordination range, so the actual EDA bottleneck is still compute capacity rather than PostgreSQL.

## Raw data

`benchmark/raw/postgres-index-stabilized-69ad647/summary.json`
