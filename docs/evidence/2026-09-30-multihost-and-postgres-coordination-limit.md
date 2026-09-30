# Multi-host correctness and PostgreSQL coordination ceiling evidence

Date: 2026-09-30  
Base revision: `dd432bc bench: close postgres backlog boundary`

## 1. Scope

This cycle continued after the SS Heavy backlog result showed that the current same-VM workload is limited by OpenSTA execution capacity rather than PostgreSQL delivery.

The goals were:

1. revalidate the current logical multi-host ownership / fencing / recovery contract;
2. identify what can and cannot be claimed about OpenSTA capacity scaling in the available environment;
3. remove OpenSTA compute cost and stress only PostgreSQL coordination until a reproducible database-side ceiling appeared;
4. allow one bounded PostgreSQL correction and rerun the same failing condition.

Kafka was not an objective.

## 2. Logical multi-host correctness regression

Current contract and integration suites were run against a fresh disposable PostgreSQL database on the current revision.

Result:

```text
21 tests
20 passed
1 skipped
```

The skipped case requires the separate recorded local OpenSTA integration fixture and was not counted as live evidence.

The passing suite retained these invariants:

- old host epoch / old session cannot accepted-complete after a new epoch becomes authoritative;
- foreign Host Agent does not interpret a remote PID as local liveness evidence;
- foreign `PROCESS_EXITED` witness never implies accepted success;
- durable runtime termination evidence allows fail-closed recovery;
- only one Supervisor claims a host-local execution request;
- queued execution Attempt leases are refreshed only while the delivery remains `QUEUED`;
- Supervisor ownership takes over after claim;
- PostgreSQL claim remains atomic across independent workers;
- recovery claim and terminal fencing remain single-owner / transactional.

This is logical multi-host evidence only: separate host identities, sessions, Supervisor ownership, PostgreSQL connections, and PID namespaces share one Docker Linux VM.

It does not prove physical multi-host network or failure-domain behavior.

## 3. Why physical OpenSTA capacity scaling was not claimed

The current Docker VM exposes eight CPUs.

The validated SS Heavy profile already uses eight one-CPU Supervisors and saturates those execution CPUs.

Creating:

```text
Host A: 8 Supervisors
Host B: 8 Supervisors
```

inside the same eight-CPU VM would not create sixteen CPUs. It would only oversubscribe the same physical compute budget.

Therefore this cycle does not claim two-host OpenSTA throughput scaling without a second physical compute budget.

The existing SS Heavy execution result remains the relevant capacity baseline:

- eight fixed one-CPU Supervisors;
- approximately 0.63–0.69 SS Heavy Runs/s in the accepted backlog stages;
- PostgreSQL coordination not limiting those execution slots.

## 4. PostgreSQL coordination-only stress

To expose the next database limit without OpenSTA CPU masking it, the EDA execution cost was replaced with `SyntheticTimingAdapter`.

This benchmark is **not EDA throughput**.

### PostgreSQL environment

- PostgreSQL 16 Alpine
- CPU limit: 0.5 CPU
- memory limit: 384 MiB
- `max_connections=100`
- `shared_buffers=128MB`
- fresh database per stage / repeat
- runtime workers use `PostgresStore(..., migrate=False)`
- schema migration occurs before worker concurrency begins

Raw summary:

`benchmark/raw/postgres-coordination-limit-dd432bc/summary.json`

## 5. Baseline coordination result

### 8 workers / 128 Runs

| metric | result |
| --- | ---: |
| throughput | 200.8 Runs/s |
| claim call p95 | 4.87 ms |
| claim call p99 | 18.11 ms |
| max lock-wait sessions | 0 |
| max connections | 9 |
| completion | 128/128 `SUCCEEDED` |

This is the low-contention baseline.

### 16 workers / 512 Runs

Three repeats:

| repeat | throughput | claim p95 | claim p99 | max lock waits | max connections |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 233.0 Runs/s | 47.5 ms | 72.9 ms | 3 | 17 |
| 2 | 211.1 Runs/s | 65.1 ms | 75.5 ms | 3 | 17 |
| 3 | 244.1 Runs/s | 46.6 ms | 71.9 ms | 6 | 17 |

Compared with eight workers, throughput improvement already became sub-linear while claim tail latency and lock waits appeared repeatedly.

### 32 workers / 1024 Runs — reproduced DB ceiling

Three repeats before the PostgreSQL correction:

