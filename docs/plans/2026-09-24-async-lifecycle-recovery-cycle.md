# P1 bounded async lifecycle and recovery cycle

## Problem and scope

Determine whether the in-process worker preserves enough durable state to distinguish a retryable failure, a non-retryable execution result, and a worker interruption after an adapter has returned an artifact but before the final run state is persisted.

The selected slice is synthetic and uses SQLite plus failure injection. It does not add a queue, PostgreSQL, Redis, Kafka, a subprocess supervisor, or a cross-process lease.

## Human hypothesis and falsification

- **Prediction:** before reinforcement, an interruption at the post-artifact/pre-terminal boundary leaves `runs.status=RUNNING` with no attempt history. Recording `RUNNING` before adapter execution makes that ambiguity durable; recovery can terminally mark it failed only after the local future is no longer live.
- **Falsification:** if the baseline already has a durable attempt, do not add the attempt-start transition. If recovery changes a still-live local worker to terminal `FAILED`, reject the recovery rule. If a non-retryable tool exit starts a later attempt, reject the retry taxonomy.
- **Invariant:** a run is never made `SUCCEEDED` by reconciliation. Each started attempt has one numbered durable history row. `timeout` and `transport_error` may retry within `max_attempts`; parse-invalid, unknown execution outcome, tool exit, and ordinary execution errors do not. A stale `RUNNING` record is recovered only when no local live future owns it.

## Selected reinforcement

1. Persist attempt `RUNNING` before calling the adapter, retaining `started_at`, `updated_at`, and `retry_class` on the attempt.
2. Record retryable and non-retryable terminal outcomes on that same attempt number; a retry starts the next number after bounded delay.
3. Add `recover_stale_runs(stale_after_seconds)`. It turns an orphaned stale `RUNNING` attempt into `ABANDONED/worker_unavailable` and the run into `FAILED`; it skips an active local future because caller timeout or a stale database timestamp cannot prove its tool child ended.

`execution_status` remains `runs.status`; parser and check status remain separate `parse_status` and `check_status`. `retry_class` describes the recorded failure policy; recovery is represented by `ABANDONED`, `worker_unavailable`, and a recovery error rather than a new run-state system.

## Kafka decision boundary

Kafka remains out of scope. This slice has one durable store and one local owner. Re-open a broker comparison only if an observed workload requires all of: retained replay across an owner restart, two independent consumers of the same lifecycle event, independently scheduled reprocessing, ordering per run across those consumers, or measured backpressure/throughput beyond the current owner. Record the actual workload, retention window, consumers, replay behavior, and comparison result before selecting Kafka.

## Stop condition

Stop after the injected interruption, retry/no-retry, and live-worker disagreement cases pass on the same synthetic workload. Do not add automatic retry after recovery or cross-process child inspection without a separate human policy decision.
