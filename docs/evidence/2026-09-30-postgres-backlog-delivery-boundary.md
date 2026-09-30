# PostgreSQL backlog / delivery boundary evidence

Date: 2026-09-30
Base revision: 9ad020a (fix: retain queued execution leases)

## Question

Can PostgreSQL-backed Run polling, execution-request delivery, and authoritative state keep eight fixed SS Heavy execution slots fed while Runs arrive faster than OpenSTA can execute them, and does any measured coordination limit justify Kafka?

## Fixed environment

The accepted stages kept the same VM, PostgreSQL 16, one Host Agent, eight SS Heavy Supervisors, 1 CPU / 1.5 GiB per Supervisor, 30-second execution lease, supervised execution mode, and the pinned SS Heavy input.

Provenance remained uniform:
- Liberty SHA-256: 9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361
- netlist SHA-256: b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce
- script SHA-256: cad5237c39e914222b23d6f30a86c6c34d5782bad5480dc7c8714607fb2688a1

Raw summaries:
- ../../benchmark/raw/ss-heavy-backlog-9ad020a/8-runs.json
- ../../benchmark/raw/ss-heavy-backlog-9ad020a/32-runs.json
- ../../benchmark/raw/ss-heavy-backlog-9ad020a/128-runs.json

## Failure discovered before accepted backlog evidence

The first isolated backlog environment exposed a PostgreSQL deadlock between release_terminal_execution_requests() and ALTER TABLE eda_execution_requests ADD COLUMN IF NOT EXISTS process_pid integer.

Every PostgresStore constructor was still performing schema migration, so runtime Host Agent / Supervisor startup could overlap DDL with steady-state coordination queries. PostgreSQL aborted the Host Agent transaction.

This is preserved in 2026-09-30-backlog-startup-migration-deadlock.md and classified as a database lifecycle defect, not a backlog-volume limit.

The single permitted PostgreSQL correction was used here:
1. add an explicit python -m eda_lab migrate bootstrap;
2. migrate once before runtime startup;
3. allow runtime processes to set EDA_POSTGRES_AUTO_MIGRATE=0.

No Kafka component was introduced.

## Accepted stages

| Runs | completion | elapsed / execution window | throughput | backlog evidence | execution-slot behavior | lock wait | max connections | expired lease | unexpected UNAVAILABLE |
| ---: | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| 8 | 8/8 SUCCEEDED/TRUSTED | 12.693 s | 0.630 Runs/s | none | 8 active | 0 | 11 | 0 | 0 |
| 32 | 32/32 SUCCEEDED/TRUSTED | 46.433 s | 0.689 Runs/s | max observed Run queue 23 | while Run backlog > 0, active execution requests never fell below 8 | 0 | 11 | 0 | 0 |
| 128 | 128/128 SUCCEEDED; uniform provenance | 189.426 s from first dispatch to last witness | about 0.676 Runs/s over execution window | captured late-run queue 38 -> 31 | every captured backlog-positive snapshot had 8 RUNNING execution requests | 0 | 11 live / 10 after completion | 0 | 0 |

The accepted 128 stage ended with 128 execution requests COMPLETED, zero ABANDONED Attempts, zero recovery-claimed Attempts, and zero failed Runs.

## Submission behavior

The fully observed 32-Run stage had submit latency p50 1.105 ms, p95 1.763 ms, and p99 4.748 ms. This does not show submission-path pressure relative to the corrected 8-Run baseline.

The first accepted 128 stage did not preserve per-submit latency stdout because an outer command replay collided with the still-running benchmark client. That limitation is explicit in the raw record; no 128-Run submit-latency claim is made.

## Interpreting execution-request created-to-claimed latency

32 Runs:
- p50 76.6 ms
- p95 11.278 s
- p99 11.404 s

128 Runs:
- p50 93.6 ms
- p95 11.172 s
- p99 11.894 s

This is delivery queue residence, not SQL execution time. When all eight Supervisors are executing Heavy OpenSTA, a newly created execution request can wait roughly one Heavy execution wave before a Supervisor becomes free.

