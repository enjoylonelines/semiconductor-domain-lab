# PostgreSQL backlog / delivery boundary cycle

Date: 2026-09-30  
Base revision: `9ad020a fix: retain queued execution leases`  
Branch context: `multihost-validation-cycle`
Status: closed at 128 Runs; Kafka challenger not triggered. See `../evidence/2026-09-30-postgres-backlog-delivery-boundary.md` and `../decisions/2026-09-30-postgres-delivery-kafka-gate.md`.

## 1. Question

> With the validated SS Heavy execution profile held fixed, how far can the current PostgreSQL-backed Run polling / execution-request claim / authoritative state coordination path absorb a backlog that grows faster than OpenSTA execution capacity, and does any observed limit justify opening a Kafka delivery challenger?

Kafka adoption is not an objective of this cycle. The preferred outcome is still “retain PostgreSQL” unless a measured coordination limit or an actual delivery requirement crosses the predeclared gate below.

## 2. Preconditions and closed scope

The preceding fixed-batch scaling cycle is treated as closed before this cycle starts.

Validated execution profile to freeze:

- SS Heavy / `picorv32x64`
- pinned netlist / Liberty / OpenSTA inputs and provenance hashes
- same application revision for a comparison set
- same PostgreSQL configuration
- same VM CPU / RAM
- eight Supervisor execution slots
- one CPU / 1.5 GiB per Supervisor
- one live Host Agent
- same lease / heartbeat / fencing contracts
- accepted completion invariant

The queued-delivery lease failure discovered during scaling is part of the evidence chain:

- while delivery is `QUEUED`, the live Host Agent refreshes the Attempt lease;
- once a Supervisor changes the delivery to `CLAIMED`, Host Agent refresh stops;
- Supervisor heartbeat then owns Attempt liveness;
- queue wait alone must not be interpreted as worker loss.

Rejected scaling runs remain rejected evidence and are not reused as accepted baseline data.

This cycle does **not** expand Heavy/PVT/resource calibration. Do not add larger fixtures, more corners, 16/32 Supervisors, autoscaling, scheduler features, Kubernetes, Kafka HA, Schema Registry, or multi-host execution.

## 3. Human hypothesis, prediction, falsification

Human hypothesis: PostgreSQL coordination will remain a small component of end-to-end delay while the eight fixed SS Heavy execution slots are saturated; queue wait should grow primarily because execution capacity is bounded, not because delivery cannot keep slots fed.

Prediction before measurement:

- backlog depth and queue wait will rise as submitted Runs exceed eight execution slots;
- OpenSTA execution slots should remain continuously occupied while backlog exists;
- PostgreSQL claim latency should remain small relative to Heavy execution time;
- lock waits, deadlocks/serialization failures, connection pressure, duplicate accepted completion, stale completion, and unexpected `UNAVAILABLE` should remain absent;
- queued Attempt leases should remain live for arbitrarily longer queue waits within the bounded experiment.

Falsification candidates:

- an execution slot is available while queued work exists and delivery/claim delay prevents it from being filled;
- claim latency or submit latency grows structurally with backlog and is reproducible;
- lock waits, transaction failures, deadlocks/serialization errors, or connection pressure recur;
- queued rows make the claim query materially more expensive;
- queue depth causes lease expiry, recovery invocation, unexpected `UNAVAILABLE`, stale completion, duplicate execution, duplicate accepted completion, non-terminal Runs, or provenance mismatch.

## 4. Independent variable and stages

Only arrival/backlog size changes.

Planned bounded stages:

1. 8 Runs
2. 32 Runs
3. 128 Runs
4. 512 Runs
5. 1024 Runs only if the prior stages neither expose a limit nor provide sufficient stable evidence.

Run one stage at a time. Do not execute later stages merely to fill the table.

A stage should be repeated when a suspected coordination failure must be distinguished from noise or environment contamination. Repetition is evidence-driven rather than an automatic production-style soak test.

## 5. Measurements

### Submission

- submit latency p50 / p95 / p99
- submission failures / backpressure / idempotency conflicts
- submission throughput

### PostgreSQL coordination

- execution-request claim latency p50 / p95 / p99 (`claimed_at - created_at`)
- queue depth over time
- execution-request state counts: `QUEUED / CLAIMED / RUNNING / COMPLETED / UNAVAILABLE`
- total / active DB connections
- sessions waiting on locks
- deadlock / serialization / query failures if observed
- expired live Attempt leases
- if queued-row growth correlates with claim degradation, capture `EXPLAIN (ANALYZE, BUFFERS)` for the actual claim query before changing indexes