| repeat | throughput | claim p95 | claim p99 | max lock waits | max connections |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 213.0 Runs/s | 94.3 ms | 123.3 ms | 9 | 33 |
| 2 | 207.5 Runs/s | 87.2 ms | 94.9 ms | 7 | 34 |
| 3 | 217.0 Runs/s | 88.7 ms | 162.0 ms | 9 | 34 |

The median throughput was **213.0 Runs/s**, which no longer improved over the 16-worker range and was below its best samples.

The median claim p95 was **88.7 ms** and the median observed lock-wait count was **9**.

All 1024 Runs still completed successfully. The limit is therefore a coordination throughput/latency ceiling, not a correctness failure.

## 6. Actual claim SQL plan before correction

The real `claim_next_run` query is:

```sql
WITH candidate AS (
  SELECT job_id
  FROM eda_runs
  WHERE status='QUEUED'
  ORDER BY updated_at
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE eda_runs r
SET status='RUNNING', updated_at=...
FROM candidate
WHERE r.job_id=candidate.job_id
RETURNING r.spec_payload
```

With 1024 queued rows, `EXPLAIN (ANALYZE, BUFFERS)` showed:

```text
Seq Scan on eda_runs
  Filter: status = 'QUEUED'
  rows=1024
→ Sort on updated_at
→ LockRows
→ Limit 1
```

Observed execution time in the captured plan: **0.726 ms**.

This confirmed a simple PostgreSQL-internal inefficiency before considering any delivery broker.

## 7. One permitted PostgreSQL correction

A partial claim index was added:

```sql
CREATE INDEX idx_eda_runs_queued_updated_at
ON eda_runs(updated_at)
WHERE status='QUEUED'
```

A regression test now checks that the migration creates this index.

On the same 1024 queued-row plan, `EXPLAIN (ANALYZE, BUFFERS)` changed to:

```text
Index Scan using idx_eda_runs_queued_updated_at
→ LockRows
→ Limit 1
```

Captured execution time: **0.273 ms**.

The individual candidate lookup became materially cheaper and the sequential scan / explicit sort disappeared.

## 8. Same-condition rerun after the index

32 workers / 1024 Runs, three fresh-database repeats:

| repeat | throughput | claim p95 | claim p99 | max lock waits | max connections |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 218.0 Runs/s | 95.0 ms | 133.9 ms | 4 | 34 |
| 2 | 233.9 Runs/s | 75.1 ms | 136.2 ms | 5 | 33 |
| 3 | 207.1 Runs/s | 93.4 ms | 120.4 ms | 7 | 34 |

Median before index:

- throughput: **213.0 Runs/s**
- claim p95: **88.7 ms**
- lock-wait sessions: **9**

Median after index:

- throughput: **218.0 Runs/s**
- claim p95: **93.4 ms**
- lock-wait sessions: **5**

The index improved the individual SQL plan and reduced observed lock pressure, but did **not** materially remove the concurrent coordination ceiling.

Median throughput changed by only about **+2.3%**, while claim p95 remained in the same order of magnitude.

Therefore the 32-worker ceiling is not explained only by the missing queue-order index. Under this deliberately tiny 0.5-CPU PostgreSQL budget, transaction scheduling / row-lock coordination / connection concurrency now dominate the synthetic path.

## 9. What this means for the EDA architecture

A database coordination limit was successfully reproduced, but it is far above the current real SS Heavy demand.

Current real SS Heavy execution rate:

```text
~0.63–0.69 Runs/s with 8 CPU-bound Supervisors
```

Synthetic PostgreSQL coordination ceiling in this bounded 0.5-CPU database:

```text
~200–240 state transitions / Runs per second
```

These numbers must not be treated as the same workload, but their scale matters.

The current EDA execution path is hundreds of times slower per Run than the bounded PostgreSQL coordination ceiling.

Even a hypothetical second physical host doubling the current eight-CPU execution capacity would remain far below the observed database ceiling.

Therefore:

- **DB bottleneck exists as a coordination microbenchmark limit.**
- **DB bottleneck is not currently the end-to-end EDA bottleneck.**
- Kafka is not justified by the current SS Heavy operating profile.
- The next meaningful production-scale trigger would be actual execution capacity growing enough that available OpenSTA slots begin waiting on PostgreSQL delivery/claim.

## 10. Kafka trigger decision

The synthetic stress satisfies the statement:

> PostgreSQL coordination has a measurable bounded ceiling under high claim concurrency.

It does **not** satisfy the stronger architecture trigger:

> PostgreSQL coordination is starving real EDA execution capacity.

The real workload evidence still shows the opposite.

Therefore no Kafka A/B is opened in this cycle.

