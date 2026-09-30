# PostgreSQL coordination ceiling decision

Date: 2026-09-30

## Decision

Keep PostgreSQL as the authoritative Run/Attempt and delivery-coordination store for the current EDA execution profile.

Do not open a Kafka challenger from this cycle.

## Evidence

Logical multi-host ownership/fencing contracts remain valid on the current revision.

A PostgreSQL coordination-only benchmark, with OpenSTA execution removed, reproduced a bounded database-side ceiling between 16 and 32 concurrent claimers on a deliberately small PostgreSQL profile:

- PostgreSQL 16
- 0.5 CPU
- 384 MiB
- max_connections=100
- SyntheticTimingAdapter

At 32 workers / 1024 queued Runs, three repeats showed:

- throughput: 207–217 Runs/s before the PostgreSQL correction
- claim p95: 87–94 ms
- repeated lock-wait pressure: 7–9 sessions
- all Runs still completed successfully

The actual claim query originally performed a sequential scan and sort over queued rows. One bounded PostgreSQL correction added:

`idx_eda_runs_queued_updated_at ON eda_runs(updated_at) WHERE status='QUEUED'`

The captured single-query plan changed from Seq Scan + Sort to an index scan and execution time improved from about 0.726 ms to 0.273 ms in the recorded 1024-row example.

However, repeating the same 32-worker / 1024-Run stress after the index produced:

- throughput median: 218.0 Runs/s versus 213.0 Runs/s before (+2.3%)
- claim p95 median: 93.4 ms versus 88.7 ms before
- observed lock-wait median: 5 versus 9 before

The index corrected a real query inefficiency and reduced lock pressure, but did not remove the higher-concurrency coordination ceiling.

## Architecture interpretation

This synthetic DB ceiling is not the current EDA bottleneck.

The validated SS Heavy execution rate with eight one-CPU Supervisors is approximately 0.63–0.69 Runs/s. The bounded PostgreSQL coordination stress remained around 200+ Runs/s.

Therefore the current architecture has a large coordination margin relative to real SS Heavy execution demand. Even a second physical execution host that roughly doubled current OpenSTA capacity would still be far below the measured PostgreSQL coordination ceiling.

## Kafka gate

Performance trigger for a Kafka challenger is **not met for the real EDA profile**.

A synthetic database ceiling alone is insufficient. Kafka becomes relevant only when real execution capacity is available but PostgreSQL delivery/claim prevents those slots from being fed, or when broker-specific product requirements appear such as replay, retained event history, independent consumers, partition ordering, or event reprocessing.

## Multi-host status

Logical multi-host correctness is supported by current tests and prior fault-injection evidence.

Physical multi-host throughput remains unverified because the current Docker VM has only eight CPUs. Running sixteen CPU-bound Supervisors inside that same VM would oversubscribe one physical compute budget rather than prove horizontal scaling.

## Stabilized improvement measurement

A follow-up five-repeat A/B measurement on fresh databases was recorded in `../evidence/2026-09-30-postgres-claim-index-stabilized.md`.

At the same 32-worker / 1024-job synthetic coordination condition, median results changed as follows after the queue-order partial index:

- throughput: 191.9 → 216.5 Runs/s (**+12.8%**)
- claim p50: 2.95 → 2.00 ms (**-32.0%**)
- claim p95: 95.1 → 89.2 ms (**-6.1%**)

This strengthens the claim that the index produced a measurable improvement while preserving the earlier conclusion that it did not remove the higher-concurrency coordination ceiling.

## Next trigger

Reopen the delivery architecture decision when one of the following occurs:

1. a second physical compute host is available and real SS Heavy execution capacity materially increases;
2. real execution slots become idle while durable backlog exists because PostgreSQL delivery cannot feed them;
3. PostgreSQL lock/connection/transaction pressure appears in a production-representative execution profile;
4. a broker-specific requirement becomes real.

Until then, the next scaling investment should be additional OpenSTA compute capacity, not Kafka.