DB CPU and polling-query rate are optional evidence only when the current environment exposes a reliable source. Do not invent them from unrelated host metrics.

### Execution path

- makespan / throughput
- queue wait p50 / p95 / p99
- number of execution requests in `CLAIMED/RUNNING` while backlog exists
- Supervisor container CPU / memory samples
- whether idle execution capacity appears while `QUEUED > 0`

### Correctness

- terminal Run count
- accepted `SUCCEEDED/TRUSTED` count
- Attempt count per Run
- duplicate accepted completion
- unexpected `UNAVAILABLE`
- expired lease / recovery invocation
- non-terminal Run
- provenance hash mismatch

## 6. Distinguishing execution saturation from coordination saturation

Queue wait growth alone is not a PostgreSQL bottleneck.

Classify the result as execution-capacity saturation when:

- SS Heavy Supervisor CPU is saturated or execution requests remain continuously `CLAIMED/RUNNING`;
- queued work exists;
- claim latency remains small;
- lock wait / connection pressure remain absent;
- no idle execution slot is attributable to delivery delay.

Consider coordination saturation only when delivery/state coordination itself prevents available execution capacity from being used, or when PostgreSQL failure/latency pressure is repeatedly reproduced.

## 7. Kafka challenger trigger — declared before results

### Performance trigger

Open Kafka comparison only if repeated evidence shows PostgreSQL coordination itself causes one or more of:

- idle execution capacity while backlog is available because delivery/claim is delayed;
- substantial baseline-relative submit/claim latency degradation;
- recurring lock / connection / query pressure;
- transaction / deadlock / serialization failures;
- queued-row growth making the actual claim path inefficient after reasonable query/index inspection.

There is no invented production SLO. Record baseline-relative changes and reproducibility, then leave the interpretation as a Human Decision if the evidence is borderline.

### Requirement trigger

Kafka can also be reconsidered if the actual system requirement now includes one of:

- retained event history,
- replay,
- independent multiple consumers,
- consumer-group delivery semantics,
- partition ordering,
- large durable delivery backlog independent of Run state,
- event reprocessing.

If these are not actual requirements, mark the requirement trigger unmet.

## 8. PostgreSQL repair budget before Kafka

If a reproducible coordination limit appears:

1. isolate the failing query/path;
2. determine whether it is a straightforward query/index/config defect;
3. allow exactly one bounded PostgreSQL challenger change;
4. rerun the same workload and execution capacity;
5. open Kafka only if the delivery responsibility itself remains the measured structural limit.

The sequence is:

`slowdown → cause isolation → one reasonable PostgreSQL correction → same-condition remeasurement → structural delivery limit → Kafka challenger`.

## 9. Kafka challenger, only if triggered

Kafka responsibility:

- delivery
- partitioning
- consumer-group distribution
- redelivery

PostgreSQL remains authoritative for:

- Run / Attempt state
- idempotency
- ownership / fencing
- accepted completion
- result / provenance

Compare PostgreSQL baseline and Kafka challenger with the same SS Heavy workload, execution capacity, VM resources, and arrival stage. Compare end-to-end behavior, not broker message throughput in isolation.

Stop after one bounded A/B comparison. Do not expand into cluster HA, KRaft tuning, Kubernetes, Schema Registry, or multi-region work.

## 10. Stop conditions

### Case A — no PostgreSQL coordination limit

Stop when the largest justified bounded backlog preserves correctness, coordination metrics remain stable enough to keep execution slots fed, and the observed bottleneck is SS Heavy execution/resource capacity.

Decision record:

> Within the validated bounded environment, PostgreSQL coordination did not become the limiting resource and the Kafka trigger was not met.

Do not implement Kafka.

### Case B — PostgreSQL coordination limit

Stop the baseline once the same coordination failure is reproducible. Apply the one-change PostgreSQL repair budget above and remeasure. Only then decide whether Kafka comparison is triggered.

## 11. Evidence discipline

Every accepted stage records:

- git revision
- workload / Liberty / netlist / script hashes
- container/image revision if available
- VM resources
- Supervisor count and per-Supervisor limits
- PostgreSQL configuration relevant to the experiment
- raw JSON output
- rejected/invalid runs and reasons
- limitations

If a run is contaminated:

1. reject it;
2. preserve the raw result;
3. record root cause;
4. add or strengthen the relevant contract test;
5. fix;
6. rerun the same condition.

Never silently overwrite evidence.

## 12. Next gate

Physical multi-host validation is a separate cycle after this delivery decision closes. Kafka is not a prerequisite for multi-host validation.

The next multi-host question remains:

> Do the single-host execution ownership / recovery invariants remain valid across two physical/logical Hosts sharing PostgreSQL?