The discriminator is slot utilization. At 32 Runs, active execution requests never fell below 8 while durable Run backlog existed. The captured 128 backlog snapshots also kept eight execution requests RUNNING. PostgreSQL lock wait stayed zero. Therefore the long upper tail is execution-capacity saturation rather than database coordination starvation.

## Lease / recovery correctness under backlog

Across accepted evidence:
- expired live Attempt lease: 0
- recovery claim: 0
- unexpected UNAVAILABLE: 0
- ABANDONED Attempt: 0
- non-terminal Run after completion: 0
- provenance mismatch: 0

The current architecture bounds dispatched execution requests to the fixed execution capacity. Larger backlog remains primarily in durable eda_runs.QUEUED state until Host Agent capacity opens instead of creating an unbounded population of leased Attempts. The prior queued-delivery lease failure therefore did not recur even though the 128-Run execution window lasted much longer than one 30-second lease interval.

## Rejected / invalid observations

The following are excluded from accepted evidence:
1. startup-migration deadlock: runtime DDL overlapped operational queries;
2. an initial corrected 8-Run observation: execution succeeded but the observer still hardcoded database name eda_m1 for connection sampling;
3. the first attempted 128 measurement after 32: another submitter prefix contaminated the in-flight population;
4. a second 128 repeat: duplicate benchmark invocation created independent 128-Run and 41-Run prefixes.

They remain failure-mode or harness evidence and are not merged into accepted metrics.

## Kafka trigger evaluation

Performance trigger: not met after migration/runtime separation.

Observed:
- no execution-slot starvation while Run backlog was available;
- no PostgreSQL lock wait;
- no connection growth beyond the small fixed profile;
- no deadlock after separating migration from runtime startup;
- no lease/recovery correctness regression;
- similar SS Heavy execution throughput at 32 and 128 Runs.

Requirement trigger: not met. This cycle did not establish a current requirement for retained event history, replay, independent multiple consumers, partition ordering, event reprocessing, or a durable delivery backlog independent of authoritative Run state.

## Stop decision

Do not execute 512 or 1024 Runs only to populate a larger table.

The 128-Run stage already held the fixed eight Heavy execution slots busy for roughly 189 seconds while preserving completion, provenance, lease, recovery, lock, and connection invariants. More Runs in the same VM/profile would primarily extend OpenSTA CPU saturation without a new PostgreSQL coordination signal.

Bounded conclusion:

Within this validated same-VM SS Heavy profile, PostgreSQL coordination did not become the limiting resource after migration/runtime separation. The observed limit remained fixed OpenSTA execution capacity, so the Kafka challenger trigger was not met.

This is not a production-capacity claim and does not reject Kafka for different delivery requirements or larger deployments.

## Current architecture

API / submitter
  -> PostgreSQL authoritative Run state
  -> eda_runs.QUEUED durable backlog
  -> Host Agent with bounded dispatch capacity 8
  -> PostgreSQL execution request
  -> eight fixed Supervisors
  -> SS Heavy OpenSTA
  -> PostgreSQL Attempt / accepted completion / provenance

PostgreSQL remains authoritative for Run / Attempt state, ownership, fencing, accepted completion, and provenance.

## Verified claims

- eight fixed SS Heavy Supervisors remained occupied while PostgreSQL held a larger Run backlog;
- accepted 32 and 128 Run stages completed without observed lock wait, expired lease, recovery, UNAVAILABLE, or completion failure;
- the queued-delivery lease correction remained valid with a longer-lived overall backlog;
- runtime schema DDL can deadlock with operational coordination and should be separated from steady-state process startup.

## Not verified

- production capacity or SLO
- physical multi-host throughput
- remote database latency or network partition behavior
- PostgreSQL replication/failover
- 512 / 1024 backlog behavior
- actual customer MCMM/sign-off workloads
- license-seat pressure
- Kafka comparative performance
- autoscaling

## Next Human Decision Gate

The delivery decision closes before multi-host work starts.

Next question:

Does the execution ownership / recovery invariant validated on one Host remain correct when two Hosts share PostgreSQL and one Host Agent or runtime disappears?

Kafka is not a prerequisite for that cycle.