Kafka remains gated until a real or production-representative execution profile approaches this coordination boundary, or a separate requirement appears for retained event history, replay, independent consumers, partition ordering, or event reprocessing.

## 11. Verified claims

- logical multi-host ownership/fencing contracts still pass on the current revision;
- physical two-host throughput is not proven;
- PostgreSQL claim coordination begins showing repeated lock/latency pressure between 16 and 32 concurrent synthetic claimers in the bounded 0.5-CPU PostgreSQL profile;
- a missing queue-order index caused a real avoidable scan/sort cost;
- the partial index fixes that query plan but does not remove the higher-concurrency coordination ceiling;
- current SS Heavy execution remains far below the measured coordination ceiling.

## 12. Unverified claims

- physical two-host SS Heavy throughput scaling
- network partition / physical host reboot behavior
- remote artifact-store behavior
- PostgreSQL replication/failover
- production PostgreSQL capacity
- Kafka performance for this EDA path
- MCMM/sign-off customer workload behavior
- license-server bottlenecks
- autoscaling behavior

## 13. Current architecture

```text
API / submitter
      |
      v
PostgreSQL
  - authoritative Run / Attempt state
  - QUEUED backlog
  - atomic claim / ownership / fencing
  - accepted completion / provenance
      |
      +-------------------+
      |                   |
      v                   v
Host Agent A          Host Agent B
(logical proof)       (logical proof)
      |                   |
      v                   v
Supervisor pool      Supervisor pool
      |                   |
      +---------+---------+
                |
                v
             OpenSTA
```

Current same-VM SS Heavy capacity is still bounded by the eight physical CPU execution slots. Physical Host A + Host B throughput scaling remains a later validation when a second compute budget exists.

## 14. Portfolio summary candidate

1. SS Heavy backlog stress showed that PostgreSQL could continuously feed eight CPU-saturated OpenSTA execution slots, so I did not introduce Kafka merely because a queue existed.
2. I then removed OpenSTA compute cost and increased only PostgreSQL claim concurrency, reproducing a coordination ceiling at 32 synthetic claimers with rising claim latency and repeated lock waits.
3. EXPLAIN ANALYZE showed the queued-Run claim path performing a sequential scan and sort, so I added a partial queue-order index and re-ran the identical workload.
4. The index removed the avoidable scan/sort and reduced observed lock pressure, but the higher-concurrency ceiling remained; because real SS Heavy throughput was still hundreds of times below this DB ceiling, PostgreSQL remained the appropriate coordination layer and Kafka stayed gated.


## 14.1 Five-repeat index A/B validation

To produce a more stable portfolio-grade improvement number, the same 32-worker / 1024-Run coordination-only condition was repeated five times per condition, using a fresh database for every repeat.

This comparison is still a PostgreSQL coordination microbenchmark, not OpenSTA/EDA throughput.

### Median across five fresh-database repeats

| metric | without queue index | with queue index | median change |
| --- | ---: | ---: | ---: |
| throughput | 189.7 Runs/s | 234.3 Runs/s | **+23.5%** |
| claim p50 | 2.88 ms | 2.10 ms | **-27.1%** |
| claim p95 | 95.3 ms | 85.1 ms | **-10.8%** |
| claim p99 | 127.9 ms | 148.9 ms | **+16.4% worse** |
| observed lock-wait sessions | 13 | 6 | **-53.8%** |

All ten runs completed 1024/1024 Runs successfully with no worker execution errors.

The repeated A/B therefore supports these bounded claims:

- the partial queue-order index improved median coordination throughput by about **23.5%** under this 32-claimer synthetic stress;
- median claim latency improved by **27.1% at p50** and **10.8% at p95**;
- observed lock-wait pressure fell by about **53.8%** at the median;
- **p99 did not improve** and was worse in the indexed sample, so the experiment does not support a tail-latency improvement claim.

This is more defensible than using the single captured EXPLAIN execution-time change as the primary portfolio result. The EXPLAIN result remains useful as the causal explanation: the index removed the queued-row sequential scan and explicit sort. The five-repeat A/B is the preferred improvement number because it measures the concurrent system behavior under identical load.

Raw data: `benchmark/raw/postgres-coordination-limit-dd432bc/index-ab-5x.json`.

## 15. Stop condition

The cycle stops here because the requested DB coordination bottleneck was reproduced, one reasonable PostgreSQL repair was applied, and the same failing stage was remeasured.

Further synthetic worker counts would characterize a larger artificial ceiling but would not change the current architecture decision without a corresponding real EDA execution demand.
