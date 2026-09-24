# Decision record: bounded attempt lifecycle and stale-running recovery

Evidence: [P1 async lifecycle evidence](../evidence/2026-09-24-async-lifecycle-cycle.md). Plan: [P1 async lifecycle plan](../plans/2026-09-24-async-lifecycle-recovery-cycle.md).

## Implemented technical decision

Adopt a durable attempt-start record and local-owner-aware stale reconciliation for the synthetic in-process service. The baseline showed a post-artifact interruption could leave only an unresolved run. The reinforcement preserves attempt numbering and classifies retryable timeout/transport failures separately from non-retryable parser, execution-outcome, tool-exit, and execution-error cases.

Recovered work terminates as `FAILED`; it is not implicitly retried and cannot become `SUCCEEDED` through recovery. A live local future wins over stale database time because a caller-side timeout does not establish that a tool child stopped.

## Pending human decision

Choose the product policy only if this synthetic boundary needs extension:

1. whether an `ABANDONED/worker_unavailable` attempt should require explicit resubmission or receive a new bounded retry; and
2. what external ownership/lease evidence is required before a restarted process may declare a worker or child dead.

The current evidence does not authorize either policy. It also does not authorize Kafka: retained replay, independent consumers, retention, reprocessing, ordering, and throughput/backpressure have not been observed in this workload.

## Stop

The selected synthetic retry and reconciliation slice is closed. Keep cross-process recovery, child termination, queue admission, and broker evaluation as separate experiments with their own workload and acceptance criteria.
